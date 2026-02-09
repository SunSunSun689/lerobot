#!/usr/bin/env python3
"""
LeRobot数据格式转换脚本
将LeRobot格式转换为交付标准的JSONL格式

输入: LeRobot格式 (data/chunk-*/file-*.parquet + videos/observation.images.*/chunk-*/file-*.mp4)
输出: 交付格式 (JSONL + 重组的目录结构)
"""

import json
import shutil
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# ============================================================================
# 夹爪单位转换配置
# ============================================================================
# ARX5夹爪使用无量纲控制值(0-3范围)，需要转换为物理宽度(米)
# 转换公式: width_m = control_value * GRIPPER_SCALE_FACTOR
#
# ARX5夹爪实际夹持范围: 0-80mm
# 控制值范围: 0-3.0 (SDK标准)
# 转换系数: 0.08m / 3.0 = 0.026667
GRIPPER_SCALE_FACTOR = 0.08 / 3.0  # 控制值 -> 米 (约0.0267)
# ============================================================================

# 导入FK计算器
try:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "DoRobot-vr" / "scripts"))
    from fk_calculator import ForwardKinematicsCalculator

    FK_AVAILABLE = True
except Exception as e:
    print(f"⚠ 无法导入FK计算器: {e}")
    print("  将使用占位符代替end_effector_pose")
    FK_AVAILABLE = False


