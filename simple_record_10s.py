#!/usr/bin/env python3
"""简化的录制测试 - 直接保存MP4和CSV"""

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import cv2

from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig

print("=" * 60)
print("完整录制测试 - 20秒")
print("=" * 60)
print()

# 创建输出目录
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_dir = Path(f"/home/dora/lerobot/recordings/test_{timestamp}")
output_dir.mkdir(parents=True, exist_ok=True)
print(f"输出目录: {output_dir}")
print()

# 配置主臂
print("配置主臂...")
leader_config = FeetechLeaderConfig(
    port="/dev/ttyACM2",
    motor_ids=[1, 2, 3, 4, 5, 6],
    gripper_id=7,
    use_degrees=False,
    id="feetech_leader_default",
)

# 配置从臂 + 3个相机
print("配置从臂和相机...")
follower_config = ARXFollowerConfig(
    can_port="can0",
    arx_type=0,
    cameras={
        "wrist": RealSenseCameraConfig(
            serial_number_or_name="346522074669",
            fps=30,
            width=640,
            height=480,
        ),
        "front": RealSenseCameraConfig(
            serial_number_or_name="347622073355",
            fps=30,
            width=640,
            height=480,
        ),
        "top": RealSenseCameraConfig(
            serial_number_or_name="406122070147",
            fps=30,
            width=640,
            height=480,
        ),
    },
)

# 连接硬件
print("连接硬件...")
leader = FeetechLeader(leader_config)
follower = ARXFollower(follower_config)

leader.connect(calibrate=False)
print("✓ 主臂已连接")

follower.connect(calibrate=False)
print("✓ 从臂已连接")
print("✓ 3个相机已连接")
print()

# 创建视频写入器
print("初始化视频写入器...")
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
fps = 30
video_writers = {
    "wrist": cv2.VideoWriter(str(output_dir / "wrist.mp4"), fourcc, fps, (640, 480)),
    "front": cv2.VideoWriter(str(output_dir / "front.mp4"), fourcc, fps, (640, 480)),
    "top": cv2.VideoWriter(str(output_dir / "top.mp4"), fourcc, fps, (640, 480)),
}
print("✓ 视频写入器已创建")
print()

# 创建CSV文件
csv_file = output_dir / "robot_states.csv"
csv_writer = None
csv_handle = open(csv_file, "w", newline="")

print("=" * 60)
print("开始录制 - 20秒")
print("=" * 60)
print("请移动主臂进行遥操作...")
print()

start_time = time.time()
frame_count = 0
dt = 1.0 / fps
duration = 20.0  # 录制20秒

try:
    while time.time() - start_time < duration:
        loop_start = time.time()

        # 读取主臂（动作）
        leader_obs = leader.get_observation()

        # 读取从臂（观测，包含相机）
        follower_obs = follower.get_observation()

        # 保存相机图像到视频
        for camera_name in ["wrist", "front", "top"]:
            # 相机图像直接用相机名称作为键
            if camera_name in follower_obs:
                img = follower_obs[camera_name]
                # 转换为BGR（OpenCV格式）
                if img.shape[2] == 3:  # RGB
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                else:
                    img_bgr = img
                video_writers[camera_name].write(img_bgr)

        # 保存状态数据到CSV
        elapsed = time.time() - start_time
        row = {
            "timestamp": elapsed,
            "frame": frame_count,
            # 主臂位置（动作）
            "leader_j0": leader_obs["joint_0.pos"],
            "leader_j1": leader_obs["joint_1.pos"],
            "leader_j2": leader_obs["joint_2.pos"],
            "leader_j3": leader_obs["joint_3.pos"],
            "leader_j4": leader_obs["joint_4.pos"],
            "leader_j5": leader_obs["joint_5.pos"],
            "leader_gripper": leader_obs["gripper.pos"],
            # 从臂位置（观测）
            "follower_j0": follower_obs["joint_0.pos"],
            "follower_j1": follower_obs["joint_1.pos"],
            "follower_j2": follower_obs["joint_2.pos"],
            "follower_j3": follower_obs["joint_3.pos"],
            "follower_j4": follower_obs["joint_4.pos"],
            "follower_j5": follower_obs["joint_5.pos"],
            "follower_gripper": follower_obs["gripper.pos"],
        }

        if csv_writer is None:
            csv_writer = csv.DictWriter(csv_handle, fieldnames=row.keys())
            csv_writer.writeheader()

        csv_writer.writerow(row)
        frame_count += 1

        # 显示进度
        if frame_count % 30 == 0:
            print(f"录制中... {elapsed:.1f}s / {duration:.1f}s ({frame_count} 帧)")

        # 控制帧率
        loop_time = time.time() - loop_start
        sleep_time = dt - loop_time
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    print("\n用户中断")
except Exception as e:
    print(f"\n错误: {e}")
    import traceback

    traceback.print_exc()

finally:
    # 关闭所有写入器
    print()
    print("关闭文件...")
    for name, writer in video_writers.items():
        writer.release()
    csv_handle.close()

    # 断开硬件
    print("断开硬件...")
    leader.disconnect()
    follower.disconnect()

print()
print("=" * 60)
print("录制完成！")
print("=" * 60)
print()
print(f"数据保存位置: {output_dir}")
print(f"总帧数: {frame_count}")
print()
print("文件列表:")
print("  - wrist.mp4  (手腕相机)")
print("  - front.mp4  (前置相机)")
print("  - top.mp4    (顶部相机)")
print("  - robot_states.csv (机器人状态)")
print()
print("查看视频:")
print(f"  vlc {output_dir}/wrist.mp4")
print()
print("分析视频帧率:")
print(
    f"  ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 {output_dir}/wrist.mp4"
)
print()
