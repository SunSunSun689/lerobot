#!/usr/bin/env python3
"""
测试脚本：验证回位过程是否被记录到数据集中
"""
import json
import numpy as np
from pathlib import Path

def analyze_return_process(dataset_path):
    """分析数据集中是否包含回位过程"""

    states_file = Path(dataset_path) / "data/episode_000000/states/states.jsonl"

    if not states_file.exists():
        print(f"❌ 文件不存在: {states_file}")
        return

    with open(states_file, 'r') as f:
        lines = f.readlines()

    total_frames = len(lines)
    first_frame = json.loads(lines[0])
    last_frame = json.loads(lines[-1])

    start_pos = first_frame['joint_positions']
    duration = last_frame['timestamp'] - first_frame['timestamp']

    print("=" * 80)
    print("回位过程检测")
    print("=" * 80)
    print(f"总帧数: {total_frames}")
    print(f"持续时间: {duration:.2f} 秒")
    print(f"FPS: {total_frames / duration:.2f}")
    print()

    # 分析最后 120 帧（4秒），看是否有回位过程
    print("分析最后 120 帧的运动特征...")
    print()

    last_120_frames = [json.loads(lines[i]) for i in range(max(0, total_frames - 120), total_frames)]

    # 计算每帧与起始位置的距离
    distances = []
    timestamps = []
    for frame in last_120_frames:
        pos = frame['joint_positions']
        dist = np.sqrt(sum((pos[i] - start_pos[i])**2 for i in range(6)))
        distances.append(dist)
        timestamps.append(frame['timestamp'] - first_frame['timestamp'])

    # 检查距离变化趋势
    initial_dist = distances[0]
    final_dist = distances[-1]
    min_dist = min(distances)
    max_dist = max(distances)

    print(f"距离起始位置的变化:")
    print(f"  初始距离（第 {total_frames - 120} 帧）: {initial_dist:.4f} rad")
    print(f"  最终距离（第 {total_frames - 1} 帧）: {final_dist:.4f} rad")
    print(f"  最小距离: {min_dist:.4f} rad")
    print(f"  最大距离: {max_dist:.4f} rad")
    print(f"  距离减小: {initial_dist - final_dist:.4f} rad ({np.rad2deg(initial_dist - final_dist):.2f}°)")
    print()

    # 计算速度（每帧的位置变化）
    velocities = []
    for i in range(1, len(last_120_frames)):
        pos1 = last_120_frames[i-1]['joint_positions']
        pos2 = last_120_frames[i]['joint_positions']
        vel = np.sqrt(sum((pos2[j] - pos1[j])**2 for j in range(6)))
        velocities.append(vel)

    avg_velocity = np.mean(velocities)
    max_velocity = max(velocities)

    print(f"运动速度分析:")
    print(f"  平均速度: {avg_velocity:.6f} rad/frame ({np.rad2deg(avg_velocity):.3f}°/frame)")
    print(f"  最大速度: {max_velocity:.6f} rad/frame ({np.rad2deg(max_velocity):.3f}°/frame)")
    print()

    # 判断是否包含回位过程
    # 回位过程的特征：
    # 1. 距离明显减小（至少减小 50%）
    # 2. 有持续的运动（平均速度 > 0.001 rad/frame）
    # 3. 最终距离接近 0

    has_return = False
    reasons = []

    if final_dist < initial_dist * 0.5:
        has_return = True
        reasons.append(f"✅ 距离减小超过 50%")
    else:
        reasons.append(f"❌ 距离减小不足 50% ({(1 - final_dist/initial_dist)*100:.1f}%)")

    if avg_velocity > 0.001:
        has_return = has_return and True
        reasons.append(f"✅ 有持续运动（平均速度 {np.rad2deg(avg_velocity):.3f}°/frame）")
    else:
        has_return = False
        reasons.append(f"❌ 运动速度过慢（平均速度 {np.rad2deg(avg_velocity):.3f}°/frame）")

    if final_dist < 0.02:  # < 1.15°
        has_return = has_return and True
        reasons.append(f"✅ 最终距离接近起始位置（{np.rad2deg(final_dist):.2f}°）")
    else:
        has_return = False
        reasons.append(f"❌ 最终距离较远（{np.rad2deg(final_dist):.2f}°）")

    print("回位过程判断:")
    for reason in reasons:
        print(f"  {reason}")
    print()

    if has_return:
        print("🎉 结论：数据集包含回位过程")
    else:
        print("⚠️  结论：数据集不包含完整的回位过程")

    # 显示最后 10 帧的详细信息
    print("\n" + "=" * 80)
    print("最后 10 帧的详细位置信息")
    print("=" * 80)
    print(f"{'帧号':>6} {'时间':>8} {'joint_0':>10} {'距起始':>10}")
    print("-" * 80)
    for i in range(max(0, total_frames - 10), total_frames):
        frame = json.loads(lines[i])
        pos = frame['joint_positions'][0]
        diff = pos - start_pos[0]
        time_offset = frame['timestamp'] - first_frame['timestamp']
        print(f"{i:6d} {time_offset:8.2f}s {np.rad2deg(pos):9.2f}° {np.rad2deg(diff):+9.2f}°")

if __name__ == "__main__":
    dataset_path = "/home/dora/lerobot/Arrange_flowers"
    analyze_return_process(dataset_path)
