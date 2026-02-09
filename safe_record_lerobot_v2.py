#!/usr/bin/env python3
"""安全遥操作 + LeRobot 数据录制
在 LeRobot 框架内实现零位对齐、低通滤波和软限位保护
"""

import sys
import math
import os
import time
from pathlib import Path
from typing import Any

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 控制文件路径
CONTROL_DIR = Path("/tmp/lerobot_control")
CONTROL_DIR.mkdir(exist_ok=True)
SAVE_FLAG = CONTROL_DIR / "save_episode"
EXIT_FLAG = CONTROL_DIR / "exit_recording"

# 清理旧的控制文件
SAVE_FLAG.unlink(missing_ok=True)
EXIT_FLAG.unlink(missing_ok=True)

# 过滤 ARX SDK 的冗余输出
class OutputFilter:
    def __init__(self, stream):
        self.stream = stream
        self.buffer = ""

    def write(self, text):
        # 过滤掉 "ARX方舟无限" 消息
        if "ARX方舟无限" not in text and "方舟无限" not in text:
            self.stream.write(text)
            self.stream.flush()

    def flush(self):
        self.stream.flush()

# 应用输出过滤器
sys.stdout = OutputFilter(sys.stdout)
sys.stderr = OutputFilter(sys.stderr)

import numpy as np
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.pipeline_features import aggregate_pipeline_dataset_features, create_initial_features
from lerobot.datasets.utils import combine_feature_dicts
from lerobot.processor import RobotAction, RobotObservation, RobotProcessorPipeline
from lerobot.processor.converters import robot_action_observation_to_transition, transition_to_robot_action
from lerobot.processor.pipeline import ProcessorStep, EnvTransition
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.scripts.lerobot_record import record_loop
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.utils.utils import log_say


def init_file_based_listener():
    """基于文件的控制监听器 - 检查控制文件"""
    events = {
        "exit_early": False,
        "rerecord_episode": False,
        "stop_recording": False,
    }

    def check_control_files():
        """检查控制文件并设置事件标志"""
        if SAVE_FLAG.exists():
            print("\n[文件控制] 收到保存指令")
            events["exit_early"] = True
            SAVE_FLAG.unlink()  # 删除标志文件

        if EXIT_FLAG.exists():
            print("\n[文件控制] 收到退出指令")
            events["stop_recording"] = True
            events["exit_early"] = True
            EXIT_FLAG.unlink()  # 删除标志文件

    # 创建一个定时检查线程
    import threading

    def monitor_thread():
        while not events.get("_stop_monitor", False):
            check_control_files()
            time.sleep(0.1)  # 每 100ms 检查一次

    monitor = threading.Thread(target=monitor_thread, daemon=True)
    monitor.start()

    return None, events  # 返回 None 作为 listener（兼容原接口）




class LowPassFilter1D:
    """一阶低通滤波器"""
    def __init__(self, cutoff_freq=3.0, sample_rate=20.0):
        self.fc = cutoff_freq
        self.fs = sample_rate
        self.dt = 1.0 / sample_rate
        rc = 1.0 / (2.0 * math.pi * self.fc)
        self.alpha = self.dt / (rc + self.dt)
        self.y = None

    def update(self, x):
        if self.y is None:
            self.y = x
            return self.y
        self.y = self.alpha * x + (1.0 - self.alpha) * self.y
        return self.y


