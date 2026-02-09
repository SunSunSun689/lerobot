#!/usr/bin/env python3
"""测试主臂读取 - 不控制从臂

这个脚本只读取主臂的位置，用于验证主臂数据是否正常。
"""

import sys
import time
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig


def main():
    print("=" * 60)
    print("测试主臂读取（不控制从臂）")
    print("=" * 60)

    # 配置主臂
    config = FeetechLeaderConfig(
        port="/dev/ttyACM2",
        motor_ids=[1, 2, 3, 4, 5, 6],
        gripper_id=7,
        use_degrees=False,  # 使用 -100~100 范围
        id="feetech_leader_default",
    )

    print("\n正在连接主臂...")
    leader = FeetechLeader(config)
    leader.connect(calibrate=False)
    print("✓ 主臂已连接\n")

    print("开始读取主臂位置（按 Ctrl+C 停止）")
    print("=" * 60)
    print(f"{'时间':>8} | {'J0':>7} {'J1':>7} {'J2':>7} {'J3':>7} {'J4':>7} {'J5':>7} | {'夹爪':>7}")
    print("-" * 60)

    try:
        iteration = 0
        start_time = time.time()

        while True:
            # 读取主臂位置
            obs = leader.get_observation()

            # 每10次迭代显示一次
            if iteration % 10 == 0:
                elapsed = time.time() - start_time
                print(
                    f"{elapsed:8.1f} | "
                    f"{obs['joint_0.pos']:7.2f} "
                    f"{obs['joint_1.pos']:7.2f} "
                    f"{obs['joint_2.pos']:7.2f} "
                    f"{obs['joint_3.pos']:7.2f} "
                    f"{obs['joint_4.pos']:7.2f} "
                    f"{obs['joint_5.pos']:7.2f} | "
                    f"{obs['gripper.pos']:7.2f}"
                )

            iteration += 1
            time.sleep(0.05)  # 20Hz

    except KeyboardInterrupt:
        print("\n\n用户中断")

    finally:
        print("\n正在断开连接...")
        leader.disconnect()
        print("✓ 主臂已断开")
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


if __name__ == "__main__":
    main()
