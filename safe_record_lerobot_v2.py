#!/usr/bin/env python3
"""安全遥操作 + LeRobot 数据录制
在 LeRobot 框架内实现零位对齐、低通滤波和软限位保护
"""

import math
import sys
import time
from pathlib import Path
from typing import Any
import pyrealsense2 as rs

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 控制文件路径
CONTROL_DIR = Path("/tmp/lerobot_control")
CONTROL_DIR.mkdir(exist_ok=True)
SAVE_FLAG = CONTROL_DIR / "save_episode"
NEXT_FLAG = CONTROL_DIR / "next_episode"
EXIT_FLAG = CONTROL_DIR / "exit_recording"

# 清理旧的控制文件
SAVE_FLAG.unlink(missing_ok=True)
NEXT_FLAG.unlink(missing_ok=True)
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
from lerobot.processor.pipeline import EnvTransition, ProcessorStep
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
        "next_episode": False,
    }

    def check_control_files():
        """检查控制文件并设置事件标志"""
        if SAVE_FLAG.exists():
            print("\n[文件控制] 收到保存指令")
            events["exit_early"] = True
            SAVE_FLAG.unlink()  # 删除标志文件

        if NEXT_FLAG.exists():
            print("\n[文件控制] 收到开始下一组指令")
            events["next_episode"] = True
            NEXT_FLAG.unlink()  # 删除标志文件

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

    def __init__(self, fps=30, follower_offset=None, transition_time=3.0):
        super().__init__()
        # 零位对齐
        self.initial_leader_pos = None
        self.initial_follower_pos = None
        self.zero_aligned = False
        self.zero_align_delay = 10
        self.cmd_count = 0

        # 从臂初始位置偏移（弧度）
        # 例如：[0, 0, 0, 0, 0, 0] 表示无偏移
        # [π/2, 0, 0, -1.379, 0, 0] 表示 Joint0 +90°, Joint3 -79°
        self.follower_offset = follower_offset if follower_offset is not None else [0, 0, 0, 0, 0, 0]

        # 渐进式偏移参数
        self.transition_time = transition_time  # 过渡时间（秒）
        self.transition_steps = int(transition_time * fps)  # 过渡步数
        self.transition_counter = 0  # 当前过渡步数
        self.in_transition = False  # 是否在过渡期
        self.current_offset_ratio = 0.0  # 当前偏移比例（0.0 到 1.0）

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
            (-2.53, 3.05),  # joint_0: -145° to 175° (机械限位 -150° to 180°，留安全余量)
            (-0.10, 3.60),  # joint_1: -5.7° to 206.3° (官方软件限位，防止解算失效)
            (-0.09, 2.97),  # joint_2: -5° to 170°
            (-2.97, 2.97),  # joint_3: -170° to 170° (扩大范围以支持 1:2 映射)
            (-1.29, 1.29),  # joint_4: -74° to 74° (软件限位，机械限位 ±90°)
            (-1.66, 1.66),  # joint_5: -95° to 95°
        ]

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        """处理环境转换，应用安全映射"""
        self._current_transition = transition

        # 从 transition 中提取 action 和 observation
        # transition 是一个字典
        action = transition["action"]
        observation = transition["observation"]
        # 主臂归一化值 -100~100 对应 180° 物理角度
        # 使用 π/2 使其他关节保持 1:1，joint3 通过 2x 实现 1:2
        scale = (np.pi / 2) / 100.0  # -100~100 → -90°~90° (180° 物理范围)

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
                # 从观测中获取从臂初始位置（不立即应用偏移）
                self.initial_follower_pos_raw = [
                    observation["joint_0.pos"],
                    observation["joint_1.pos"],
                    observation["joint_2.pos"],
                    observation["joint_3.pos"],
                    observation["joint_4.pos"],
                    observation["joint_5.pos"],
                ]
                # 目标偏移位置
                self.initial_follower_pos = [
                    observation["joint_0.pos"] + self.follower_offset[0],
                    observation["joint_1.pos"] + self.follower_offset[1],
                    observation["joint_2.pos"] + self.follower_offset[2],
                    observation["joint_3.pos"] + self.follower_offset[3],
                    observation["joint_4.pos"] + self.follower_offset[4],
                    observation["joint_5.pos"] + self.follower_offset[5],
                ]
                self.zero_aligned = True
                self.in_transition = any(abs(offset) > 0.01 for offset in self.follower_offset)
                print("\n✓ 零位已记录")
                print(f"  主臂初始位置 (归一化): {[f'{x:.2f}' for x in self.initial_leader_pos]}")
                print(f"  主臂初始角度: {[f'{x * (180 / 200):.1f}°' for x in self.initial_leader_pos]}")
                print(f"  从臂当前位置 (弧度): {[f'{x:.3f}' for x in self.initial_follower_pos_raw]}")
                print(f"  从臂当前角度: {[f'{np.rad2deg(x):.1f}°' for x in self.initial_follower_pos_raw]}")
                print(f"  从臂目标偏移: {[f'{np.rad2deg(x):.1f}°' for x in self.follower_offset]}")
                if self.in_transition:
                    print(f"  🔄 将在 {self.transition_time:.1f} 秒内渐进移动到偏移位置")
                print("  ⚠️  Joint3 使用 1:2 映射（主臂 90° → 从臂 180°）")
            else:
                self.cmd_count += 1
                # 还在等待，返回当前位置（不移动）
                if self.initial_follower_pos is not None:
                    new_action = RobotAction(
                        {
                            "joint_0.pos": self.initial_follower_pos[0],
                            "joint_1.pos": self.initial_follower_pos[1],
                            "joint_2.pos": self.initial_follower_pos[2],
                            "joint_3.pos": self.initial_follower_pos[3],
                            "joint_4.pos": self.initial_follower_pos[4],
                            "joint_5.pos": self.initial_follower_pos[5],
                            "gripper.pos": observation["gripper.pos"],
                        }
                    )
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
                new_action = RobotAction(
                    {
                        "joint_0.pos": observation["joint_0.pos"],
                        "joint_1.pos": observation["joint_1.pos"],
                        "joint_2.pos": observation["joint_2.pos"],
                        "joint_3.pos": observation["joint_3.pos"],
                        "joint_4.pos": observation["joint_4.pos"],
                        "joint_5.pos": observation["joint_5.pos"],
                        "gripper.pos": observation["gripper.pos"],
                    }
                )
                transition["action"] = new_action
                return transition

        # 相对位置
        relative_positions = [leader_positions[i] - self.initial_leader_pos[i] for i in range(6)]

        # 转换为弧度，joint_0 和 joint_1 反向
        target_radians = [
            -relative_positions[0] * scale,  # joint_0 反向
            -relative_positions[1] * scale,  # joint_1 反向
            relative_positions[2] * scale,
            relative_positions[3] * scale * 2.0,  # joint_3: 1:2 映射（主臂 90° → 从臂 180°）
            relative_positions[4] * scale,
            relative_positions[5] * scale,
        ]

        # 调试输出（每 100 次输出一次 joint3 的映射）
        if self.cmd_count % 100 == 0 and abs(relative_positions[3]) > 1:
            leader_angle = relative_positions[3] * (180 / 200)  # 主臂实际物理角度
            follower_angle = np.rad2deg(target_radians[3])  # 从臂目标角度
            ratio = follower_angle / leader_angle if leader_angle != 0 else 0
            print(
                f"[Joint3] 主臂: {relative_positions[3]:.1f}单位({leader_angle:.1f}°) → 从臂: {follower_angle:.1f}° (比例:{ratio:.2f}x)"
            )

        # 低通滤波
        filtered_radians = [self.lowpass_filters[i].update(target_radians[i]) for i in range(6)]

        # 渐进式偏移处理
        if self.in_transition:
            self.transition_counter += 1
            self.current_offset_ratio = min(1.0, self.transition_counter / self.transition_steps)

            # 每30帧显示一次进度
            if self.transition_counter % 30 == 0:
                progress = self.current_offset_ratio * 100
                print(f"🔄 偏移进度: {progress:.0f}% ({self.transition_counter}/{self.transition_steps})")

            # 完成过渡
            if self.current_offset_ratio >= 1.0:
                self.in_transition = False
                print("✓ 偏移完成，开始正常遥操作")
        else:
            self.current_offset_ratio = 1.0

        # 加上初始位置并应用软限位
        final_positions = []
        for i in range(6):
            # 使用渐进式偏移
            current_initial_pos = (
                self.initial_follower_pos_raw[i] * (1 - self.current_offset_ratio)
                + self.initial_follower_pos[i] * self.current_offset_ratio
            )
            target = current_initial_pos + filtered_radians[i]
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

        new_action = RobotAction(
            {
                "joint_0.pos": final_positions[0],
                "joint_1.pos": final_positions[1],
                "joint_2.pos": final_positions[2],
                "joint_3.pos": final_positions[3],
                "joint_4.pos": final_positions[4],
                "joint_5.pos": final_positions[5],
                "gripper.pos": gripper_value,
            }
        )

        transition["action"] = new_action
        return transition

    def transform_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """描述此步骤如何转换特征（不改变特征）"""
        return features

    def reset_for_new_episode(self):
        """新 episode 开始前重置零位对齐状态（不重新应用偏移，从当前位置继续）"""
        self.zero_aligned = False
        self.initial_leader_pos = None
        self.initial_follower_pos = None
        self.cmd_count = 0
        self.in_transition = False
        self.current_offset_ratio = 0.0
        self.transition_counter = 0
        # 清零偏移：臂已在工作位置，无需再次移动
        self.follower_offset = [0.0] * 6
        # 重置低通滤波器
        for f in self.lowpass_filters:
            f.y = None
        print("✓ 零位对齐已重置（从当前位置继续，无偏移）")


