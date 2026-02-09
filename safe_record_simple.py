#!/usr/bin/env python3
"""安全遥操作 + 简化数据录制
使用安全遥操作（零位对齐）+ 直接保存数据（避免复杂依赖）
"""

import sys
import time
import csv
import math
from pathlib import Path
from datetime import datetime

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import cv2
import numpy as np
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig


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


class SafeRecordingSystem:
    """安全录制系统"""

    def __init__(self, output_dir, duration=20, fps=30):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.duration = duration
        self.fps = fps
        self.dt = 1.0 / fps

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

        self.last_sent_positions = None

        # 软限位（ARX-X5 机械限位）
        self.joint_limits = [
            (-2.44, 2.97),   # joint_0: -140° to 170°
            (-0.09, 3.49),   # joint_1: -5° to 200°
            (-0.09, 2.97),   # joint_2: -5° to 170°
            (-1.22, 1.22),   # joint_3: -70° to 70°
            (-1.40, 1.40),   # joint_4: -80° to 80°
            (-1.66, 1.66),   # joint_5: -95° to 95°
        ]

        # 配置
        self.leader_config = FeetechLeaderConfig(
            port="/dev/ttyACM2",
            motor_ids=[1, 2, 3, 4, 5, 6],
            gripper_id=7,
            use_degrees=False,
            id="feetech_leader_default",
        )

        self.follower_config = ARXFollowerConfig(
            can_port="can0",
            arx_type=0,
            cameras={
                "wrist": RealSenseCameraConfig(
                    serial_number_or_name="346522074669",
                    fps=fps, width=640, height=480,
                ),
                "front": RealSenseCameraConfig(
                    serial_number_or_name="347622073355",
                    fps=fps, width=640, height=480,
                ),
                "top": RealSenseCameraConfig(
                    serial_number_or_name="406122070147",
                    fps=fps, width=640, height=480,
                ),
            },
        )

        self.leader = None
        self.follower = None
        self.video_writers = {}
        self.csv_file = None
        self.csv_writer = None

    def map_leader_to_follower_safe(self, leader_obs):
        """安全映射：零位对齐 + 低通滤波"""
        scale = np.pi / 100.0

        leader_positions = [
            leader_obs["joint_0.pos"],
            leader_obs["joint_1.pos"],
            leader_obs["joint_2.pos"],
            leader_obs["joint_3.pos"],
            leader_obs["joint_4.pos"],
            leader_obs["joint_5.pos"],
        ]

        # 零位对齐
        if not self.zero_aligned:
            if self.cmd_count >= self.zero_align_delay:
                self.initial_leader_pos = leader_positions.copy()
                self.zero_aligned = True
                print(f"\n✓ 零位已记录")
                print(f"  主臂初始位置: {[f'{x:.2f}' for x in self.initial_leader_pos]}")
            else:
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

        # 相对位置
        relative_positions = [
            leader_positions[i] - self.initial_leader_pos[i]
            for i in range(6)
        ]

        # 转换为弧度，joint_1 反向
        target_radians = [
            relative_positions[0] * scale,
            -relative_positions[1] * scale,  # 反向
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

        self.last_sent_positions = filtered_radians.copy()

        # 加上初始位置并应用软限位
        final_positions = []
        for i in range(6):
            target = self.initial_follower_pos[f"joint_{i}.pos"] + filtered_radians[i]
            lower, upper = self.joint_limits[i]
            clamped = max(lower, min(upper, target))

            # 警告：如果超出限位
            if abs(clamped - target) > 0.01 and self.cmd_count % 20 == 0:
                print(f"⚠️  关节{i}限位: {np.rad2deg(target):.1f}° -> {np.rad2deg(clamped):.1f}°")

            final_positions.append(clamped)

        gripper_value = leader_obs["gripper.pos"] * 10.0
        gripper_value = max(0, min(1000, gripper_value))

        return {
            "joint_0.pos": final_positions[0],
            "joint_1.pos": final_positions[1],
            "joint_2.pos": final_positions[2],
            "joint_3.pos": final_positions[3],
            "joint_4.pos": final_positions[4],
            "joint_5.pos": final_positions[5],
            "gripper.pos": gripper_value,
        }

    def connect(self):
        """连接硬件"""
        print("连接硬件...")
        self.leader = FeetechLeader(self.leader_config)
        self.follower = ARXFollower(self.follower_config)

        self.leader.connect(calibrate=False)
        print("✓ 主臂已连接")

        self.follower.connect(calibrate=False)
        print("✓ 从臂已连接")
        print("✓ 3个相机已连接")

        # 记录从臂初始位置
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

        # 初始化视频写入器
        print("\n初始化视频写入器...")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        for cam_name in ["wrist", "front", "top"]:
            self.video_writers[cam_name] = cv2.VideoWriter(
                str(self.output_dir / f"{cam_name}.mp4"),
                fourcc, self.fps, (640, 480)
            )
        print("✓ 视频写入器已创建")

        # 初始化CSV
        self.csv_file = open(self.output_dir / "robot_states.csv", 'w', newline='')

    def disconnect(self):
        """断开连接"""
        print("\n断开连接...")

        # 关闭视频写入器
        for writer in self.video_writers.values():
            writer.release()

        # 关闭CSV
        if self.csv_file:
            self.csv_file.close()

        # 断开机器人
        if self.leader:
            self.leader.disconnect()
            print("✓ 主臂已断开")

        if self.follower:
            self.follower.disconnect()
            print("✓ 从臂已断开")

    def record(self):
        """录制数据"""
        print("\n" + "=" * 60)
        print(f"开始安全录制 - {self.duration}秒")
        print("=" * 60)
        print("⚠️  重要：启动后请保持主臂静止约0.5秒")
        print("等待 '✓ 零位已记录' 提示后再移动主臂")
        print("=" * 60)
        print()

        start_time = time.time()
        frame_count = 0

        try:
            while time.time() - start_time < self.duration:
                loop_start = time.time()

                # 读取主臂
                leader_obs = self.leader.get_observation()

                # 安全映射
                follower_action = self.map_leader_to_follower_safe(leader_obs)

                if follower_action is not None:
                    # 发送到从臂
                    self.follower.send_action(follower_action)

                    # 读取从臂观测
                    follower_obs = self.follower.get_observation()

                    # 保存相机图像
                    for cam_name in ["wrist", "front", "top"]:
                        if cam_name in follower_obs:
                            img = follower_obs[cam_name]
                            if img.shape[2] == 3:
                                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                            else:
                                img_bgr = img
                            self.video_writers[cam_name].write(img_bgr)

                    # 保存状态到CSV
                    elapsed = time.time() - start_time
                    row = {
                        "timestamp": elapsed,
                        "frame": frame_count,
                        "leader_j0": leader_obs["joint_0.pos"],
                        "leader_j1": leader_obs["joint_1.pos"],
                        "leader_j2": leader_obs["joint_2.pos"],
                        "leader_j3": leader_obs["joint_3.pos"],
                        "leader_j4": leader_obs["joint_4.pos"],
                        "leader_j5": leader_obs["joint_5.pos"],
                        "leader_gripper": leader_obs["gripper.pos"],
                        "follower_j0": follower_obs["joint_0.pos"],
                        "follower_j1": follower_obs["joint_1.pos"],
                        "follower_j2": follower_obs["joint_2.pos"],
                        "follower_j3": follower_obs["joint_3.pos"],
                        "follower_j4": follower_obs["joint_4.pos"],
                        "follower_j5": follower_obs["joint_5.pos"],
                        "follower_gripper": follower_obs["gripper.pos"],
                    }

                    if self.csv_writer is None:
                        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=row.keys())
                        self.csv_writer.writeheader()

                    self.csv_writer.writerow(row)
                    frame_count += 1

                    # 显示进度
                    if frame_count % 30 == 0:
                        print(f"录制中... {elapsed:.1f}s / {self.duration:.1f}s ({frame_count} 帧)")

                self.cmd_count += 1

                # 控制频率
                loop_time = time.time() - loop_start
                sleep_time = self.dt - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\n用户中断")

        finally:
            elapsed = time.time() - start_time
            actual_freq = frame_count / elapsed if elapsed > 0 else 0
            print(f"\n总帧数: {frame_count}")
            print(f"总时间: {elapsed:.1f}s")
            print(f"平均频率: {actual_freq:.1f} Hz")


def main():
    print("=" * 60)
    print("安全遥操作录制系统")
    print("=" * 60)
    print()

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"/home/dora/lerobot/recordings/safe_{timestamp}")

    print(f"输出目录: {output_dir}")
    print()

    # 创建录制系统
    system = SafeRecordingSystem(output_dir, duration=20, fps=30)

    try:
        # 连接
        system.connect()

        # 录制
        system.record()

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 断开
        system.disconnect()

    print("\n" + "=" * 60)
    print("录制完成！")
    print("=" * 60)
    print()
    print(f"数据保存位置: {output_dir}")
    print()
    print("文件列表:")
    print(f"  - wrist.mp4  (手腕相机)")
    print(f"  - front.mp4  (前置相机)")
    print(f"  - top.mp4    (顶部相机)")
    print(f"  - robot_states.csv (机器人状态)")
    print()


if __name__ == "__main__":
    main()