class SafeTeleopProcessor(ProcessorStep):
    """安全遥操作处理器：零位对齐 + 低通滤波 + 软限位"""

    def __init__(self, fps=30):
        super().__init__()
        # 零位对齐
        self.initial_leader_pos = None
        self.initial_follower_pos = None
        self.zero_aligned = False
        self.zero_align_delay = 10
        self.cmd_count = 0

        # 低通滤波器
        self.lowpass_filters = [
            LowPassFilter1D(cutoff_freq=2.0, sample_rate=fps),
            LowPassFilter1D(cutoff_freq=3.0, sample_rate=fps),
            LowPassFilter1D(cutoff_freq=4.0, sample_rate=fps),
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=fps),
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=fps),
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=fps),
        ]

        # 软限位（ARX-X5 官方规格）
        self.joint_limits = [
            (-1.57, 1.57),   # joint_0: -90° to 90° (官方软件限位)
            (-0.10, 3.60),   # joint_1: -5.7° to 206.3° (官方软件限位，防止解算失效)
            (-0.09, 2.97),   # joint_2: -5° to 170°
            (-1.48, 1.48),   # joint_3: -85° to 85° (官方软件限位)
            (-1.40, 1.40),   # joint_4: -80° to 80°
            (-1.66, 1.66),   # joint_5: -95° to 95°
        ]

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        """处理环境转换，应用安全映射"""
        self._current_transition = transition

        # 从 transition 中提取 action 和 observation
        # transition 是一个字典
        action = transition["action"]
        observation = transition["observation"]
        scale = np.pi / 100.0

        # 提取主臂位置
        leader_positions = [
            action["joint_0.pos"],
            action["joint_1.pos"],
            action["joint_2.pos"],
            action["joint_3.pos"],
            action["joint_4.pos"],
            action["joint_5.pos"],
        ]

        # 零位对齐
        if not self.zero_aligned:
            if self.cmd_count >= self.zero_align_delay:
                self.initial_leader_pos = leader_positions.copy()
                # 从观测中获取从臂初始位置
                self.initial_follower_pos = [
                    observation["joint_0.pos"],
                    observation["joint_1.pos"],
                    observation["joint_2.pos"],
                    observation["joint_3.pos"],
                    observation["joint_4.pos"],
                    observation["joint_5.pos"],
                ]
                self.zero_aligned = True
                print(f"\n✓ 零位已记录")
                print(f"  主臂初始位置: {[f'{x:.2f}' for x in self.initial_leader_pos]}")
            else:
                self.cmd_count += 1
                # 还在等待，返回当前位置（不移动）
                if self.initial_follower_pos is not None:
                    new_action = RobotAction({
                        "joint_0.pos": self.initial_follower_pos[0],
                        "joint_1.pos": self.initial_follower_pos[1],
                        "joint_2.pos": self.initial_follower_pos[2],
                        "joint_3.pos": self.initial_follower_pos[3],
                        "joint_4.pos": self.initial_follower_pos[4],
                        "joint_5.pos": self.initial_follower_pos[5],
                        "gripper.pos": observation["gripper.pos"],
                    })
                    transition["action"] = new_action
                    return transition
                # 第一次调用，记录从臂初始位置
                self.initial_follower_pos = [
                    observation["joint_0.pos"],
                    observation["joint_1.pos"],
                    observation["joint_2.pos"],
                    observation["joint_3.pos"],
                    observation["joint_4.pos"],
                    observation["joint_5.pos"],
                ]
                self.cmd_count += 1
                new_action = RobotAction({
                    "joint_0.pos": observation["joint_0.pos"],
                    "joint_1.pos": observation["joint_1.pos"],
                    "joint_2.pos": observation["joint_2.pos"],
                    "joint_3.pos": observation["joint_3.pos"],
                    "joint_4.pos": observation["joint_4.pos"],
                    "joint_5.pos": observation["joint_5.pos"],
                    "gripper.pos": observation["gripper.pos"],
                })
                transition["action"] = new_action
                return transition

        # 相对位置
        relative_positions = [
            leader_positions[i] - self.initial_leader_pos[i]
            for i in range(6)
        ]

        # 转换为弧度，joint_0 和 joint_1 反向
        target_radians = [
            -relative_positions[0] * scale,  # joint_0 反向
            -relative_positions[1] * scale,  # joint_1 反向
            relative_positions[2] * scale,
            relative_positions[3] * scale,
            relative_positions[4] * scale,
            relative_positions[5] * scale,
        ]

        # 低通滤波
        filtered_radians = [
            self.lowpass_filters[i].update(target_radians[i])
            for i in range(6)
        ]

        # 加上初始位置并应用软限位
        final_positions = []
        for i in range(6):
            target = self.initial_follower_pos[i] + filtered_radians[i]
            lower, upper = self.joint_limits[i]
            clamped = max(lower, min(upper, target))

            # 警告：如果超出限位
            if abs(clamped - target) > 0.01 and self.cmd_count % 20 == 0:
                print(f"⚠️  关节{i}限位: {np.rad2deg(target):.1f}° -> {np.rad2deg(clamped):.1f}°")

            final_positions.append(clamped)

        self.cmd_count += 1

        # 夹爪映射
        gripper_value = action["gripper.pos"] * 10.0
        gripper_value = max(0, min(1000, gripper_value))

        new_action = RobotAction({
            "joint_0.pos": final_positions[0],
            "joint_1.pos": final_positions[1],
            "joint_2.pos": final_positions[2],
            "joint_3.pos": final_positions[3],
            "joint_4.pos": final_positions[4],
            "joint_5.pos": final_positions[5],
            "gripper.pos": gripper_value,
        })

        transition["action"] = new_action
        return transition

    def transform_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """描述此步骤如何转换特征（不改变特征）"""
        return features


