#!/usr/bin/env python3
"""快速修改录制配置"""

from pathlib import Path

import yaml

config_file = Path("/home/dora/lerobot/record_config.yaml")

print("=" * 60)
print("LeRobot 录制配置修改")
print("=" * 60)
print()

# 读取当前配置
with open(config_file) as f:
    config = yaml.safe_load(f)

print("当前配置:")
print(f"  数据集名称: {config['dataset']['repo_id']}")
print(f"  Episode数量: {config['dataset']['num_episodes']}")
print(f"  任务描述: {config['dataset']['single_task']}")
print(f"  FPS: {config['dataset']['fps']}")
print(f"  视频编码: {config['dataset']['vcodec']}")
print()

# 询问是否修改
modify = input("是否修改配置? (y/n, 默认n): ").strip().lower()
if modify != "y":
    print("配置未修改")
    exit(0)

print()
print("=" * 60)
print("修改配置")
print("=" * 60)
print()

# 修改数据集名称
print("数据集名称 (格式: 用户名/数据集名)")
print(f"当前: {config['dataset']['repo_id']}")
new_repo_id = input("新值 (直接回车保持不变): ").strip()
if new_repo_id:
    config["dataset"]["repo_id"] = new_repo_id

# 修改episode数量
print()
print("Episode数量")
print(f"当前: {config['dataset']['num_episodes']}")
new_num = input("新值 (直接回车保持不变): ").strip()
if new_num:
    config["dataset"]["num_episodes"] = int(new_num)

# 修改任务描述
print()
print("任务描述")
print(f"当前: {config['dataset']['single_task']}")
new_task = input("新值 (直接回车保持不变): ").strip()
if new_task:
    config["dataset"]["single_task"] = new_task

# 修改FPS
print()
print("录制FPS (建议: 20-30)")
print(f"当前: {config['dataset']['fps']}")
new_fps = input("新值 (直接回车保持不变): ").strip()
if new_fps:
    config["dataset"]["fps"] = int(new_fps)

# 修改视频编码
print()
print("视频编码器")
print("  h264 - 兼容性最好，速度快")
print("  hevc - 更高压缩率")
print("  libsvtav1 - 最高压缩率，但编码慢")
print(f"当前: {config['dataset']['vcodec']}")
new_vcodec = input("新值 (直接回车保持不变): ").strip()
if new_vcodec:
    config["dataset"]["vcodec"] = new_vcodec

# 保存配置
with open(config_file, "w") as f:
    yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

print()
print("=" * 60)
print("配置已保存")
print("=" * 60)
print()
print("新配置:")
print(f"  数据集名称: {config['dataset']['repo_id']}")
print(f"  Episode数量: {config['dataset']['num_episodes']}")
print(f"  任务描述: {config['dataset']['single_task']}")
print(f"  FPS: {config['dataset']['fps']}")
print(f"  视频编码: {config['dataset']['vcodec']}")
print()
print("运行 ./start_recording.sh 开始录制")
