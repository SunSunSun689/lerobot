#!/usr/bin/env python3
"""安全遥操作系统 - 基于DoRobot-vr的实现

核心安全机制：
1. 零位对齐 - 启动时记录初始位置，所有运动都是相对的
2. 低通滤波 - 平滑运动，避免突变
3. 死区过滤 - 减少小幅抖动
4. 软限位保护 - 防止超出机械范围
"""

import sys
import time
import math
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import numpy as np
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig


class LowPassFilter1D:
    """一阶低通滤波器，用于关节位置平滑"""
    def __init__(self, cutoff_freq=3.0, sample_rate=20.0):
        """
        cutoff_freq: 截止频率（Hz），越小越平滑但响应越慢
        sample_rate: 采样频率（Hz），默认20Hz
        """
        self.fc = cutoff_freq
        self.fs = sample_rate
        self.dt = 1.0 / sample_rate

        # 计算alpha系数
        rc = 1.0 / (2.0 * math.pi * self.fc)
        self.alpha = self.dt / (rc + self.dt)

        self.y = None  # 滤波器输出

    def update(self, x):
        """更新滤波器，返回滤波后的值"""
        if self.y is None:
            self.y = x
            return self.y

        # 一阶低通滤波公式
        self.y = self.alpha * x + (1.0 - self.alpha) * self.y
        return self.y