# 录制配置
NUM_EPISODES = 10  # 最多录制 10 个 episodes（可用 e 键提前退出）
FPS = 30
EPISODE_TIME_SEC = 300  # 每个 episode 最长 5 分钟（可用 s/n 键提前结束）
RESET_TIME_SEC = 10
TASK_DESCRIPTION = "ARX-X5 safe teleoperation"
HF_REPO_ID = "lerobot/arx_safe_test"

# 从臂初始位置偏移（弧度）
# 格式：[joint_0, joint_1, joint_2, joint_3, joint_4, joint_5]
# 例如：底座旋转 +90 度 = [π/2, 0, 0, 0, 0, 0]
# Joint3 中心点对应偏移（主臂 -43.9° 对应从臂中心）

FOLLOWER_OFFSET = [math.pi / 2, 0, 0, 0, 0, 0]  # Joint0 +90°, Joint3 中间值（物理零位）, Joint5 动态计算

# 每轮标准起始位置（弧度）：预定位完成后的目标姿态
EPISODE_START_POSITION = {
    "joint_0.pos": math.pi / 2,  # 90°
    "joint_1.pos": 0.0,
    "joint_2.pos": 0.0,
    "joint_3.pos": 0.0,
    "joint_4.pos": 0.0,
    "joint_5.pos": 0.0,
    "gripper.pos": 0.0,
}
RETURN_TIME_SEC = 3.0  # 回位过渡时间（秒）


