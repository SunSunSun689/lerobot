#!/usr/bin/env python3
"""测试 Feetech 主臂"""

import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig


def test_feetech_leader():
    """测试 Feetech 主臂连接和读取"""
    print("=" * 60)
    print("测试 Feetech 主臂")
    print("=" * 60)

    # 创建配置
    config = FeetechLeaderConfig(
        port="/dev/ttyACM0",
        motor_ids=[1, 2, 3, 4, 5, 6],  # 6 个关节
        gripper_id=7,  # 夹爪
        use_degrees=False,  # 使用 -100 到 100 范围
        id="feetech_leader_default",  # 使用已有的校准文件
    )

    print("\n配置:")
    print(f"  端口: {config.port}")
    print(f"  关节电机 ID: {config.motor_ids}")
    print(f"  夹爪电机 ID: {config.gripper_id}")
    print(f"  使用角度: {config.use_degrees}")

    try:
        # 连接主臂
        print("\n正在连接主臂...")
        leader = FeetechLeader(config)
        leader.connect(calibrate=False)  # 使用已有校准文件，不重新校准

        print("✓ 主臂已连接")
        print(f"✓ 使用校准文件: {leader.calibration_fpath}")

        # 读取当前位置
        print("\n读取当前位置...")
        obs = leader.get_observation()

        print("\n当前关节位置:")
        for i in range(6):
            motor_name = f"joint_{i}"
            if f"{motor_name}.pos" in obs:
                print(f"  {motor_name}: {obs[f'{motor_name}.pos']:.2f}")

        if "gripper.pos" in obs:
            print(f"  gripper: {obs['gripper.pos']:.2f}")

        # 断开连接
        print("\n断开连接...")
        leader.disconnect()
        print("✓ 主臂已断开")

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
    success = test_feetech_leader()
    sys.exit(0 if success else 1)
