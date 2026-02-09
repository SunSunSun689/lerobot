#!/usr/bin/env python3
"""安全遥操作 + LeRobot 数据录制
结合零位对齐的安全遥操作和 LeRobot 标准数据格式
"""

import sys
import time
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.pipeline_features import aggregate_pipeline_dataset_features, create_initial_features
from lerobot.datasets.utils import combine_feature_dicts
from lerobot.processor import RobotAction, RobotObservation, make_default_processors
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.scripts.lerobot_record import record_loop
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.utils.control_utils import init_keyboard_listener
from lerobot.utils.utils import log_say
from lerobot.utils.visualization_utils import init_rerun

# 录制配置
NUM_EPISODES = 1  # 录制1个episode
FPS = 30
EPISODE_TIME_SEC = 20  # 20秒
RESET_TIME_SEC = 10
TASK_DESCRIPTION = "ARX-X5 teleoperation with safe control"
HF_REPO_ID = "lerobot/arx_safe_test"

def main():
    print("=" * 60)
    print("安全遥操作 + LeRobot 数据录制")
    print("=" * 60)
    print()

    # 配置相机
    camera_config = {
        "wrist": RealSenseCameraConfig(
            serial_number_or_name="346522074669",
            fps=FPS, width=640, height=480,
        ),
        "front": RealSenseCameraConfig(
            serial_number_or_name="347622073355",
            fps=FPS, width=640, height=480,
        ),
        "top": RealSenseCameraConfig(
            serial_number_or_name="406122070147",
            fps=FPS, width=640, height=480,
        ),
    }

    # 配置从臂
    follower_config = ARXFollowerConfig(
        can_port="can0",
        arx_type=0,
        cameras=camera_config,
    )

    # 配置主臂
    leader_config = FeetechLeaderConfig(
        port="/dev/ttyACM2",
        motor_ids=[1, 2, 3, 4, 5, 6],
        gripper_id=7,
        use_degrees=False,
        id="feetech_leader_default",
    )

    # 初始化机器人
    print("初始化机器人...")
    follower = ARXFollower(follower_config)
    leader = FeetechLeader(leader_config)

    # 创建处理器
    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    # 创建数据集特征
    dataset_features = combine_feature_dicts(
        aggregate_pipeline_dataset_features(
            pipeline=teleop_action_processor,
            initial_features=create_initial_features(action=follower.action_features),
            use_videos=True,
        ),
        aggregate_pipeline_dataset_features(
            pipeline=robot_observation_processor,
            initial_features=create_initial_features(observation=follower.observation_features),
            use_videos=True,
        ),
    )

    # 创建数据集
    print(f"创建数据集: {HF_REPO_ID}")
    dataset = LeRobotDataset.create(
        HF_REPO_ID,
        FPS,
        root="./data",
        robot_type=follower.name,
        features=dataset_features,
        use_videos=True,
        image_writer_processes=4,
        image_writer_threads=len(camera_config) * 4,
        vcodec="h264",
    )

    # 初始化键盘监听
    listener, events = init_keyboard_listener()

    try:
        # 连接机器人
        print("连接机器人...")
        follower.connect(calibrate=False)
        leader.connect(calibrate=False)
        print("✓ 机器人已连接")
        print()

        # 录制循环
        episode_idx = 0
        while episode_idx < NUM_EPISODES and not events["stop_recording"]:
            log_say(f"录制 episode {episode_idx + 1} / {NUM_EPISODES}")

            record_loop(
                robot=follower,
                events=events,
                fps=FPS,
                teleop=leader,
                dataset=dataset,
                control_time_s=EPISODE_TIME_SEC,
                single_task=TASK_DESCRIPTION,
                display_data=False,
                teleop_action_processor=teleop_action_processor,
                robot_action_processor=robot_action_processor,
                robot_observation_processor=robot_observation_processor,
            )

            episode_idx += 1

            # 重置环境
            if episode_idx < NUM_EPISODES and not events["stop_recording"]:
                log_say("重置环境")
                record_loop(
                    robot=follower,
                    events=events,
                    fps=FPS,
                    teleop=leader,
                    dataset=dataset,
                    control_time_s=RESET_TIME_SEC,
                    single_task="Reset",
                    display_data=False,
                    teleop_action_processor=teleop_action_processor,
                    robot_action_processor=robot_action_processor,
                    robot_observation_processor=robot_observation_processor,
                )

    finally:
        # 清理
        print("\n断开连接...")
        if follower:
            follower.disconnect()
        if leader:
            leader.disconnect()
        if listener:
            listener.stop()

        print("✓ 录制完成")
        print(f"数据保存位置: ./data/{HF_REPO_ID}")

if __name__ == "__main__":
    main()
