#!/usr/bin/env python3
"""检测和测试相机设备"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import cv2


def list_available_cameras(max_index=20):
    """列出所有可用的相机设备"""
    print("=" * 60)
    print("检测可用的相机设备")
    print("=" * 60)

    available_cameras = []

    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            # 尝试读取一帧
            ret, frame = cap.read()
            if ret:
                height, width = frame.shape[:2]
                # 尝试获取相机信息
                fps = cap.get(cv2.CAP_PROP_FPS)
                backend = cap.getBackendName()

                print(f"\n✓ 找到相机 {index}:")
                print(f"  - 分辨率: {width}x{height}")
                print(f"  - FPS: {fps}")
                print(f"  - 后端: {backend}")

                available_cameras.append({
                    "index": index,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "backend": backend,
                })
            cap.release()

    print("\n" + "=" * 60)
    print(f"总共找到 {len(available_cameras)} 个可用相机")
    print("=" * 60)

    return available_cameras


def test_camera(index, duration=3):
    """测试指定的相机"""
    print(f"\n测试相机 {index}（按 'q' 退出）...")

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f"✗ 无法打开相机 {index}")
        return False

    print(f"✓ 相机 {index} 已打开")
    print(f"显示 {duration} 秒预览...")

    import time
    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if ret:
            frame_count += 1
            # 在图像上显示相机索引
            cv2.putText(
                frame,
                f"Camera {index}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            cv2.imshow(f"Camera {index}", frame)

            # 按 'q' 退出
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            print(f"✗ 无法读取相机 {index} 的帧")
            break

    cap.release()
    cv2.destroyAllWindows()

    actual_fps = frame_count / (time.time() - start_time)
    print(f"✓ 实际 FPS: {actual_fps:.2f}")

    return True


def generate_camera_config(cameras):
    """生成相机配置代码"""
    print("\n" + "=" * 60)
    print("生成相机配置")
    print("=" * 60)

    # 建议的相机名称
    camera_names = ["wrist", "front", "top", "side", "overhead"]

    print("\n建议的相机配置:\n")
    print("```python")
    print("from lerobot.cameras.configs import CameraConfig")
    print()
    print("cameras = {")

    for i, cam in enumerate(cameras[:5]):  # 最多显示 5 个
        name = camera_names[i] if i < len(camera_names) else f"camera_{i}"
        print(f'    "{name}": CameraConfig(')
        print(f'        type="opencv",')
        print(f'        index_or_path={cam["index"]},')
        print(f'        width={cam["width"]},')
        print(f'        height={cam["height"]},')
        print(f'        fps=30,  # 建议使用 30 FPS')
        print(f'    ),')

    print("}")
    print("```")

    print("\n用于 ARX Follower 的配置:\n")
    print("```python")
    print("from lerobot.robots.arx_follower import ARXFollowerConfig")
    print("from lerobot.cameras.configs import CameraConfig")
    print()
    print("config = ARXFollowerConfig(")
    print('    can_port="can0",')
    print("    cameras={")

    for i, cam in enumerate(cameras[:5]):
        name = camera_names[i] if i < len(camera_names) else f"camera_{i}"
        print(f'        "{name}": CameraConfig(')
        print(f'            type="opencv",')
        print(f'            index_or_path={cam["index"]},')
        print(f'            width={cam["width"]},')
        print(f'            height={cam["height"]},')
        print(f'            fps=30,')
        print(f'        ),')

    print("    },")
    print(")")
    print("```")


def main():
    """主函数"""
    print("\n相机检测和配置工具")

    # 列出所有可用相机
    cameras = list_available_cameras()

    if not cameras:
        print("\n✗ 未找到任何相机")
        return 1

    # 询问是否测试相机
    print("\n是否要测试相机？(y/n): ", end="")
    try:
        response = input().strip().lower()
        if response == "y":
            for cam in cameras:
                print(f"\n测试相机 {cam['index']}...")
                test_camera(cam["index"], duration=3)
    except (EOFError, KeyboardInterrupt):
        print("\n跳过测试")

    # 生成配置
    generate_camera_config(cameras)

    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
