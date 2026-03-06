#!/usr/bin/env python3
"""分析 episode 的起始和终止关节位置"""

import json
from pathlib import Path

def analyze_episode(episode_path):
    """分析单个 episode 的起始和终止位置"""
    states_file = episode_path / "states" / "states.jsonl"

    with open(states_file, 'r') as f:
        lines = f.readlines()

    # 第一帧和最后一帧
    first_frame = json.loads(lines[0])
    last_frame = json.loads(lines[-1])

    return first_frame, last_frame

def print_joint_info(frame, label):
    """打印关节信息"""
    joints = frame['joint_positions']
    gripper = frame['gripper_width']

    print(f"\n{label}:")
    print(f"  joint_0: {joints[0]:.4f} rad ({joints[0] * 180 / 3.14159:.2f}°)")
    print(f"  joint_1: {joints[1]:.4f} rad ({joints[1] * 180 / 3.14159:.2f}°)")
    print(f"  joint_2: {joints[2]:.4f} rad ({joints[2] * 180 / 3.14159:.2f}°)")
    print(f"  joint_3: {joints[3]:.4f} rad ({joints[3] * 180 / 3.14159:.2f}°)")
    print(f"  joint_4: {joints[4]:.4f} rad ({joints[4] * 180 / 3.14159:.2f}°)")
    print(f"  joint_5: {joints[5]:.4f} rad ({joints[5] * 180 / 3.14159:.2f}°)")
    print(f"  gripper: {gripper:.4f}")

def compare_positions(pos1, pos2, label1, label2):
    """比较两个位置是否一致"""
    print(f"\n比较 {label1} vs {label2}:")

    joints1 = pos1['joint_positions']
    joints2 = pos2['joint_positions']
    gripper1 = pos1['gripper_width']
    gripper2 = pos2['gripper_width']

    threshold = 0.01  # 阈值

    all_match = True

    # 比较关节
    for i in range(6):
        diff = abs(joints1[i] - joints2[i])
        match = diff < threshold
        all_match = all_match and match

        status = "✓" if match else "✗"
        diff_deg = diff * 180 / 3.14159
        print(f"  {status} joint_{i}: {joints1[i]:.4f} vs {joints2[i]:.4f} (差值: {diff:.4f} rad = {diff_deg:.2f}°)")

    # 比较夹爪
    diff = abs(gripper1 - gripper2)
    match = diff < threshold
    all_match = all_match and match
    status = "✓" if match else "✗"
    print(f"  {status} gripper: {gripper1:.4f} vs {gripper2:.4f} (差值: {diff:.4f})")

    return all_match

# 主程序
import sys

# 从命令行参数获取数据集路径，默认为 Arrange_flowers
if len(sys.argv) > 1:
    dataset_path = Path(sys.argv[1])
else:
    dataset_path = Path("/home/dora/lerobot/Arrange_flowers/data")

if not dataset_path.exists():
    print(f"错误：数据集路径不存在: {dataset_path}")
    sys.exit(1)

print(f"分析数据集: {dataset_path}\n")

# 检查有多少个 episode
episodes = sorted([d for d in dataset_path.iterdir() if d.is_dir() and d.name.startswith("episode_")])
num_episodes = len(episodes)

print(f"找到 {num_episodes} 个 episode\n")

# 分析所有 episode
episode_data = []
for i, ep_dir in enumerate(episodes):
    print("=" * 80)
    print(f"Episode {i} 分析")
    print("=" * 80)

    first, last = analyze_episode(ep_dir)
    episode_data.append((first, last))
    print_joint_info(first, f"Episode {i} - 起始位置")
    print_joint_info(last, f"Episode {i} - 终止位置")
    print()

print("\n" + "=" * 80)
print("一致性检查 - 起始位置")
print("=" * 80)

# 检查所有 episode 的起始位置是否一致
start_matches = []
for i in range(num_episodes - 1):
    match = compare_positions(episode_data[i][0], episode_data[i+1][0],
                              f"Episode {i} 起始", f"Episode {i+1} 起始")
    start_matches.append(match)

print("\n" + "=" * 80)
print("一致性检查 - 终止位置")
print("=" * 80)

# 检查所有 episode 的终止位置是否一致
end_matches = []
for i in range(num_episodes - 1):
    match = compare_positions(episode_data[i][1], episode_data[i+1][1],
                              f"Episode {i} 终止", f"Episode {i+1} 终止")
    end_matches.append(match)

print("\n" + "=" * 80)
print("一致性检查 - 终止到起始")
print("=" * 80)

# 检查每个 episode 的终止位置是否与下一个 episode 的起始位置一致
transition_matches = []
for i in range(num_episodes - 1):
    match = compare_positions(episode_data[i][1], episode_data[i+1][0],
                              f"Episode {i} 终止", f"Episode {i+1} 起始")
    transition_matches.append(match)

print("\n" + "=" * 80)
print("总结")
print("=" * 80)
print("\n起始位置一致性:")
for i in range(num_episodes - 1):
    status = '✓ 一致' if start_matches[i] else '✗ 不一致'
    print(f"  Episode {i} 起始 = Episode {i+1} 起始: {status}")

print("\n终止位置一致性:")
for i in range(num_episodes - 1):
    status = '✓ 一致' if end_matches[i] else '✗ 不一致'
    print(f"  Episode {i} 终止 = Episode {i+1} 终止: {status}")

print("\n终止到起始过渡:")
for i in range(num_episodes - 1):
    status = '✓ 一致' if transition_matches[i] else '✗ 不一致'
    print(f"  Episode {i} 终止 = Episode {i+1} 起始: {status}")

print(f"\n整体评估:")
all_starts_match = all(start_matches)
all_ends_match = all(end_matches)
print(f"  所有起始位置一致: {'✓ 是' if all_starts_match else '✗ 否'}")
print(f"  所有终止位置一致: {'✓ 是' if all_ends_match else '✗ 否'}")
