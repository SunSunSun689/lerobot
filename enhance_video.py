#!/usr/bin/env python
"""
视频增强工具
用于降噪、锐化、对比度增强等视频质量改善
"""

import argparse
from pathlib import Path
import cv2
import numpy as np
from tqdm import tqdm
import json


class VideoEnhancer:
    """视频增强处理器"""

    def __init__(
        self,
        denoise_strength=10,
        sharpen_strength=1.0,
        contrast_enhance=True,
        brightness_adjust=0,
        use_clahe=True,
    ):
        """
        初始化视频增强器

        Args:
            denoise_strength: 降噪强度 (0-30, 推荐 10)
            sharpen_strength: 锐化强度 (0.0-3.0, 推荐 1.0)
            contrast_enhance: 是否启用对比度增强
            brightness_adjust: 亮度调整 (-50 到 50)
            use_clahe: 是否使用 CLAHE 对比度增强
        """
        self.denoise_strength = denoise_strength
        self.sharpen_strength = sharpen_strength
        self.contrast_enhance = contrast_enhance
        self.brightness_adjust = brightness_adjust
        self.use_clahe = use_clahe

        # 创建 CLAHE 对象
        if self.use_clahe:
            self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def denoise_frame(self, frame):
        """
        对帧进行降噪处理

        使用非局部均值降噪（Non-Local Means Denoising）
        这是一种高质量的降噪算法，能保留边缘细节
        """
        if self.denoise_strength > 0:
            # fastNlMeansDenoisingColored 适用于彩色图像
            frame = cv2.fastNlMeansDenoisingColored(
                frame,
                None,
                h=self.denoise_strength,
                hColor=self.denoise_strength,
                templateWindowSize=7,
                searchWindowSize=21,
            )
        return frame

    def sharpen_frame(self, frame):
        """
        对帧进行锐化处理

        使用 Unsharp Mask (USM) 锐化算法
        """
        if self.sharpen_strength > 0:
            # 创建高斯模糊版本
            blurred = cv2.GaussianBlur(frame, (0, 0), 3)

            # USM 锐化: 原图 + 强度 * (原图 - 模糊图)
            frame = cv2.addWeighted(
                frame, 1.0 + self.sharpen_strength, blurred, -self.sharpen_strength, 0
            )

        return frame

    def enhance_contrast(self, frame):
        """
        增强对比度

        使用 CLAHE (Contrast Limited Adaptive Histogram Equalization)
        """
        if not self.contrast_enhance:
            return frame

        if self.use_clahe:
            # 转换到 LAB 色彩空间
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)

            # 只对亮度通道应用 CLAHE
            l = self.clahe.apply(l)

            # 合并通道
            lab = cv2.merge([l, a, b])
            frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            # 简单的对比度拉伸
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = cv2.equalizeHist(l)
            lab = cv2.merge([l, a, b])
            frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return frame

    def adjust_brightness(self, frame):
        """调整亮度"""
        if self.brightness_adjust != 0:
            # 使用 HSV 色彩空间调整亮度
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
            h, s, v = cv2.split(hsv)

            # 调整 V 通道（亮度）
            v = v + self.brightness_adjust
            v = np.clip(v, 0, 255)

            hsv = cv2.merge([h, s, v]).astype(np.uint8)
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        return frame

    def process_frame(self, frame):
        """
        处理单帧图像

        处理顺序：降噪 -> 对比度增强 -> 亮度调整 -> 锐化
        """
        # 1. 降噪（先做，避免放大噪声）
        frame = self.denoise_frame(frame)

        # 2. 对比度增强
        frame = self.enhance_contrast(frame)

        # 3. 亮度调整
        frame = self.adjust_brightness(frame)

        # 4. 锐化（最后做，增强细节）
        frame = self.sharpen_frame(frame)

        return frame


