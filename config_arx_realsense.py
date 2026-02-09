#!/usr/bin/env python3
"""ARX 从臂 + 3 个 RealSense D435 相机配置示例"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.configs import CameraConfig


def create_arx_with_realsense_config():
    """创建 ARX 从臂 + 3 个 RealSense 相机的配置"""

    # 配置 ARX 从臂，包含 3 个 RealSense D435 相机
    config = ARXFollowerConfig(
        can_port="can0",
        arx_type=0,
        cameras={
            # 手腕相机（第一人称视角）
            "wrist": CameraConfig(
                type="realsense",
                serial_number="123456789",  # 替换为您的 wrist 相机序列号
                width=640,
                height=480,
                fps=30,
            ),
            # 前置相机（第三人称视角）
            "front": CameraConfig(
                type="realsense",
                serial_number="234567890",  # 替换为您的 front 相机序列号
                width=640,
                height=480,
                fps=30,
            ),
            # 顶部相机（俯视视角）
            "top": CameraConfig(
                type="realsense",
                serial_number="345678901",  # 替换为您的 top 相机序列号
                width=640,
                height=480,
                fps=30,
            ),
        },
    )

    return config


def test_arx_with_realsense():
    """测试 ARX 从臂 + RealSense 相机配置"""
    print("=" * 60)
    print("ARX 从臂 + 3 个 RealSense D435 相机配置")
    print("=" * 60)

    config = create_arx_with_realsense_config()

    print("\n配置信息:")
    print(f"  CAN 端口: {config.can_port}")
    print(f"  ARX 类型: {config.arx_type}")
    print(f"  相机数量: {len(config.cameras)}")
    print("\n相机配置:")
    for name, cam_config in config.cameras.items():
        print(f"  {name}:")
        print(f"    类型: {cam_config.type}")
        print(f"    序列号: {cam_config.serial_number}")
        print(f"    分辨率: {cam_config.width}x{cam_config.height}")
        print(f"    FPS: {cam_config.fps}")

    print("\n" + "=" * 60)
    print("注意事项")
    print("=" * 60)
    print("\n1. 替换序列号:")
    print("   - 连接 RealSense 相机后，运行 'realsense-viewer'")
    print("   - 记录 3 个相机的真实序列号")
    print("   - 替换上面配置中的序列号")
    print("\n2. 确定相机位置:")
    print("   - wrist: 手腕相机（第一人称视角）")
    print("   - front: 前置相机（第三人称视角）")
    print("   - top: 顶部相机（俯视视角）")
    print("\n3. 测试配置:")
    print("   - 替换序列号后，运行此脚本测试")
    print("   - 或运行 'python3 test_arx_with_realsense_full.py'")

    # 如果用户想测试（需要真实相机）
    print("\n是否要测试连接？(需要真实相机和正确的序列号) [y/N]: ", end="")
    try:
        response = input().strip().lower()
        if response == "y":
            print("\n正在连接...")
            robot = ARXFollower(config)
            robot.connect(calibrate=False)
            print("✓ ARX 从臂已连接")

            print("\n正在读取观测...")
            obs = robot.get_observation()

            print("\n关节位置:")
            for i in range(6):
                print(f"  joint_{i}: {obs[f'joint_{i}.pos']:.3f} rad")
            print(f"  gripper: {obs['gripper.pos']:.0f}")

            print("\n相机图像:")
            for cam_name in ["wrist", "front", "top"]:
                if cam_name in obs:
                    img = obs[cam_name]
                    print(f"  {cam_name}: {img.shape}")

            robot.disconnect()
            print("\n✓ 测试成功！")
        else:
            print("\n跳过测试")
    except (EOFError, KeyboardInterrupt):
        print("\n跳过测试")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        print("\n请确保:")
        print("  1. RealSense 相机已连接")
        print("  2. 序列号正确")
        print("  3. ARX 从臂已连接到 can0")


if __name__ == "__main__":
    test_arx_with_realsense()
