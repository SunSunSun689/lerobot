#!/usr/bin/env python
"""
为视频添加绝对时间戳元数据
从 states.jsonl 读取起始时间，添加到视频文件
"""

import argparse
import json
import subprocess
from pathlib import Path
import datetime


def get_start_timestamp_from_states(states_file):
    """从 states.jsonl 获取起始时间戳"""
    with open(states_file, 'r') as f:
        first_line = f.readline()
        data = json.loads(first_line)
        return data.get("timestamp")


def add_timestamp_to_video(video_path, start_timestamp, output_path=None):
    """
    为视频添加绝对时间戳元数据
    """
    if output_path is None:
        output_path = video_path.parent / f"{video_path.stem}_timestamped{video_path.suffix}"

    # 转换时间戳为 ISO 8601 格式
    dt = datetime.datetime.fromtimestamp(start_timestamp)
    creation_time = dt.strftime("%Y-%m-%dT%H:%M:%S")

    print(f"视频: {video_path.name}")
    print(f"起始时间戳: {start_timestamp}")
    print(f"起始时间: {dt}")
    print(f"输出: {output_path.name}")

    # 使用 ffmpeg 添加元数据
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-c", "copy",  # 不重新编码
        "-metadata", f"creation_time={creation_time}",
        "-metadata", f"start_timestamp={start_timestamp}",
        "-y",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ 成功添加时间戳元数据\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 失败: {e}\n")
        return False


def process_episode(episode_dir, output_dir=None):
    """
    处理一个 episode 的所有视频
    """
    episode_dir = Path(episode_dir)
    states_file = episode_dir / "states" / "states.jsonl"
    videos_dir = episode_dir / "videos"

    if not states_file.exists():
        print(f"错误: 未找到 states 文件: {states_file}")
        return

    if not videos_dir.exists():
        print(f"错误: 未找到 videos 目录: {videos_dir}")
        return

    # 获取起始时间戳
    start_timestamp = get_start_timestamp_from_states(states_file)
    if not start_timestamp:
        print(f"错误: 无法从 states 文件读取时间戳")
        return

    print(f"\n{'='*60}")
    print(f"为视频添加绝对时间戳")
    print(f"{'='*60}\n")
    print(f"Episode: {episode_dir}")
    print(f"起始时间戳: {start_timestamp}")
    print(f"起始时间: {datetime.datetime.fromtimestamp(start_timestamp)}\n")

    # 设置输出目录
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = videos_dir.parent / "videos_timestamped"
        output_dir.mkdir(parents=True, exist_ok=True)

    # 处理所有视频
    video_files = sorted(videos_dir.glob("*.mp4"))
    success_count = 0

    for video_file in video_files:
        output_path = output_dir / video_file.name
        if add_timestamp_to_video(video_file, start_timestamp, output_path):
            success_count += 1

    print(f"{'='*60}")
    print(f"完成: {success_count}/{len(video_files)} 个视频添加了时间戳")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="为视频添加绝对时间戳元数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理一个 episode
  python add_video_timestamps.py /path/to/episode_000000

  # 指定输出目录
  python add_video_timestamps.py /path/to/episode_000000 --output /path/to/output

说明:
  - 从 states/states.jsonl 读取起始时间戳
  - 将绝对时间戳添加到视频元数据
  - 不重新编码视频，只修改元数据
  - 输出到 videos_timestamped 目录
        """
    )

    parser.add_argument("episode_dir", type=str, help="Episode 目录路径")
    parser.add_argument("--output", type=str, help="输出目录（可选）")

    args = parser.parse_args()

    process_episode(args.episode_dir, args.output)


if __name__ == "__main__":
    main()
