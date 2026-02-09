#!/usr/bin/env python3
"""测试 ARX 从臂的三相机配置"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import cv2

from lerobot.cameras.configs import CameraConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig


def test_arx_with_cameras():
    """测试 ARX 从臂的三相机配置"""
    print("=" * 60)
    print("测试 ARX 从臂 + 3 相机配置")
    print("=" * 60)

    # 配置 ARX 从臂，包含 3 个相机
    # 根据您的实际情况调整相机索引
    config = ARXFollowerConfig(
        can_port="can0",
        cameras={
            "wrist": CameraConfig(
                type="opencv",
                index_or_path=0,  # 修改为您的手腕相机索引
                width=640,
                height=480,
                fps=30,
            ),
            "front": CameraConfig(
                type="opencv",
                index_or_path=2,  # 修改为您的前置相机索引
                width=640,
                height=360,
                fps=30,
            ),
            "top": CameraConfig(
                type="opencv",
                index_or_path=6,  # 修改为您的顶部相机索引
                width=640,
                height=400,
                fps=30,
            ),
        },
    )

    print("\n配置:")
    print(f"  CAN 端口: {config.can_port}")
    print(f"  相机数量: {len(config.cameras)}")
    for name, cam_config in config.cameras.items():
        print(f"  - {name}: 索引 {cam_config.index_or_path}, {cam_config.width}x{cam_config.height}")

    try:
        # 连接机器人
        print("\n正在连接 ARX 从臂...")
        robot = ARXFollower(config)
        robot.connect(calibrate=False)
        print("✓ ARX 从臂已连接")

        # 获取观测（包括相机图像）
        print("\n正在读取观测...")
        obs = robot.get_observation()

        # 显示关节位置
        print("\n关节位置:")
        for i in range(6):
            print(f"  joint_{i}: {obs[f'joint_{i}.pos']:.3f} rad")
        print(f"  gripper: {obs['gripper.pos']:.0f}")

        # 显示相机图像
        print("\n相机图像:")
        for cam_name in ["wrist", "front", "top"]:
            if cam_name in obs:
                img = obs[cam_name]
                print(f"  {cam_name}: {img.shape}")

                # 显示图像（按 'q' 关闭）
                cv2.imshow(f"{cam_name} camera", img)

        print("\n按任意键关闭图像窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # 断开连接
        robot.disconnect()
        print("\n✓ ARX 从臂已断开")

        print("\n" + "=" * 60)
        print("✓ 测试成功！")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_arx_with_cameras()
    sys.exit(0 if success else 1)