def _return_to_start(follower, fps: int = 30, return_time: float = RETURN_TIME_SEC) -> None:
    """渐进地将从臂移回标准起始位置，防止看门狗断线。"""
    print("\n🔙 从臂回位中...")
    steps = int(return_time * fps)
    try:
        obs = follower.get_observation()
        start = {k: obs[k] for k in EPISODE_START_POSITION}
        for i in range(steps):
            ratio = (i + 1) / steps
            action = RobotAction({
                k: start[k] + (EPISODE_START_POSITION[k] - start[k]) * ratio
                for k in EPISODE_START_POSITION
            })
            follower.send_action(action)
            time.sleep(1.0 / fps)
        print("✅ 从臂已回到起始位置")
    except Exception as e:
        print(f"⚠️  回位出错: {e}")


def _configure_cameras(serial_numbers: list[str]) -> None:
    """固定相机参数：自动白平衡，提高锐度和对比度。"""
    # top 相机对比度单独设置更高
    contrast_map = {"406122070147": 70}
    ctx = rs.context()
    devices = {d.get_info(rs.camera_info.serial_number): d for d in ctx.query_devices()}
    for sn in serial_numbers:
        dev = devices.get(sn)
        if dev is None:
            print(f"⚠ 相机 {sn} 未找到，跳过参数设置")
            continue
        for sensor in dev.query_sensors():
            name = sensor.get_info(rs.camera_info.name)
            if "RGB" not in name and "Color" not in name.lower():
                continue
            try:
                contrast = contrast_map.get(sn, 60)
                sensor.set_option(rs.option.enable_auto_white_balance, 1)
                sensor.set_option(rs.option.sharpness, 75)
                sensor.set_option(rs.option.contrast, contrast)
                print(f"✓ 相机 {sn} 参数已固定（自动白平衡 锐度=75 对比度={contrast}）")
            except Exception as e:
                print(f"⚠ 相机 {sn} 参数设置失败: {e}")


