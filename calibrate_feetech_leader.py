#!/usr/bin/env python3
"""校准 Feetech 主臂"""

import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig


def calibrate_feetech_leader():
    """校准 Feetech 主臂"""
    print("=" * 60)
    print("Feetech 主臂校准程序")
    print("=" * 60)

    # 创建配置
    config = FeetechLeaderConfig(
        port="/dev/ttyACM0",
        motor_ids=[1, 2, 3, 4, 5, 6],
        gripper_id=7,
        use_degrees=False,
        id="feetech_leader_default",  # 设置 ID 用于保存校准文件
    )

    print("\n配置:")
    print(f"  端口: {config.port}")
    print(f"  关节电机 ID: {config.motor_ids}")
    print(f"  夹爪电机 ID: {config.gripper_id}")
    print(f"  校准 ID: {config.id}")

    try:
        # 创建主臂实例
        leader = FeetechLeader(config)

        # 连接并校准
        print("\n正在连接主臂...")
        leader.connect(calibrate=True)

        print("\n✓ 校准完成！")
        print(f"校准文件已保存到: {leader.calibration_fpath}")

        # 测试读取
        print("\n测试读取位置...")
        obs = leader.get_observation()

        print("\n当前关节位置:")
        for i in range(6):
            motor_name = f"joint_{i}"
            if f"{motor_name}.pos" in obs:
                print(f"  {motor_name}: {obs[f'{motor_name}.pos']:.2f}")

        if "gripper.pos" in obs:
            print(f"  gripper: {obs['gripper.pos']:.2f}")

        # 断开连接
        leader.disconnect()

        print("\n" + "=" * 60)
        print("✓ 校准成功！")
        print("=" * 60)

        return True

    except KeyboardInterrupt:
        print("\n\n用户中断")
        return False
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = calibrate_feetech_leader()
    sys.exit(0 if success else 1)
