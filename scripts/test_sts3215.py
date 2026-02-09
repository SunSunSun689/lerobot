#!/usr/bin/env python3
"""测试 STS3215 电机连接"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import time

def test_sts3215_connection(port="/dev/ttyACM0"):
    """测试 STS3215 电机连接"""
    print(f"测试 STS3215 电机连接 @ {port}")
    print("=" * 60)

    try:
        import scservo_sdk as scs

        # STS3215 默认参数
        BAUDRATE = 1000000
        PROTOCOL_VERSION = 0  # STS 协议

        # 创建端口处理器和数据包处理器
        port_handler = scs.PortHandler(port)
        packet_handler = scs.PacketHandler(PROTOCOL_VERSION)

        # 打开端口
        if not port_handler.openPort():
            print(f"✗ 无法打开端口 {port}")
            return False

        print(f"✓ 端口 {port} 已打开")

        # 设置波特率
        if not port_handler.setBaudRate(BAUDRATE):
            print(f"✗ 无法设置波特率 {BAUDRATE}")
            return False

        print(f"✓ 波特率设置为 {BAUDRATE}")

        # 尝试不同的波特率
        baudrates_to_try = [1000000, 115200, 1000000]

        for baudrate in baudrates_to_try:
            print(f"\n尝试波特率 {baudrate}...")
            port_handler.setBaudRate(baudrate)
            time.sleep(0.1)

            # 扫描电机 ID 1-20
            found = []
            for motor_id in range(1, 21):
                # 尝试 ping 电机
                scs_model_number, scs_comm_result, scs_error = packet_handler.ping(port_handler, motor_id)

                if scs_comm_result == scs.COMM_SUCCESS:
                    print(f"  ✓ 找到电机 ID {motor_id}, 型号: {scs_model_number}")
                    found.append(motor_id)

                    # 读取当前位置
                    try:
                        position, result, error = packet_handler.read2ByteTxRx(port_handler, motor_id, 56)  # 地址 56 是当前位置
                        if result == scs.COMM_SUCCESS:
                            print(f"    当前位置: {position}")
                    except:
                        pass

            if found:
                print(f"\n✓ 在波特率 {baudrate} 下找到 {len(found)} 个电机: {found}")
                port_handler.closePort()
                return found
            else:
                print(f"  - 未找到电机")

        port_handler.closePort()
        print("\n✗ 未找到任何电机")
        print("\n请检查:")
        print("  1. 电机是否已上电")
        print("  2. 串口连接是否正确")
        print("  3. 电机 ID 是否在 1-20 范围内")

        return []

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    result = test_sts3215_connection(port)

    if result:
        print("\n" + "=" * 60)
        print("✓ 测试成功！")
        print(f"找到的电机 ID: {result}")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ 测试失败")
        print("=" * 60)
