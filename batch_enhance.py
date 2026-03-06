#!/usr/bin/env python
"""
批量增强视频脚本
自动处理目录下的所有视频文件
"""

import argparse
from pathlib import Path
import subprocess
import sys


def batch_enhance_videos(
    input_dir,
    output_dir,
    denoise=12,
    sharpen=1.5,
    brightness=5,
    quality=20,
    pattern="*.mp4",
):
    """
    批量增强视频

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        denoise: 降噪强度
        sharpen: 锐化强度
        brightness: 亮度调整
        quality: 输出质量
        pattern: 文件匹配模式
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    if not input_dir.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        return

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有视频文件
    video_files = list(input_dir.glob(pattern))

    if not video_files:
        print(f"错误: 在 {input_dir} 中未找到匹配 {pattern} 的视频文件")
        return

    print(f"找到 {len(video_files)} 个视频文件")
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"\n增强参数:")
    print(f"  降噪强度: {denoise}")
    print(f"  锐化强度: {sharpen}")
    print(f"  亮度调整: {brightness}")
    print(f"  输出质量: {quality}")
    print()

    # 处理每个视频
    for i, video_file in enumerate(video_files, 1):
        print(f"\n{'='*60}")
        print(f"处理 [{i}/{len(video_files)}]: {video_file.name}")
        print(f"{'='*60}")

        # 构建输出文件名
        output_file = output_dir / f"{video_file.stem}_enhanced{video_file.suffix}"

        # 构建命令
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "enhance_video.py"),
            str(video_file),
            str(output_file),
            "--denoise",
            str(denoise),
            "--sharpen",
            str(sharpen),
            "--brightness",
            str(brightness),
            "--quality",
            str(quality),
        ]

        try:
            # 执行增强
            subprocess.run(cmd, check=True)
            print(f"✓ 完成: {output_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"✗ 失败: {video_file.name}")
            print(f"  错误: {e}")
        except KeyboardInterrupt:
            print(f"\n\n用户中断处理")
            return

    print(f"\n{'='*60}")
    print(f"批量处理完成！")
    print(f"处理了 {len(video_files)} 个视频")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="批量视频增强工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理目录下所有 mp4 文件
  python batch_enhance.py /path/to/videos /path/to/output

  # 自定义参数
  python batch_enhance.py /path/to/videos /path/to/output --denoise 15 --sharpen 2.0

  # 处理特定模式的文件
  python batch_enhance.py /path/to/videos /path/to/output --pattern "*_rgb.mp4"
        """,
    )

    parser.add_argument("input_dir", type=str, help="输入视频目录")
    parser.add_argument("output_dir", type=str, help="输出视频目录")

    parser.add_argument(
        "--denoise",
        type=int,
        default=12,
        help="降噪强度 (0-30, 默认 12)",
    )

    parser.add_argument(
        "--sharpen",
        type=float,
        default=1.5,
        help="锐化强度 (0.0-3.0, 默认 1.5)",
    )

    parser.add_argument(
        "--brightness",
        type=int,
        default=5,
        help="亮度调整 (-50 到 50, 默认 5)",
    )

    parser.add_argument(
        "--quality",
        type=int,
        default=20,
        help="输出质量 CRF 值 (0-51, 默认 20)",
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default="*.mp4",
        help="文件匹配模式 (默认 *.mp4)",
    )

    args = parser.parse_args()

    batch_enhance_videos(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        denoise=args.denoise,
        sharpen=args.sharpen,
        brightness=args.brightness,
        quality=args.quality,
        pattern=args.pattern,
    )


if __name__ == "__main__":
    main()
