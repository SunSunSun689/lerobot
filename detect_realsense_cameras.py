#!/usr/bin/env python3
"""检测 Intel RealSense 相机"""

import sys

try:
    import pyrealsense2 as rs
except ImportError:
    print("✗ 未安装 pyrealsense2")
    print("\n请安装:")
    print("  pip3 install pyrealsense2")
    sys.exit(1)


def detect_realsense_cameras():
    """检测所有连接的 RealSense 相机"""
    print("=" * 60)
    print("检测 Intel RealSense 相机")
    print("=" * 60)

    # 创建上下文
    ctx = rs.context()
    devices = ctx.query_devices()

    if len(devices) == 0:
        print("\n✗ 未找到任何 RealSense 相机")
        print("\n请检查:")
        print("  1. 相机是否已连接")
        print("  2. USB 连接是否正常")
        print("  3. 是否有权限访问设备")
        return []

    print(f"\n找到 {len(devices)} 个 RealSense 相机:\n")

    cameras = []

    for i, device in enumerate(devices):
        serial = device.get_info(rs.camera_info.serial_number)
        name = device.get_info(rs.camera_info.name)
        firmware = device.get_info(rs.camera_info.firmware_version)
        product_line = device.get_info(rs.camera_info.product_line)

        print(f"相机 {i + 1}:")
        print(f"  序列号: {serial}")
        print(f"  型号: {name}")
        print(f"  产品线: {product_line}")
        print(f"  固件版本: {firmware}")

        # 获取支持的流
        sensors = device.query_sensors()
        print(f"  传感器数量: {len(sensors)}")

        for sensor in sensors:
            sensor_name = sensor.get_info(rs.camera_info.name)
            print(f"    - {sensor_name}")

        cameras.append({
            "serial": serial,
            "name": name,
            "product_line": product_line,
            "firmware": firmware,
        })
        print()

    return cameras


def generate_config(cameras):
    """生成配置代码"""
    if not cameras:
        return

    print("=" * 60)
    print("生成配置代码")
    print("=" * 60)

    camera_names = ["wrist", "front", "top"]

    print("\n用于 ARX Follower 的配置:\n")
    print("```python")
    print("from lerobot.robots.arx_follower import ARXFollowerConfig")
    print("from lerobot.cameras.configs import CameraConfig")
    print()
    print("config = ARXFollowerConfig(")
    print('    can_port="can0",')
    print("    cameras={")

    for i, cam in enumerate(cameras[:3]):  # 最多 3 个
        name = camera_names[i] if i < len(camera_names) else f"camera_{i}"
        print(f'        "{name}": CameraConfig(')
        print(f'            type="realsense",')
        print(f'            serial_number="{cam["serial"]}",')
        print(f'            width=640,')
        print(f'            height=480,')
        print(f'            fps=30,')
        print(f'        ),')

    print("    },")
    print(")")
    print("```")

    print("\n用于 lerobot-record 的配置:\n")
    print("```bash")
    print("lerobot-record \\")
    print("    --robot-type arx_follower \\")
    print("    --robot-config '{")
    print('        "can_port": "can0",')
    print('        "cameras": {')

    for i, cam in enumerate(cameras[:3]):
        name = camera_names[i] if i < len(camera_names) else f"camera_{i}"
        comma = "," if i < min(len(cameras), 3) - 1 else ""
        print(f'            "{name}": {{')
        print(f'                "type": "realsense",')
        print(f'                "serial_number": "{cam["serial"]}",')
        print(f'                "width": 640,')
        print(f'                "height": 480,')
        print(f'                "fps": 30')
        print(f'            }}{comma}')

    print('        }')
    print("    }' \\")
    print("    --repo-id username/dataset_name")
    print("```")


def main():
    """主函数"""
    cameras = detect_realsense_cameras()

    if cameras:
        generate_config(cameras)

        print("\n" + "=" * 60)
        print("完成！")
        print("=" * 60)
        print("\n提示:")
        print("  - 将上面的序列号复制到您的配置中")
        print("  - 确保相机名称（wrist, front, top）与实际位置匹配")
        print("  - 可以运行 test_realsense_cameras.py 测试配置")

    return 0 if cameras else 1


if __name__ == "__main__":
    sys.exit(main())