class SafeTeleoperationSystem:
    """安全的遥操作系统 - 基于DoRobot-vr实现"""

    def __init__(
        self,
        leader_port="/dev/ttyACM2",
        follower_can_port="can0",
        enable_cameras=False,
        control_frequency=20,
    ):
        self.control_frequency = control_frequency
        self.control_dt = 1.0 / control_frequency

        # 零位对齐
        self.initial_leader_pos = None
        self.initial_follower_pos = None
        self.zero_aligned = False
        self.zero_align_delay = 10  # 等待10帧后记录零位

        # 低通滤波器（每个关节独立）
        self.lowpass_filters = [
            LowPassFilter1D(cutoff_freq=2.0, sample_rate=control_frequency),  # joint_0 基座
            LowPassFilter1D(cutoff_freq=3.0, sample_rate=control_frequency),  # joint_1 肩部
            LowPassFilter1D(cutoff_freq=4.0, sample_rate=control_frequency),  # joint_2 肘部
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=control_frequency),  # joint_3 腕部
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=control_frequency),  # joint_4 腕部
            LowPassFilter1D(cutoff_freq=5.0, sample_rate=control_frequency),  # joint_5 腕部
        ]

        # 死区阈值（弧度）
        self.deadband_thresholds = [
            0.0,     # joint_0 基座 - 无死区
            0.017,   # joint_1 肩部 - 1度
            0.012,   # joint_2 肘部 - 0.7度
            0.026,   # joint_3 腕部 - 1.5度
            0.026,   # joint_4 腕部 - 1.5度
            0.026,   # joint_5 腕部 - 1.5度
        ]

        # 软限位（弧度）- ARX X5机械限位
        self.joint_limits = [
            (-2.44, 2.97),   # joint_0: -140° to 170°
            (-0.09, 3.49),   # joint_1: -5° to 200°
            (-0.09, 2.97),   # joint_2: -5° to 170°
            (-1.22, 1.22),   # joint_3: -70° to 70°
            (-1.40, 1.40),   # joint_4: -80° to 80°
            (-1.66, 1.66),   # joint_5: -95° to 95°
        ]

        # 上一次发送的位置（用于死区过滤）
        self.last_sent_positions = None

        # 配置主臂
        self.leader_config = FeetechLeaderConfig(
            port=leader_port,
            motor_ids=[1, 2, 3, 4, 5, 6],
            gripper_id=7,
            use_degrees=False,  # 使用 -100~100 范围
            id="feetech_leader_default",
        )

        # 配置从臂
        cameras = {}
        if enable_cameras:
            cameras = {
                "wrist": RealSenseCameraConfig(
                    serial_number_or_name="346522074669",
                    fps=30, width=640, height=480,
                ),
                "front": RealSenseCameraConfig(
                    serial_number_or_name="347622073355",
                    fps=30, width=640, height=480,
                ),
                "top": RealSenseCameraConfig(
                    serial_number_or_name="406122070147",
                    fps=30, width=640, height=480,
                ),
            }

        self.follower_config = ARXFollowerConfig(
            can_port=follower_can_port,
            arx_type=0,
            cameras=cameras,
        )

        self.leader = None
        self.follower = None
        self.cmd_count = 0

    def map_leader_to_follower(self, leader_obs):
        """将主臂观测映射到从臂动作（带完整安全机制）"""
        # 映射比例：-100~100 -> -π~π
        scale = np.pi / 100.0

        # 提取主臂关节位置
        leader_positions = [
            leader_obs["joint_0.pos"],
            leader_obs["joint_1.pos"],
            leader_obs["joint_2.pos"],
            leader_obs["joint_3.pos"],
            leader_obs["joint_4.pos"],
            leader_obs["joint_5.pos"],
        ]

        # 步骤1：零位对齐
        if not self.zero_aligned:
            if self.cmd_count >= self.zero_align_delay:
                # 记录零位
                self.initial_leader_pos = leader_positions.copy()
                self.zero_aligned = True
                print(f"\n✓ 零位已记录")
                print(f"  主臂初始位置: {[f'{x:.2f}' for x in self.initial_leader_pos]}")
            else:
                # 还在等待稳定，返回当前位置（不移动）
                if self.initial_follower_pos is not None:
                    return {
                        "joint_0.pos": self.initial_follower_pos["joint_0.pos"],
                        "joint_1.pos": self.initial_follower_pos["joint_1.pos"],
                        "joint_2.pos": self.initial_follower_pos["joint_2.pos"],
                        "joint_3.pos": self.initial_follower_pos["joint_3.pos"],
                        "joint_4.pos": self.initial_follower_pos["joint_4.pos"],
                        "joint_5.pos": self.initial_follower_pos["joint_5.pos"],
                        "gripper.pos": self.initial_follower_pos["gripper.pos"],
                    }
                return None

        # 应用零位偏移
        relative_positions = [
            leader_positions[i] - self.initial_leader_pos[i]
            for i in range(6)
        ]

        # 步骤2：转换为弧度
        # joint_1 方向反转
        target_radians = [
            relative_positions[0] * scale,      # joint_0: 正常
            -relative_positions[1] * scale,     # joint_1: 反向
            relative_positions[2] * scale,      # joint_2: 正常
            relative_positions[3] * scale,      # joint_3: 正常
            relative_positions[4] * scale,      # joint_4: 正常
            relative_positions[5] * scale,      # joint_5: 正常
        ]

        # 步骤3：低通滤波
        filtered_radians = [
            self.lowpass_filters[i].update(target_radians[i])
            for i in range(6)
        ]

        # 步骤4：死区过滤
        if self.last_sent_positions is not None:
            final_radians = []
            for i in range(6):
                delta = abs(filtered_radians[i] - self.last_sent_positions[i])
                if delta < self.deadband_thresholds[i]:
                    # 变化太小，使用上一次的值
                    final_radians.append(self.last_sent_positions[i])
                else:
                    # 变化足够大，使用新值
                    final_radians.append(filtered_radians[i])
        else:
            final_radians = filtered_radians

        # 步骤5：软限位保护
        clamped_radians = []
        for i in range(6):
            lower, upper = self.joint_limits[i]
            # 加上初始位置
            target = self.initial_follower_pos[f"joint_{i}.pos"] + final_radians[i]
            clamped = max(lower, min(upper, target))

            if abs(clamped - target) > 0.01:
                if self.cmd_count % 20 == 0:
                    print(f"⚠️  关节{i}限位: {np.rad2deg(target):.1f}° -> {np.rad2deg(clamped):.1f}°")

            clamped_radians.append(clamped)

        # 记录本次发送的相对位置
        self.last_sent_positions = final_radians.copy()

        # 夹爪映射：0~100 -> 0~1000
        gripper_value = leader_obs["gripper.pos"] * 10.0
        gripper_value = max(0, min(1000, gripper_value))

        return {
            "joint_0.pos": clamped_radians[0],
            "joint_1.pos": clamped_radians[1],
            "joint_2.pos": clamped_radians[2],
            "joint_3.pos": clamped_radians[3],
            "joint_4.pos": clamped_radians[4],
            "joint_5.pos": clamped_radians[5],
            "gripper.pos": gripper_value,
        }

    def connect(self):
        """连接主臂和从臂"""
        print("=" * 60)
        print("安全遥操作系统 - 基于DoRobot-vr")
        print("=" * 60)

        # 连接主臂
        print("\n正在连接主臂...")
        self.leader = FeetechLeader(self.leader_config)
        self.leader.connect(calibrate=False)
        print("✓ 主臂已连接")

        # 连接从臂
        print("\n正在连接从臂...")
        self.follower = ARXFollower(self.follower_config)
        self.follower.connect(calibrate=False)
        print("✓ 从臂已连接")

        # 读取从臂初始位置
        print("\n读取从臂初始位置...")
        follower_obs = self.follower.get_observation()
        self.initial_follower_pos = {
            "joint_0.pos": follower_obs["joint_0.pos"],
            "joint_1.pos": follower_obs["joint_1.pos"],
            "joint_2.pos": follower_obs["joint_2.pos"],
            "joint_3.pos": follower_obs["joint_3.pos"],
            "joint_4.pos": follower_obs["joint_4.pos"],
            "joint_5.pos": follower_obs["joint_5.pos"],
            "gripper.pos": follower_obs["gripper.pos"],
        }
        print(f"从臂初始位置: J0={np.rad2deg(self.initial_follower_pos['joint_0.pos']):.1f}°")

        print("\n✓ 系统已就绪")
        print(f"\n⏳ 等待{self.zero_align_delay}帧后开始零位对齐...")

    def disconnect(self):
        """断开连接"""
        print("\n\n正在断开连接...")
        if self.leader:
            self.leader.disconnect()
            print("✓ 主臂已断开")
        if self.follower:
            self.follower.disconnect()
            print("✓ 从臂已断开")

    def run(self, duration=None):
        """运行遥操作循环"""
        print("\n" + "=" * 60)
        print("开始安全遥操作")
        print("=" * 60)
        print("安全机制：")
        print("  ✓ 零位对齐 - 相对运动")
        print("  ✓ 低通滤波 - 平滑运动")
        print("  ✓ 死区过滤 - 减少抖动")
        print("  ✓ 软限位保护 - 防止超限")
        print(f"\n控制频率: {self.control_frequency} Hz")
        print("按 Ctrl+C 停止")
        print("=" * 60)

        start_time = time.time()
        last_display_time = start_time

        try:
            while True:
                loop_start = time.time()

                # 读取主臂位置
                leader_obs = self.leader.get_observation()

                # 映射到从臂动作（带安全机制）
                follower_action = self.map_leader_to_follower(leader_obs)

                if follower_action is not None:
                    # 发送到从臂
                    self.follower.send_action(follower_action)

                self.cmd_count += 1

                # 每秒显示一次
                if time.time() - last_display_time >= 1.0:
                    elapsed = time.time() - start_time
                    freq = self.cmd_count / elapsed if elapsed > 0 else 0

                    if self.zero_aligned and follower_action:
                        rel_pos = follower_action["joint_0.pos"] - self.initial_follower_pos["joint_0.pos"]
                        print(f"\n时间: {elapsed:.1f}s | 频率: {freq:.1f} Hz | 命令: {self.cmd_count}")
                        print(f"主臂 J0: {leader_obs['joint_0.pos']:6.2f} | "
                              f"从臂相对: {np.rad2deg(rel_pos):6.1f}° | "
                              f"从臂绝对: {np.rad2deg(follower_action['joint_0.pos']):6.1f}°")
                    else:
                        print(f"\n⏳ 等待零位对齐... ({self.cmd_count}/{self.zero_align_delay})")

                    last_display_time = time.time()

                # 检查运行时长
                if duration and (time.time() - start_time >= duration):
                    print(f"\n达到运行时长 {duration} 秒")
                    break

                # 控制循环频率
                loop_time = time.time() - loop_start
                sleep_time = self.control_dt - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\n用户中断")

        finally:
            elapsed = time.time() - start_time
            freq = self.cmd_count / elapsed if elapsed > 0 else 0
            print(f"\n总命令: {self.cmd_count}")
            print(f"总时间: {elapsed:.1f}s")
            print(f"平均频率: {freq:.1f} Hz")


def main():
    print("\n安全遥操作系统 v2.0")
    print("基于 DoRobot-vr 实现")
    print("=" * 60)

    # 创建系统
    system = SafeTeleoperationSystem(
        leader_port="/dev/ttyACM2",
        follower_can_port="can0",
        enable_cameras=False,  # 默认禁用相机以提高性能
        control_frequency=20,
    )

    try:
        # 连接
        system.connect()

        # 运行
        system.run(duration=None)

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 断开
        system.disconnect()

    print("\n" + "=" * 60)
    print("遥操作结束")
    print("=" * 60)


if __name__ == "__main__":
    main()