# 录制配置
NUM_EPISODES = 10  # 最多录制 10 个 episodes（可用 e 键提前退出）
FPS = 30
EPISODE_TIME_SEC = 300  # 每个 episode 最长 5 分钟（可用 s/n 键提前结束）
RESET_TIME_SEC = 10
TASK_DESCRIPTION = "ARX-X5 safe teleoperation"
HF_REPO_ID = "lerobot/arx_safe_test"


def main():
    print("=" * 60)
    print("安全遥操作 + LeRobot 数据录制")
    print("=" * 60)
    print()

    # 配置相机（序列号已对换 wrist 和 front）
    camera_config = {
        "wrist": RealSenseCameraConfig(
            serial_number_or_name="347622073355",  # 原 front 序列号
            fps=FPS, width=640, height=480,
        ),
        "front": RealSenseCameraConfig(
            serial_number_or_name="346522074669",  # 原 wrist 序列号
            fps=FPS, width=640, height=480,
        ),
        "top": RealSenseCameraConfig(
            serial_number_or_name="406122070147",
            fps=FPS, width=640, height=480,
        ),
    }

    # 配置从臂
    follower_config = ARXFollowerConfig(
        can_port="can0",
        arx_type=0,
        cameras=camera_config,
    )

    # 配置主臂
    from pathlib import Path
    leader_config = FeetechLeaderConfig(
        port="/dev/ttyACM2",
        motor_ids=[1, 2, 3, 4, 5, 6],
        gripper_id=7,
        use_degrees=False,
        id="LeaderX5",  # 必须与标定文件名匹配 (LeaderX5.json)
        calibration_dir=Path("/home/dora/lerobot"),  # 标定文件所在目录
    )

    # 初始化机器人
    print("初始化机器人...")
    follower = ARXFollower(follower_config)
    leader = FeetechLeader(leader_config)

    # 创建安全处理器
    safe_processor = SafeTeleopProcessor(fps=FPS)

    # 创建处理器管道
    teleop_action_processor = RobotProcessorPipeline[
        tuple[RobotAction, RobotObservation], RobotAction
    ](
        steps=[safe_processor],
        to_transition=robot_action_observation_to_transition,
        to_output=transition_to_robot_action,
    )

    # 机器人处理器（直通）
    robot_action_processor = RobotProcessorPipeline[
        tuple[RobotAction, RobotObservation], RobotAction
    ](
        steps=[],
        to_transition=robot_action_observation_to_transition,
        to_output=transition_to_robot_action,
    )

    from lerobot.processor import make_default_processors
    _, _, robot_observation_processor = make_default_processors()

    # 创建数据集特征
    dataset_features = combine_feature_dicts(
        aggregate_pipeline_dataset_features(
            pipeline=teleop_action_processor,
            initial_features=create_initial_features(action=follower.action_features),
            use_videos=True,
        ),
        aggregate_pipeline_dataset_features(
            pipeline=robot_observation_processor,
            initial_features=create_initial_features(observation=follower.observation_features),
            use_videos=True,
        ),
    )

    # 创建数据集
    print(f"创建数据集: {HF_REPO_ID}")
    try:
        dataset = LeRobotDataset.create(
            HF_REPO_ID,
            FPS,
            root="./data",
            robot_type=follower.name,
            features=dataset_features,
            use_videos=True,
            image_writer_processes=4,
            image_writer_threads=len(camera_config) * 4,
            vcodec="h264",
        )
        print(f"✓ 数据集创建成功")
        print(f"  Dataset 对象: {dataset}")
        print(f"  Dataset 类型: {type(dataset)}")
    except Exception as e:
        print(f"✗ 数据集创建失败: {e}")
        import traceback
        traceback.print_exc()
        dataset = None

    # 初始化基于文件的控制监听器
    listener, events = init_file_based_listener()

    try:
        # 连接机器人
        print("连接机器人...")
        follower.connect(calibrate=False)
        leader.connect(calibrate=False)
        print("✓ 机器人已连接")
        print()
        print("⚠️  重要提示：")
        print("  启动后请保持主臂静止约0.5秒")
        print("  等待 '✓ 零位已记录' 提示后再移动主臂")
        print()
        print("📹 录制控制：")
        print("  在另一个终端运行: python3 record_control.py")
        print("  然后输入命令:")
        print("    s - 保存当前 episode")
        print("    e - 保存并退出")
        print()

        # 录制循环
        episode_idx = 0
        while episode_idx < NUM_EPISODES and not events["stop_recording"]:
            print(f"\n{'='*60}")
            print(f"开始录制 Episode {episode_idx}")
            print(f"{'='*60}\n")
            log_say(f"录制 episode {episode_idx + 1} / {NUM_EPISODES}")

            try:
                record_loop(
                    robot=follower,
                    events=events,
                    fps=FPS,
                    teleop=leader,
                    dataset=dataset,
                    control_time_s=EPISODE_TIME_SEC,
                    single_task=TASK_DESCRIPTION,
                    display_data=False,
                    teleop_action_processor=teleop_action_processor,
                    robot_action_processor=robot_action_processor,
                    robot_observation_processor=robot_observation_processor,
                )
            except Exception as e:
                print(f"\n✗ 录制出错: {e}")
                import traceback
                traceback.print_exc()
                break

            # 保存 episode
            print(f"\n{'='*60}")
            print(f"保存 Episode {episode_idx}")
            print(f"{'='*60}")

            if dataset is not None:
                try:
                    print(f"调用 dataset.save_episode()...")
                    dataset.save_episode()
                    print(f"✓ Episode {episode_idx} 已保存到数据集")
                    print(f"  当前总 episodes: {dataset.num_episodes}")
                    print(f"  当前总 frames: {dataset.num_frames}")
                except Exception as e:
                    print(f"✗ 保存失败: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"✗ dataset 为 None，无法保存")

            episode_idx += 1

            # 重置 exit_early 标志，准备下一个 episode
            events["exit_early"] = False

    finally:
        # 整合数据（将临时 PNG 转换为 MP4 和 Parquet）
        print("\n整合数据...")
        if dataset is not None:
            dataset.finalize()
            print("✓ 数据已整合")

        # 清理
        print("\n断开连接...")
        if follower:
            follower.disconnect()
        if leader:
            leader.disconnect()
        if listener:
            listener.stop()

        print("✓ 录制完成")
        print(f"数据保存位置: ./data/{HF_REPO_ID}")


if __name__ == "__main__":
    main()
