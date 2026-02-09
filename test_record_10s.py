#!/usr/bin/env python3
"""简化的录制测试脚本 - 10秒测试"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
from lerobot.datasets.lerobot_dataset import LeRobotDataset

print("=" * 60)
print("LeRobot 10秒录制测试")
print("=" * 60)
print()

# 配置主臂
leader_config = FeetechLeaderConfig(
    port="/dev/ttyACM2",
    motor_ids=[1, 2, 3, 4, 5, 6],
    gripper_id=7,
    use_degrees=False,
    id="feetech_leader_default",
)

# 配置从臂 + 3个相机
follower_config = ARXFollowerConfig(
    can_port="can0",
    arx_type=0,
    cameras={
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
    },
)

print("连接硬件...")
leader = FeetechLeader(leader_config)
follower = ARXFollower(follower_config)

leader.connect(calibrate=False)
print("✓ 主臂已连接")

follower.connect(calibrate=False)
print("✓ 从臂已连接")
print("✓ 3个相机已连接")
print()

# 创建数据集
print("创建数据集...")
dataset = LeRobotDataset.create(
    repo_id="lerobot/arx_test_10s",
    fps=30,
    robot=follower_config,
    use_videos=True,
)
print(f"✓ 数据集已创建: {dataset.root}")
print()

print("=" * 60)
print("开始录制 - 10秒")
print("=" * 60)
print("请移动主臂进行遥操作...")
print()

# 开始episode
dataset.start_episode()

start_time = time.time()
frame_count = 0
fps = 30
dt = 1.0 / fps

try:
    while time.time() - start_time < 10.0:  # 10秒
        loop_start = time.time()

        # 读取主臂（动作）
        leader_obs = leader.get_observation()

        # 读取从臂（观测，包含相机）
        follower_obs = follower.get_observation()

        # 构建帧数据
        frame = {
            "task": "Test recording",
            "timestamp": time.time() - start_time,
        }

        # 添加观测数据
        for key, value in follower_obs.items():
            frame[f"observation.{key}"] = value

        # 添加动作数据（主臂位置映射到从臂动作）
        scale = 3.14159 / 100.0
        for i in range(6):
            frame[f"action.joint_{i}.pos"] = leader_obs[f"joint_{i}.pos"] * scale
        frame["action.gripper.pos"] = leader_obs["gripper.pos"] * 10.0

        # 保存帧
        dataset.add_frame(frame)
        frame_count += 1

        # 显示进度
        elapsed = time.time() - start_time
        if frame_count % 30 == 0:
            print(f"录制中... {elapsed:.1f}s / 10.0s ({frame_count} 帧)")

        # 控制帧率
        loop_time = time.time() - loop_start
        sleep_time = dt - loop_time
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    print("\n用户中断")

# 保存episode
print()
print("保存数据...")
dataset.save_episode()
print(f"✓ Episode已保存 ({frame_count} 帧)")

# 编码视频
print()
print("编码视频...")
dataset._batch_save_episode_video(0, 1)
print("✓ 视频已编码")

# 完成
dataset.finalize()
print()
print("=" * 60)
print("录制完成！")
print("=" * 60)
print()
print(f"数据保存位置: {dataset.root}")
print(f"总帧数: {frame_count}")
print(f"视频文件:")
print(f"  - {dataset.root}/videos/wrist/episode_000000.mp4")
print(f"  - {dataset.root}/videos/front/episode_000000.mp4")
print(f"  - {dataset.root}/videos/top/episode_000000.mp4")
print()

# 断开连接
leader.disconnect()
follower.disconnect()
print("✓ 硬件已断开")