class LeRobotDataConverter:
    def __init__(self, input_dir: str, output_dir: str, task_name: str = "leader_follower_x5"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.task_name = task_name

        # 初始化FK计算器
        if FK_AVAILABLE:
            try:
                self.fk = ForwardKinematicsCalculator()
                self.use_real_fk = True
                print("✓ FK计算器初始化成功，将使用真实的end_effector_pose")
            except Exception as e:
                print(f"⚠ FK计算器初始化失败: {e}")
                print("  将使用占位符")
                self.use_real_fk = False
        else:
            self.use_real_fk = False

    def calculate_actual_fps(self, df: pd.DataFrame) -> float:
        """
        从时间戳计算实际fps
        """
        if len(df) > 1:
            timestamps = df["timestamp"].values
            total_duration = timestamps[-1] - timestamps[0]
            num_intervals = len(timestamps) - 1

            if total_duration > 0:
                actual_fps = num_intervals / total_duration
                print(f"✓ 从时间戳计算实际fps: {actual_fps:.2f}")
                return actual_fps

        # 如果计算失败，返回默认值
        print("⚠ 无法从时间戳计算fps，使用默认fps=30")
        return 30.0

    def convert_dataset(self):
        """转换整个数据集"""
        print("=" * 70)
        print("LeRobot数据格式转换工具")
        print("=" * 70)

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 查找所有parquet文件 (LeRobot格式: file-*.parquet)
        parquet_files = sorted(self.input_dir.glob("data/chunk-*/file-*.parquet"))

        if not parquet_files:
            print("❌ 未找到parquet文件")
            return

        print(f"\n找到 {len(parquet_files)} 个数据文件")

        # 读取所有数据并按episode分组
        all_episodes = []
        for parquet_file in parquet_files:
            print(f"读取 {parquet_file.name}...")
            table = pq.read_table(str(parquet_file))
            df = table.to_pandas()

            # 按episode_index分组
            for episode_idx in df["episode_index"].unique():
                episode_df = df[df["episode_index"] == episode_idx].copy()
                episode_df = episode_df.sort_values("frame_index").reset_index(drop=True)
                all_episodes.append((episode_idx, episode_df, parquet_file.parent.name, parquet_file))

        print(f"\n总共找到 {len(all_episodes)} 个episode")

        # 转换每个episode
        for episode_idx, episode_df, chunk_name, parquet_file in all_episodes:
            episode_name = f"episode_{episode_idx:06d}"
            print(f"\n处理 {episode_name}...")
            self.convert_episode(episode_df, episode_name, episode_idx, chunk_name, parquet_file)

        # 生成全局元数据
        if all_episodes:
            _, first_df, _, _ = all_episodes[0]
            self.generate_task_desc()
            self.generate_task_info(first_df)

        print("\n" + "=" * 70)
        print("✓ 转换完成!")
        print(f"输出目录: {self.output_dir}")
        print("=" * 70)

    def convert_episode(
        self, df: pd.DataFrame, episode_name: str, episode_idx: int, chunk_name: str, parquet_file: Path
    ):
        """转换单个episode"""
        # 创建episode目录
        episode_dir = self.output_dir / "data" / episode_name
        episode_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        meta_dir = episode_dir / "meta"
        states_dir = episode_dir / "states"
        videos_dir = episode_dir / "videos"

        meta_dir.mkdir(exist_ok=True)
        states_dir.mkdir(exist_ok=True)
        videos_dir.mkdir(exist_ok=True)

        # 1. 生成states.jsonl
        print("  生成 states.jsonl...")
        self.generate_states_jsonl(df, states_dir / "states.jsonl", parquet_file)

        # 2. 生成episode_meta.json
        print("  生成 episode_meta.json...")
        self.generate_episode_meta(df, episode_idx, meta_dir / "episode_meta.json", parquet_file)

        # 3. 复制视频文件
        print("  复制视频文件...")
        self.copy_videos(chunk_name, videos_dir)

        print(f"  ✓ {episode_name} 转换完成")

    def generate_states_jsonl(self, df: pd.DataFrame, output_file: Path, parquet_file: Path):
        """生成states.jsonl文件"""
        import os

        # 计算绝对时间戳的基准时间
        file_mtime = os.path.getmtime(str(parquet_file))
        max_relative_time = float(df["timestamp"].iloc[-1])
        base_time = file_mtime - max_relative_time

        with open(output_file, "w") as f:
            for i in range(len(df)):
                # 提取数据
                action = df["action"].iloc[i]
                obs_state = df["observation.state"].iloc[i]
                relative_timestamp = df["timestamp"].iloc[i]

                # 转换为绝对时间戳
                absolute_timestamp = base_time + float(relative_timestamp)

                # 构建state字典 (确保所有值都是Python原生类型)
                state = {
                    # 关节位置 (从observation.state提取前6个)
                    "joint_positions": [float(x) for x in obs_state[:6]],
                    # 关节速度 (从相邻帧计算)
                    "joint_velocities": [
                        float(x) for x in self.calculate_velocities(df, i, "observation.state", 6)
                    ],
                    # 末端执行器位姿 (通过正运动学计算)
                    "end_effector_pose": [float(x) for x in self.get_end_effector_pose(obs_state[:6])],
                    # 夹爪宽度 (从observation.state第7个值转换为米)
                    "gripper_width": float(obs_state[6]) * GRIPPER_SCALE_FACTOR,
                    # 夹爪速度 (从相邻帧计算，转换为米/秒)
                    "gripper_velocity": float(self.calculate_gripper_velocity(df, i)) * GRIPPER_SCALE_FACTOR,
                    # 时间戳 (绝对时间戳)
                    "timestamp": absolute_timestamp,
                }

                # 写入JSONL
                f.write(json.dumps(state) + "\n")

    def calculate_velocities(self, df: pd.DataFrame, index: int, column: str, num_joints: int) -> list[float]:
        """计算关节速度"""
        if index == 0:
            # 第一帧，速度为0
            return [0.0] * num_joints

        # 当前位置和上一帧位置
        current_pos = df[column].iloc[index][:num_joints]
        prev_pos = df[column].iloc[index - 1][:num_joints]

        # 时间差
        dt = df["timestamp"].iloc[index] - df["timestamp"].iloc[index - 1]

        if dt <= 0:
            return [0.0] * num_joints

        # 速度 = (位置差) / 时间差
        velocities = [(current_pos[i] - prev_pos[i]) / dt for i in range(num_joints)]

        return velocities

    def calculate_gripper_velocity(self, df: pd.DataFrame, index: int) -> float:
        """计算夹爪速度"""
        if index == 0:
            return 0.0

        # 当前和上一帧的夹爪值
        current_gripper = df["observation.state"].iloc[index][6]
        prev_gripper = df["observation.state"].iloc[index - 1][6]

        # 时间差
        dt = df["timestamp"].iloc[index] - df["timestamp"].iloc[index - 1]

        if dt <= 0:
            return 0.0

        return float((current_gripper - prev_gripper) / dt)

    def get_end_effector_pose(self, joint_positions) -> list[float]:
        """获取末端执行器位姿"""
        if self.use_real_fk:
            try:
                # 使用FK计算器计算真实位姿
                pose = self.fk.calculate(joint_positions.tolist())
                return pose
            except Exception as e:
                print(f"    ⚠ FK计算失败: {e}, 使用占位符")
                return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        else:
            # 使用占位符
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def generate_episode_meta(
        self, df: pd.DataFrame, episode_idx: int, output_file: Path, parquet_file: Path
    ):
        """生成episode_meta.json"""
        import os

        # 获取相对时间信息
        relative_start = float(df["timestamp"].iloc[0])
        relative_end = float(df["timestamp"].iloc[-1])
        frames = int(len(df))

        # 计算绝对时间戳
        # 基准时间 = 文件修改时间 - 最大相对时间戳
        file_mtime = os.path.getmtime(str(parquet_file))
        base_time = file_mtime - relative_end

        # 绝对时间戳 = 基准时间 + 相对时间戳
        start_time = base_time + relative_start
        end_time = base_time + relative_end

        meta = {
            "episode_index": int(episode_idx),
            "start_time": start_time,
            "end_time": end_time,
            "frames": frames,
        }

        with open(output_file, "w") as f:
            json.dump(meta, f, indent=2)

        print(f"    时间戳: {start_time:.6f} ~ {end_time:.6f} (绝对时间)")

    def copy_videos(self, chunk_name: str, videos_dir: Path):
        """复制并重命名视频文件"""
        # LeRobot视频路径: videos/observation.images.*/chunk-*/file-*.mp4

        # 映射关系: LeRobot名称 -> 目标名称
        video_mapping = {
            "observation.images.top": "global_realsense_rgb.mp4",
            "observation.images.wrist": "arm_realsense_rgb.mp4",
            "observation.images.front": "right_realsense_rgb.mp4",
        }

        for src_name, dst_name in video_mapping.items():
            # LeRobot格式: videos/observation.images.top/chunk-000/file-000.mp4
            src_file = self.input_dir / "videos" / src_name / chunk_name / "file-000.mp4"
            dst_file = videos_dir / dst_name

            if src_file.exists():
                shutil.copy2(src_file, dst_file)
                print(f"    ✓ {dst_name}")
            else:
                print(f"    ⚠ 未找到 {src_file}")

    def generate_task_desc(self):
        """生成task_desc.json"""
        # task_desc.json 只包含任务描述的4个核心字段
        task_desc = {
            "task_name": "arrange_flowers",
            "prompt": "insert the three flowers on the table into the vase one by one",
            "scoring": "\n1.5*3 points: Successfully pick up a flower.\n1.5*3 points: Successfully insert a flower into the vase.\n1.0 points: The robotic arm completes its reset.",
            "task_tag": ["repeated", "single-arm", "ARX5", "precise3d"],
        }

        output_file = self.output_dir / "task_desc.json"
        with open(output_file, "w") as f:
            json.dump(task_desc, f, indent=4, ensure_ascii=False)

        print("\n✓ 生成 task_desc.json")

    def generate_task_info(self, df: pd.DataFrame):
        """生成task_info.json"""
        # 从时间戳计算实际fps（确保与视频编码fps一致）
        actual_fps = self.calculate_actual_fps(df)

        # meta/task_info.json 包含完整的任务信息
        task_info = {
            "robot_id": "arx5_1",
            "task_desc": {
                "task_name": "arrange_flowers",
                "prompt": "insert the three flowers on the table into the vase one by one",
                "scoring": "\n1.5*3 points: Successfully pick up a flower.\n1.5*3 points: Successfully insert a flower into the vase.\n1.0 points: The robotic arm completes its reset.",
                "task_tag": ["repeated", "single-arm", "ARX5", "precise3d"],
            },
            "video_info": {
                "fps": int(round(actual_fps)),  # 使用从时间戳计算的实际fps
                "ext": "mp4",
                "encoding": {"vcodec": "libx264", "pix_fmt": "yuv420p"},
            },
        }

        meta_dir = self.output_dir / "meta"
        meta_dir.mkdir(exist_ok=True)

        output_file = meta_dir / "task_info.json"
        with open(output_file, "w") as f:
            json.dump(task_info, f, indent=4, ensure_ascii=False)

        print(f"✓ 生成 task_info.json (fps={int(round(actual_fps))})")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="转换LeRobot数据格式为交付标准")
    parser.add_argument(
        "--input", "-i", default="/home/dora/lerobot/data", help="输入目录 (默认: /home/dora/lerobot/data)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="/home/dora/lerobot/Arrange_flowers",
        help="输出目录 (默认: /home/dora/lerobot/Arrange_flowers)",
    )
    parser.add_argument(
        "--task-name", "-t", default="leader_follower_x5", help="任务名称 (默认: leader_follower_x5)"
    )

    args = parser.parse_args()

    # 创建转换器并执行转换
    converter = LeRobotDataConverter(args.input, args.output, args.task_name)
    converter.convert_dataset()


if __name__ == "__main__":
    main()