def main():
    print("=" * 60)
    print("安全遥操作 + LeRobot 数据录制")
    print("=" * 60)
    print()

    # 配置相机（序列号已对换 wrist 和 front）
    camera_config = {
        "wrist": RealSenseCameraConfig(
            serial_number_or_name="347622073355",  # 原 front 序列号
            fps=FPS,
            width=640,
            height=480,
        ),
        "front": RealSenseCameraConfig(
            serial_number_or_name="346522074669",  # 原 wrist 序列号
            fps=FPS,
            width=640,
            height=480,
        ),
        "top": RealSenseCameraConfig(
            serial_number_or_name="406122070147",
            fps=FPS,
            width=640,
            height=480,
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
        port="/dev/ttyACM3",
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
    safe_processor = SafeTeleopProcessor(fps=FPS, follower_offset=FOLLOWER_OFFSET)

    # 创建处理器管道
    teleop_action_processor = RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction](
        steps=[safe_processor],
        to_transition=robot_action_observation_to_transition,
        to_output=transition_to_robot_action,
    )

    # 机器人处理器（直通）
    robot_action_processor = RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction](
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
            crf=18,
        )
        print("✓ 数据集创建成功")
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

        # 固定相机参数，避免自动白平衡/曝光导致画面偏色和对比度不稳定
        _configure_cameras([
            "347622073355",  # wrist
            "346522074669",  # front
            "406122070147",  # top
        ])

        print("✓ 机器人已连接")

        # 动态计算 joint_5 补偿：读取上电后实际位置，计算到 0° 所需偏移
        import time as _time
        _time.sleep(0.3)  # 等待传感器稳定
        _obs = follower.get_observation()
        joint5_actual = _obs["joint_5.pos"]
        FOLLOWER_OFFSET[5] = -joint5_actual  # 补偿到 0°
        print(f"  joint_5 上电位置: {math.degrees(joint5_actual):.1f}°，补偿偏移: {math.degrees(FOLLOWER_OFFSET[5]):.1f}°")
        # 同步更新 safe_processor 的偏移
        safe_processor.follower_offset = FOLLOWER_OFFSET[:]

        print()
        print("⚠️  重要提示：")
        print("  启动后请保持主臂静止，等待从臂完成预定位")
        print("  预定位完成后自动开始录制第一组数据")
        print()
        print("📹 录制控制：")
        print("  在另一个终端运行: python3 record_control.py")
        print("  然后输入命令:")
        print("    s - 保存当前 episode")
        print("    e - 保存并退出")
        print()

        # 预定位阶段：驱动从臂完成过渡（零位对齐 + 偏移过渡），过渡完成后自动开始录制
        print("\n🔄 预定位阶段：等待从臂完成过渡...")
        print("  请保持主臂静止，等待 '✓ 偏移完成' 提示")
        preposition_done = False
        while not preposition_done and not events["stop_recording"]:
            try:
                obs = follower.get_observation()
                leader_obs = leader.get_observation()
                action_raw = RobotAction({k: leader_obs[k] for k in leader_obs})
                obs_raw = RobotObservation({k: obs[k] for k in obs})
                transition = {"action": action_raw, "observation": obs_raw}
                processed = safe_processor(transition)
                follower.send_action(processed["action"])
                if safe_processor.zero_aligned and not safe_processor.in_transition:
                    preposition_done = True
                    print("\n✅ 预定位完成，自动开始数据采集")
                    log_say("预定位完成，开始录制")
            except Exception as e:
                print(f"预定位出错: {e}")
                break
            import time
            time.sleep(1.0 / FPS)

        # 录制循环
        episode_idx = 0
        while episode_idx < NUM_EPISODES and not events["stop_recording"]:
            print(f"\n{'=' * 60}")
            print(f"开始录制 Episode {episode_idx}")
            print(f"  events 状态: exit_early={events['exit_early']} stop_recording={events['stop_recording']}")
            print(f"{'=' * 60}\n")
            log_say(f"录制 episode {episode_idx + 1} / {NUM_EPISODES}")
            # 确保进入 record_loop 前 exit_early 为 False
            events["exit_early"] = False
            # 第二轮起重置零位对齐，从当前位置继续（不重新应用偏移）
            if episode_idx > 0:
                safe_processor.reset_for_new_episode()

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
            print(f"\n{'=' * 60}")
            print(f"保存 Episode {episode_idx}")
            print(f"{'=' * 60}")

            if dataset is not None:
                try:
                    print("调用 dataset.save_episode()...")
                    dataset.save_episode()
                    print(f"✓ Episode {episode_idx} 已保存到数据集")
                    print(f"  当前总 episodes: {dataset.num_episodes}")
                    print(f"  当前总 frames: {dataset.num_frames}")
                except Exception as e:
                    print(f"✗ 保存失败: {e}")
                    import traceback

                    traceback.print_exc()
            else:
                print("✗ dataset 为 None，无法保存")

            episode_idx += 1

            # 重置 exit_early 标志，准备下一个 episode
            events["exit_early"] = False

            # 等待环境复位确认，再开始下一组
            if episode_idx < NUM_EPISODES and not events["stop_recording"]:
                # 自动回到起始位置
                _return_to_start(follower, fps=FPS)
                print(f"\n⏸  环境复位后在控制终端按 n 开始下一组录制（Episode {episode_idx}）")
                print("   或按 e 退出录制")
                events["next_episode"] = False
                # 持续保持起始位置，防止 ARX 看门狗超时断开控制
                while not events["next_episode"] and not events["stop_recording"]:
                    try:
                        follower.send_action(RobotAction(EPISODE_START_POSITION))
                    except Exception:
                        pass
                    time.sleep(1 / FPS)
                events["next_episode"] = False

    finally:
        # 退出前回到起始位置
        if follower:
            _return_to_start(follower, fps=FPS)

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
