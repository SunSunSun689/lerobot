#!/usr/bin/env python3
"""扫描 Feetech 电机的脚本（增强版）"""

import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus


def scan_motors_with_baudrate(port="/dev/ttyACM0", baudrate=1000000, max_id=20):
    """使用指定波特率扫描电机"""
    temp_motors = {"temp": Motor(1, "sts3215", MotorNormMode.DEGREES)}

    try:
        bus = FeetechMotorsBus(port=port, motors=temp_motors)
        # 手动设置波特率
        bus.port_handler.setBaudRate(baudrate)
        bus.connect()

        found_motors = []

        for motor_id in range(1, max_id + 1):
            try:
                # 尝试读取电机型号
                model = bus.read("Model_Number", motor_id)
                if model is not None:
                    # 尝试读取当前位置
                    position = bus.read("Present_Position", motor_id)
                    print(f"  ✓ ID {motor_id}: 型号={model}, 位置={position}")
                    found_motors.append(motor_id)
            except Exception:
                pass

        bus.disconnect()
        return found_motors

    except Exception:
        return []


def scan_motors(port="/dev/ttyACM0"):
    """扫描指定端口上的 Feetech 电机"""
    print(f"正在扫描 {port} 上的 Feetech 电机...")
    print("=" * 60)

    # 尝试不同的波特率
    baudrates = [1000000, 115200, 57600, 38400, 19200, 9600]

    print(f"将尝试以下波特率: {baudrates}")
    print("扫描 ID 范围: 1-30")
    print("=" * 60)

    all_found = []

    for baudrate in baudrates:
        print(f"\n尝试波特率 {baudrate}...")
        found = scan_motors_with_baudrate(port, baudrate, max_id=30)
        if found:
            print(f"  ✓ 在波特率 {baudrate} 下找到 {len(found)} 个电机: {found}")
            all_found.extend([(motor_id, baudrate) for motor_id in found])
        else:
            print("  - 未找到电机")

    print("\n" + "=" * 60)
    if all_found:
        print(f"总共找到 {len(all_found)} 个电机:")
        for motor_id, baudrate in all_found:
            print(f"  - ID {motor_id} @ {baudrate} bps")
    else:
        print("未找到任何电机")
        print("\n可能的原因:")
        print("  1. 电机未上电")
        print("  2. 串口连接错误")
        print("  3. 电机 ID 超出扫描范围")
        print("  4. 波特率不匹配")
    print("=" * 60)

    return all_found


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    scan_motors(port)
