#!/usr/bin/env python3
"""Feetech 主臂 + ARX 从臂遥操作示例

这个脚本演示如何使用 Feetech 主臂控制 ARX-X5 从臂。
"""

import sys
import time
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig


def teleoperate_demo():
    """演示主臂控制从臂"""
    print("=" * 60)
    print("Feetech 主臂 + ARX 从臂遥操作演示")
    print("=" * 60)

    # 配置主臂
    leader_config = FeetechLeaderConfig(
        port="/dev/ttyACM0",
        motor_ids=[1, 2, 3, 4, 5, 6],
        gripper_id=7,
        use_degrees=False,  # 使用 -100 到 100 范围
        id="feetech_leader_default",
    )

    # 配置从臂
    follower_config = ARXFollowerConfig(
        can_port="can0",
        arx_type=0,
    )

    print("\n主臂配置:")
    print(f"  端口: {leader_config.port}")
    print(f"  关节电机 ID: {leader_config.motor_ids}")
    print(f"  夹爪电机 ID: {leader_config.gripper_id}")

    print("\n从臂配置:")
    print(f"  CAN 端口: {follower_config.can_port}")
    print(f"  ARX 类型: {follower_config.arx_type}")

    try:
        # 连接主臂
        print("\n正在连接主臂...")
        leader = FeetechLeader(leader_config)
        leader.connect(calibrate=False)
        print("✓ 主臂已连接")

        # 连接从臂
        print("\n正在连接从臂...")
        follower = ARXFollower(follower_config)
        follower.connect(calibrate=False)
        print("✓ 从臂已连接")

        print("\n" + "=" * 60)
        print("开始遥操作！")
        print("按 Ctrl+C 停止")
        print("=" * 60)

        # 遥操作循环
        iteration = 0
        while True:
            # 读取主臂位置
            leader_obs = leader.get_observation()

            # 映射主臂位置到从臂动作
            # 注意：这里需要根据实际的机械臂配置进行映射
            # 主臂使用 -100 到 100 范围，从臂使用弧度
            # 这是一个简单的示例映射，实际使用时需要调整

            follower_action = {
                # 将主臂的 -100~100 范围映射到从臂的弧度范围
                # 这里假设 -100~100 对应 -π~π
                "joint_0.pos": leader_obs["joint_0.pos"] * 3.14159 / 100.0,
                "joint_1.pos": leader_obs["joint_1.pos"] * 3.14159 / 100.0,
                "joint_2.pos": leader_obs["joint_2.pos"] * 3.14159 / 100.0,
                "joint_3.pos": leader_obs["joint_3.pos"] * 3.14159 / 100.0,
                "joint_4.pos": leader_obs["joint_4.pos"] * 3.14159 / 100.0,
                "joint_5.pos": leader_obs["joint_5.pos"] * 3.14159 / 100.0,
                # 将夹爪的 0~100 范围映射到 0~1000
                "gripper.pos": leader_obs["gripper.pos"] * 10.0,
            }

            # 发送动作到从臂
            follower.send_action(follower_action)

            # 每秒打印一次状态
            if iteration % 20 == 0:  # 假设 20Hz 控制频率
                print(f"\n迭代 {iteration}:")
                print(f"  主臂 joint_0: {leader_obs['joint_0.pos']:.2f}")
                print(f"  从臂 joint_0: {follower_action['joint_0.pos']:.3f} rad")
                print(f"  主臂 gripper: {leader_obs['gripper.pos']:.2f}")
                print(f"  从臂 gripper: {follower_action['gripper.pos']:.0f}")

            iteration += 1
            time.sleep(0.05)  # 20Hz 控制频率

    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # 断开连接
        print("\n正在断开连接...")
        try:
            leader.disconnect()
            print("✓ 主臂已断开")
        except:
            pass
        try:
            follower.disconnect()
            print("✓ 从臂已断开")
        except:
            pass

    print("\n" + "=" * 60)
    print("遥操作结束")
    print("=" * 60)


if __name__ == "__main__":
    teleoperate_demo()
