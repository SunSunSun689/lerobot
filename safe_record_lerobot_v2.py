#!/usr/bin/env python3
"""安全遥操作 + LeRobot 数据录制

在 LeRobot 框架内实现零位对齐、低通滤波和软限位保护

主要功能：
1. 零位对齐：首次启动时记录主臂和从臂的初始位置，建立相对映射关系
2. 低通滤波：对主臂指令进行滤波，减少高频抖动，保护机械臂
3. 软限位保护：限制关节运动范围，防止超出机械限位
4. 自动回位：每个 episode 结束后自动回到标准起始位置，实现连续录制

自动回位功能说明：
- 目标位置：动态学习 Episode 0 的实际起始位置（自动适应预定位差异）
- 回位时间：3 秒平滑过渡，避免机械臂运动过快
- 回位策略：使用线性插值生成平滑轨迹，防止 CAN 总线看门狗超时
- 数据记录：回位过程会被录入当前 episode 的数据中
- 连续性保证：确保所有 episode 从相同的起始位置开始，提高数据集质量

动态学习机制：
- Episode 0 开始录制时，自动记录从臂的实际位置
- 后续 episode 结束后，自动回位到这个记录的位置
- 无需手动更新代码中的固定值
- 自动适应每次运行时预定位的细微差异

使用方法：
1. 运行脚本后，保持主臂静止，等待预定位完成
2. 预定位完成后，自动记录 Episode 0 起始位置并开始录制
3. 录制完成后，机械臂自动回到 Episode 0 的起始位置
4. 在控制终端按 'n' 开始下一个 episode，或按 'e' 退出
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

# 每轮标准起始位置（弧度）：动态学习 Episode 0 的实际起始位置
# 这个初始值仅作为默认值，在 Episode 0 开始录制时会被实际位置覆盖
#
# 工作原理：
# 1. 预定位完成后，记录从臂的实际位置
# 2. Episode 0 开始录制时，将这个位置保存为标准起始位置
# 3. 后续 episode 结束后，自动回位到这个位置
# 4. 这样可以自动适应每次预定位的细微差异
#
# 注意：这个字典会在运行时被动态更新
EPISODE_START_POSITION = {
    "joint_0.pos": 1.5631,  # 默认值，会被 Episode 0 实际位置覆盖
    "joint_1.pos": 0.0017,
    "joint_2.pos": 0.0135,
    "joint_3.pos": -0.0109,
    "joint_4.pos": 0.0029,
    "joint_5.pos": 0.0044,
    "gripper.pos": 0.0,
}
RETURN_TIME_SEC = 5.0  # 回位过渡时间（秒），延长以降低运动速度，减少滤波器稳态误差
STABILIZE_TIME_SEC = 3.0  # 回位后稳定等待时间（秒），让低通滤波器完全收敛



def _return_to_start(
    follower,
    fps: int = 30,
    return_time: float = RETURN_TIME_SEC,
    dataset=None,
    robot_observation_processor=None,
    single_task: str = None,
) -> None:
    """
    渐进地将从臂移回标准起始位置，实现 episode 间的自动回位。

    功能说明：
    1. 读取当前机械臂位置
    2. 计算从当前位置到标准起始位置的轨迹
    3. 使用线性插值生成平滑的运动轨迹
    4. 逐步发送控制指令，避免突变导致看门狗超时
    5. 确保夹爪回到关闭状态
    6. 将回位过程的观测和动作记录到数据集

    参数：
        follower: ARXFollower 机械臂对象
        fps: 控制频率（Hz），默认 30
        return_time: 回位总时间（秒），默认 3.0
        dataset: LeRobotDataset 对象，用于记录回位过程数据
        robot_observation_processor: 观测处理器
        single_task: 任务描述

    目标位置：
        动态学习的 Episode 0 起始位置
        - 在 Episode 0 开始录制时自动记录
        - 自动适应每次预定位的细微差异
        - 无需手动更新代码中的固定值

    注意事项：
        - 回位过程会被录入当前 episode 的数据中
        - 回位时间不宜过短，避免机械臂运动过快
        - 使用线性插值保证运动平滑，防止 CAN 总线看门狗超时
    """
    print("\n🔙 从臂自动回位中...")
    print(f"   目标位置: joint_0={EPISODE_START_POSITION['joint_0.pos']:.4f} rad (89.56°)")
    print(f"   回位时间: {return_time:.1f} 秒")
    if dataset is not None:
        print(f"   📹 回位过程将被记录到数据集")

    steps = int(return_time * fps)  # 计算总步数

    try:
        # 获取当前位置
        obs = follower.get_observation()
        start = {k: obs[k] for k in EPISODE_START_POSITION}

        # 显示当前位置与目标位置的差异
        print(f"   当前位置: joint_0={start['joint_0.pos']:.4f} rad")
        max_diff = max(abs(start[k] - EPISODE_START_POSITION[k]) for k in EPISODE_START_POSITION)
        print(f"   最大差异: {max_diff:.4f} rad ({max_diff * 180 / 3.14159:.2f}°)")

        # 逐步插值移动到目标位置
        for i in range(steps):
            ratio = (i + 1) / steps  # 插值比例：0 → 1

            # 线性插值：current_pos + (target_pos - current_pos) * ratio
            action = RobotAction({
                k: start[k] + (EPISODE_START_POSITION[k] - start[k]) * ratio
                for k in EPISODE_START_POSITION
            })

            # 发送动作到机器人
            follower.send_action(action)

            # 如果提供了 dataset，记录回位过程的数据
            if dataset is not None and robot_observation_processor is not None:
                try:
                    # 获取当前观测
                    obs_raw = follower.get_observation()

                    # 处理观测
                    obs_processed = robot_observation_processor(obs_raw)

                    # 构建观测帧
                    from lerobot.datasets.utils import build_dataset_frame
                    from lerobot.utils.constants import OBS_STR, ACTION

                    observation_frame = build_dataset_frame(dataset.features, obs_processed, prefix=OBS_STR)

                    # 构建动作帧（使用发送的动作）
                    action_frame = build_dataset_frame(dataset.features, action, prefix=ACTION)

                    # 合并并添加到数据集
                    frame = {**observation_frame, **action_frame, "task": single_task}
                    dataset.add_frame(frame)
                except Exception as e:
                    # 只在第一次出错时打印，避免刷屏
                    if i == 0:
                        print(f"⚠️  记录回位数据失败: {e}")
                        import traceback
                        traceback.print_exc()

            time.sleep(1.0 / fps)

            # 每秒显示一次进度
            if (i + 1) % fps == 0:
                progress = (i + 1) / steps * 100
                print(f"   回位进度: {progress:.0f}%")

        # 验证最终位置
        final_obs = follower.get_observation()
        final_diff = abs(final_obs['joint_0.pos'] - EPISODE_START_POSITION['joint_0.pos'])

        if final_diff < 0.01:  # 差异小于 0.01 rad (约 0.57°)
            print("✅ 从臂已精确回到起始位置")
        else:
            print(f"⚠️  从臂已回位，但存在 {final_diff:.4f} rad ({final_diff * 180 / 3.14159:.2f}°) 的偏差")

        # 稳定等待：让低通滤波器完全收敛到目标位置
        # 在回位过程结束后，由于低通滤波器的延迟，机械臂可能还在继续向目标移动
        # 需要额外等待一段时间，持续发送目标位置指令，直到完全稳定
        stabilize_steps = int(STABILIZE_TIME_SEC * fps)
        if stabilize_steps > 0:
            print(f"\n⏳ 稳定等待 {STABILIZE_TIME_SEC:.1f} 秒，让机械臂完全收敛到目标位置...")

            for i in range(stabilize_steps):
                # 持续发送目标位置指令
                action = RobotAction(EPISODE_START_POSITION)
                follower.send_action(action)

                # 如果提供了 dataset，继续记录稳定过程
                if dataset is not None and robot_observation_processor is not None:
                    try:
                        obs_raw = follower.get_observation()
                        obs_processed = robot_observation_processor(obs_raw)

                        from lerobot.datasets.utils import build_dataset_frame
                        from lerobot.utils.constants import OBS_STR, ACTION

                        observation_frame = build_dataset_frame(dataset.features, obs_processed, prefix=OBS_STR)
                        action_frame = build_dataset_frame(dataset.features, action, prefix=ACTION)
                        frame = {**observation_frame, **action_frame, "task": single_task}
                        dataset.add_frame(frame)
                    except Exception:
                        pass  # 静默失败，避免刷屏

                time.sleep(1.0 / fps)

                # 每 0.5 秒显示一次进度
                if (i + 1) % (fps // 2) == 0:
                    progress = (i + 1) / stabilize_steps * 100
                    print(f"   稳定进度: {progress:.0f}%")

            # 验证稳定后的位置
            stable_obs = follower.get_observation()
            stable_diff = abs(stable_obs['joint_0.pos'] - EPISODE_START_POSITION['joint_0.pos'])

            print(f"\n✅ 稳定完成，最终偏差: {stable_diff:.4f} rad ({stable_diff * 180 / 3.14159:.2f}°)")

    except Exception as e:
        print(f"⚠️  回位出错: {e}")
        import traceback
        traceback.print_exc()



def _configure_cameras(serial_numbers: list[str]) -> None:
    """固定相机参数：自动白平衡，提高锐度和对比度。"""
    # top 相机对比度单独设置更高
    contrast_map = {"346522074669": 70}
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
            serial_number_or_name="336222072219",  # front 和 top 已对调
            fps=FPS,
            width=640,
            height=480,
        ),
        "top": RealSenseCameraConfig(
            serial_number_or_name="346522074669",  # front 和 top 已对调
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
        port="/dev/ttyACM0",
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
            "336222072219",  # front
            "346522074669",  # top
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
                    print("\n✅ 预定位完成，等待低通滤波器收敛...")
                    log_say("预定位完成，稳定中")
            except Exception as e:
                print(f"预定位出错: {e}")
                break
            import time
            time.sleep(1.0 / FPS)

        # 预定位完成后，等待低通滤波器完全收敛
        # 持续发送当前位置指令，让机械臂完全稳定
        if preposition_done and not events["stop_recording"]:
            stabilize_frames = int(2.0 * FPS)  # 等待 2 秒
            print(f"⏳ 稳定等待 2.0 秒，让低通滤波器完全收敛...")

            for i in range(stabilize_frames):
                try:
                    obs = follower.get_observation()
                    leader_obs = leader.get_observation()
                    action_raw = RobotAction({k: leader_obs[k] for k in leader_obs})
                    obs_raw = RobotObservation({k: obs[k] for k in obs})
                    transition = {"action": action_raw, "observation": obs_raw}
                    processed = safe_processor(transition)
                    follower.send_action(processed["action"])
                except Exception:
                    pass
                time.sleep(1.0 / FPS)

                # 每 0.5 秒显示一次进度
                if (i + 1) % (FPS // 2) == 0:
                    progress = (i + 1) / stabilize_frames * 100
                    print(f"   稳定进度: {progress:.0f}%")

            print("✅ 稳定完成，开始数据采集")
            log_say("开始录制")

        # 录制循环
        episode_idx = 0
        while episode_idx < NUM_EPISODES and not events["stop_recording"]:
            print(f"\n{'=' * 60}")
            print(f"开始录制 Episode {episode_idx}")
            print(f"  events 状态: exit_early={events['exit_early']} stop_recording={events['stop_recording']}")
            print(f"{'=' * 60}\n")
            log_say(f"录制 episode {episode_idx + 1} / {NUM_EPISODES}")

            # ============================================================
            # Episode 0 特殊处理：初始化回位目标
            # ============================================================
            # 在 Episode 0 开始前，先使用当前位置作为临时目标
            # 录制完成后会从数据集第一帧读取实际位置并更新
            if episode_idx == 0:
                print("\n📍 初始化 Episode 0 回位目标（录制后将从数据集更新）...")
                try:
                    # 读取当前从臂位置作为临时目标
                    obs = follower.get_observation()

                    # 临时设置起始位置
                    EPISODE_START_POSITION["joint_0.pos"] = obs["joint_0.pos"]
                    EPISODE_START_POSITION["joint_1.pos"] = obs["joint_1.pos"]
                    EPISODE_START_POSITION["joint_2.pos"] = obs["joint_2.pos"]
                    EPISODE_START_POSITION["joint_3.pos"] = obs["joint_3.pos"]
                    EPISODE_START_POSITION["joint_4.pos"] = obs["joint_4.pos"]
                    EPISODE_START_POSITION["joint_5.pos"] = obs["joint_5.pos"]
                    EPISODE_START_POSITION["gripper.pos"] = 0.0  # 夹爪始终设为关闭

                    print("✓ 临时回位目标已设置（录制完成后将更新为实际第一帧位置）")
                    print()
                except Exception as e:
                    print(f"⚠️  初始化回位目标失败: {e}")
                    print("   将使用默认回位位置")

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

            # ============================================================
            # Episode 结束后的自动回位处理
            # ============================================================
            # 目的：
            # 1. 确保下一个 episode 从相同的起始位置开始
            # 2. 实现 episode 间的连续性，减少人工干预
            # 3. 将夹爪复位到关闭状态
            #
            # 回位策略：
            # - 使用第一组数据的实际起始位置作为标准位置
            # - 通过线性插值生成平滑轨迹，避免机械臂突变
            # - 回位过程会被录入当前 episode 的数据中
            #
            # 注意：回位后需要保存 episode，这样下一个 episode
            # 开始时机械臂已经在正确的起始位置
            # ============================================================

            # ============================================================
            # Episode 0 特殊处理：从数据集读取第一帧位置
            # ============================================================
            # 在 Episode 0 录制完成后，从数据集缓存读取第一帧位置
            # 用于后续 episode 的回位目标
            if episode_idx == 0 and dataset is not None:
                print("\n📍 从 Episode 0 数据集读取第一帧位置...")
                try:
                    # dataset 内部维护了当前 episode 的帧缓存
                    # 尝试从缓存读取第一帧
                    if hasattr(dataset, '_current_episode') and len(dataset._current_episode) > 0:
                        first_frame = dataset._current_episode[0]

                        # 更新回位目标
                        EPISODE_START_POSITION["joint_0.pos"] = first_frame["observation.joint_0.pos"]
                        EPISODE_START_POSITION["joint_1.pos"] = first_frame["observation.joint_1.pos"]
                        EPISODE_START_POSITION["joint_2.pos"] = first_frame["observation.joint_2.pos"]
                        EPISODE_START_POSITION["joint_3.pos"] = first_frame["observation.joint_3.pos"]
                        EPISODE_START_POSITION["joint_4.pos"] = first_frame["observation.joint_4.pos"]
                        EPISODE_START_POSITION["joint_5.pos"] = first_frame["observation.joint_5.pos"]
                        EPISODE_START_POSITION["gripper.pos"] = 0.0

                        print("✓ Episode 0 第一帧位置已读取并设为回位目标:")
                        print(f"  joint_5: {EPISODE_START_POSITION['joint_5.pos']:.4f} rad ({EPISODE_START_POSITION['joint_5.pos'] * 180 / 3.14159:.2f}°)")
                        print()
                    else:
                        print("⚠️  无法访问 dataset 缓存，将使用临时目标")
                except Exception as e:
                    print(f"⚠️  读取第一帧失败: {e}")
                    print("   将使用临时目标")
                    import traceback
                    traceback.print_exc()

            print(f"\n{'=' * 60}")
            print(f"Episode {episode_idx} 录制完成 → 自动回位 → 保存数据")
            print(f"{'=' * 60}")

            # 自动回位到标准起始位置（3秒平滑过渡），并记录回位过程
            _return_to_start(
                follower,
                fps=FPS,
                dataset=dataset,
                robot_observation_processor=robot_observation_processor,
                single_task=TASK_DESCRIPTION,
            )

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

            # ============================================================
            # 等待开始下一个 episode
            # ============================================================
            # 此时机械臂已经回到标准起始位置，等待用户确认环境复位
            # （例如：重新摆放物品、调整场景等）
            #
            # 在等待期间：
            # - 持续发送起始位置指令，保持机械臂位置稳定
            # - 防止 ARX 看门狗超时导致控制断开
            # - 用户在控制终端按 'n' 开始下一组录制，或按 'e' 退出
            # ============================================================

            if episode_idx < NUM_EPISODES and not events["stop_recording"]:
                print(f"\n⏸  机械臂已回到起始位置，等待开始 Episode {episode_idx}")
                print(f"   请在控制终端输入命令：")
                print(f"     n - 开始录制下一组 (Episode {episode_idx})")
                print(f"     e - 保存并退出录制")
                print(f"\n   💡 提示：机械臂将保持在起始位置，可以调整场景后再开始")

                events["next_episode"] = False

                # 持续保持起始位置，防止 ARX 看门狗超时断开控制
                # 每 1/FPS 秒发送一次位置指令
                while not events["next_episode"] and not events["stop_recording"]:
                    try:
                        follower.send_action(RobotAction(EPISODE_START_POSITION))
                    except Exception:
                        pass
                    time.sleep(1 / FPS)

                events["next_episode"] = False
                print(f"\n▶️  开始录制 Episode {episode_idx}...")


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