def enhance_video(
    input_path,
    output_path,
    denoise_strength=10,
    sharpen_strength=1.0,
    contrast_enhance=True,
    brightness_adjust=0,
    use_clahe=True,
    output_quality=23,
):
    """
    增强视频质量

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        denoise_strength: 降噪强度 (0-30)
        sharpen_strength: 锐化强度 (0.0-3.0)
        contrast_enhance: 是否启用对比度增强
        brightness_adjust: 亮度调整 (-50 到 50)
        use_clahe: 是否使用 CLAHE
        output_quality: 输出质量 (CRF 值, 0-51, 越小质量越高)
    """
    # 打开输入视频
    cap = cv2.VideoCapture(str(input_path))

    if not cap.isOpened():
        raise ValueError(f"无法打开视频文件: {input_path}")

    # 获取视频属性
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"输入视频: {input_path}")
    print(f"分辨率: {width}x{height}, FPS: {fps:.2f}, 总帧数: {total_frames}")
    print(f"\n增强参数:")
    print(f"  降噪强度: {denoise_strength}")
    print(f"  锐化强度: {sharpen_strength}")
    print(f"  对比度增强: {contrast_enhance}")
    print(f"  亮度调整: {brightness_adjust}")
    print(f"  使用 CLAHE: {use_clahe}")
    print(f"  输出质量 (CRF): {output_quality}")

    # 创建视频增强器
    enhancer = VideoEnhancer(
        denoise_strength=denoise_strength,
        sharpen_strength=sharpen_strength,
        contrast_enhance=contrast_enhance,
        brightness_adjust=brightness_adjust,
        use_clahe=use_clahe,
    )

    # 创建输出目录
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 使用 ffmpeg 创建输出视频
    # 使用 libx264 编码器，CRF 模式控制质量
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    if not out.isOpened():
        raise ValueError(f"无法创建输出视频: {output_path}")

    # 处理视频帧
    print(f"\n开始处理视频...")
    pbar = tqdm(total=total_frames, desc="处理进度")

    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 增强帧
        enhanced_frame = enhancer.process_frame(frame)

        # 写入输出视频
        out.write(enhanced_frame)

        frame_count += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    out.release()

    print(f"\n✓ 处理完成！")
    print(f"输出视频: {output_path}")
    print(f"处理帧数: {frame_count}")

    # 使用 ffmpeg 重新编码以获得更好的压缩
    print(f"\n正在使用 ffmpeg 优化输出...")
    temp_path = output_path.with_suffix(".temp.mp4")
    output_path.rename(temp_path)

    import subprocess

    cmd = [
        "ffmpeg",
        "-i",
        str(temp_path),
        "-c:v",
        "libx264",
        "-crf",
        str(output_quality),
        "-preset",
        "slow",
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        temp_path.unlink()
        print(f"✓ 视频优化完成！")
    except subprocess.CalledProcessError as e:
        print(f"警告: ffmpeg 优化失败，使用原始输出")
        temp_path.rename(output_path)
    except FileNotFoundError:
        print(f"警告: 未找到 ffmpeg，使用原始输出")
        temp_path.rename(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="视频增强工具 - 降噪、锐化、对比度增强",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本增强
  python enhance_video.py input.mp4 output.mp4

  # 自定义参数
  python enhance_video.py input.mp4 output.mp4 --denoise 15 --sharpen 1.5

  # 高质量输出
  python enhance_video.py input.mp4 output.mp4 --quality 18

  # 调整亮度
  python enhance_video.py input.mp4 output.mp4 --brightness 10
        """,
    )

    parser.add_argument("input", type=str, help="输入视频路径")
    parser.add_argument("output", type=str, help="输出视频路径")

    parser.add_argument(
        "--denoise",
        type=int,
        default=10,
        help="降噪强度 (0-30, 默认 10, 0=关闭)",
    )

    parser.add_argument(
        "--sharpen",
        type=float,
        default=1.0,
        help="锐化强度 (0.0-3.0, 默认 1.0, 0=关闭)",
    )

    parser.add_argument(
        "--no-contrast",
        action="store_true",
        help="禁用对比度增强",
    )

    parser.add_argument(
        "--brightness",
        type=int,
        default=0,
        help="亮度调整 (-50 到 50, 默认 0)",
    )

    parser.add_argument(
        "--no-clahe",
        action="store_true",
        help="不使用 CLAHE，使用简单直方图均衡化",
    )

    parser.add_argument(
        "--quality",
        type=int,
        default=23,
        help="输出质量 CRF 值 (0-51, 默认 23, 越小质量越高)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入视频不存在: {input_path}")
        return

    # 增强视频
    enhance_video(
        input_path=input_path,
        output_path=args.output,
        denoise_strength=args.denoise,
        sharpen_strength=args.sharpen,
        contrast_enhance=not args.no_contrast,
        brightness_adjust=args.brightness,
        use_clahe=not args.no_clahe,
        output_quality=args.quality,
    )


if __name__ == "__main__":
    main()

