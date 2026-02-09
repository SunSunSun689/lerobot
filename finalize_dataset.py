#!/usr/bin/env python3
"""手动整合数据集 - 将临时 PNG 转换为 MP4 和 Parquet"""

import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.datasets.lerobot_dataset import LeRobotDataset

# 数据集路径
REPO_ID = "lerobot/arx_safe_test"
ROOT = "./data"

print("=" * 60)
print("手动整合数据集")
print("=" * 60)
print()
print(f"数据集: {REPO_ID}")
print(f"路径: {ROOT}")
print()

# 加载数据集
print("加载数据集...")
dataset = LeRobotDataset(REPO_ID, root=ROOT)

print("当前状态:")
print(f"  Episodes: {dataset.num_episodes}")
print(f"  Frames: {dataset.num_frames}")
print()

# 整合数据
print("开始整合数据（PNG → MP4, 数据 → Parquet）...")
dataset.finalize()

print()
print("✓ 整合完成！")
print()
print("最终状态:")
print(f"  Episodes: {dataset.num_episodes}")
print(f"  Frames: {dataset.num_frames}")
