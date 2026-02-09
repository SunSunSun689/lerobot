# LeRobot 数据保存机制（3 相机配置）

## 数据保存概述

当您使用 `lerobot-record` 录制数据时，LeRobot 会自动保存：
1. **机器人状态**（关节位置、夹爪位置等）
2. **相机图像**（所有配置的相机）
3. **元数据**（时间戳、episode 信息等）

## 数据集结构

### 标准 LeRobot 数据集格式

```
数据集目录/
├── meta/
│   ├── info.json              # 数据集元信息
│   ├── stats.json             # 统计信息
│   └── tasks.json             # 任务描述
├── videos/
│   ├── wrist/                 # 手腕相机视频
│   │   ├── episode_000000.mp4
│   │   ├── episode_000001.mp4
│   │   └── ...
│   ├── front/                 # 前置相机视频
│   │   ├── episode_000000.mp4
│   │   ├── episode_000001.mp4
│   │   └── ...
│   └── top/                   # 顶部相机视频（新增）
│       ├── episode_000000.mp4
│       ├── episode_000001.mp4
│       └── ...
└── data/
    ├── chunk-000/
    │   └── episode_000000.parquet  # 机器人状态数据
    ├── chunk-001/
    │   └── episode_000001.parquet
    └── ...
```

## 3 相机配置的数据保存

### 自动保存机制

当您配置了 3 个相机后，LeRobot 会**自动**为每个相机创建独立的视频流：

```python
config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "wrist": CameraConfig(...),   # 保存到 videos/wrist/
        "front": CameraConfig(...),   # 保存到 videos/front/
        "top": CameraConfig(...),     # 保存到 videos/top/
    },
)
```

### 数据保存流程

1. **录制开始**
   ```bash
   lerobot-record --robot-type arx_follower --robot-config '...' --repo-id username/dataset
   ```

2. **每一帧数据**
   - 读取机器人状态（关节位置、夹爪位置）
   - 读取 3 个相机图像
   - 保存到对应的视频文件
   - 保存状态到 parquet 文件

3. **Episode 结束**
   - 完成当前 episode 的视频编码
   - 保存元数据
   - 准备下一个 episode

## 数据格式详解

### 1. 视频数据（videos/）

每个相机的视频独立保存：

```
videos/
├── wrist/
│   ├── episode_000000.mp4    # Episode 0 的手腕相机视频
│   ├── episode_000001.mp4    # Episode 1 的手腕相机视频
│   └── ...
├── front/
│   ├── episode_000000.mp4    # Episode 0 的前置相机视频
│   ├── episode_000001.mp4
│   └── ...
└── top/
    ├── episode_000000.mp4    # Episode 0 的顶部相机视频
    ├── episode_000001.mp4
    └── ...
```

**视频编码**：
- 格式：MP4 (H.264)
- 分辨率：与配置一致（例如 640x480）
- 帧率：与配置一致（例如 30 FPS）

### 2. 状态数据（data/）

机器人状态保存为 Parquet 格式：

```python
# episode_000000.parquet 包含的列：
{
    "timestamp": [0.0, 0.033, 0.066, ...],           # 时间戳
    "episode_index": [0, 0, 0, ...],                 # Episode 索引
    "frame_index": [0, 1, 2, ...],                   # 帧索引

    # 观测数据
    "observation.joint_0.pos": [0.1, 0.12, ...],     # 关节 0 位置
    "observation.joint_1.pos": [0.2, 0.22, ...],     # 关节 1 位置
    # ... 其他关节
    "observation.gripper.pos": [500, 510, ...],      # 夹爪位置

    # 相机图像索引（指向视频文件）
    "observation.wrist.frame_index": [0, 1, 2, ...], # 手腕相机帧索引
    "observation.front.frame_index": [0, 1, 2, ...], # 前置相机帧索引
    "observation.top.frame_index": [0, 1, 2, ...],   # 顶部相机帧索引

    # 动作数据（如果有主臂）
    "action.joint_0.pos": [0.1, 0.12, ...],
    # ... 其他动作
}
```

### 3. 元数据（meta/）

#### info.json
```json
{
    "robot_type": "arx_follower",
    "fps": 30,
    "cameras": {
        "wrist": {
            "type": "realsense",
            "width": 640,
            "height": 480,
            "fps": 30
        },
        "front": {
            "type": "realsense",
            "width": 640,
            "height": 480,
            "fps": 30
        },
        "top": {
            "type": "realsense",
            "width": 640,
            "height": 480,
            "fps": 30
        }
    },
    "total_episodes": 100,
    "total_frames": 50000
}
```

## 录制数据示例

### 使用 lerobot-record

```bash
# 录制数据（3 相机配置）
lerobot-record \
    --robot-type arx_follower \
    --robot-config '{
        "can_port": "can0",
        "cameras": {
            "wrist": {
                "type": "realsense",
                "serial_number": "123456789",
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "front": {
                "type": "realsense",
                "serial_number": "234567890",
                "width": 640,
                "height": 480,
                "fps": 30
            },
            "top": {
                "type": "realsense",
                "serial_number": "345678901",
                "width": 640,
                "height": 480,
                "fps": 30
            }
        }
    }' \
    --repo-id username/my_dataset \
    --num-episodes 100 \
    --fps 30
```

### 使用 Python 脚本录制

```python
from lerobot.datasets import LeRobotDataset
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.configs import CameraConfig

# 配置机器人
config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "wrist": CameraConfig(type="realsense", serial_number="123456789", width=640, height=480, fps=30),
        "front": CameraConfig(type="realsense", serial_number="234567890", width=640, height=480, fps=30),
        "top": CameraConfig(type="realsense", serial_number="345678901", width=640, height=480, fps=30),
    },
)

# 创建数据集
dataset = LeRobotDataset.create(
    repo_id="username/my_dataset",
    fps=30,
    robot=config,
)

# 连接机器人
robot = ARXFollower(config)
robot.connect()

# 录制 episode
for episode_idx in range(100):
    print(f"Recording episode {episode_idx}...")

    # 开始新 episode
    dataset.start_episode()

    # 录制帧
    for frame_idx in range(300):  # 10 秒 @ 30 FPS
        # 读取观测（包括 3 个相机图像）
        obs = robot.get_observation()

        # 保存到数据集
        dataset.add_frame(obs)

    # 结束 episode
    dataset.end_episode()

# 保存数据集
dataset.save()
robot.disconnect()
```

## 数据加载

### 加载数据集

```python
from lerobot.datasets import LeRobotDataset

# 加载数据集
dataset = LeRobotDataset("username/my_dataset")

# 查看数据集信息
print(f"Episodes: {dataset.num_episodes}")
print(f"Frames: {dataset.num_frames}")
print(f"Cameras: {list(dataset.camera_keys)}")  # ['wrist', 'front', 'top']

# 获取一帧数据
frame = dataset[0]
print(f"Joint positions: {frame['observation.joint_0.pos']}")
print(f"Wrist image shape: {frame['observation.wrist'].shape}")  # (480, 640, 3)
print(f"Front image shape: {frame['observation.front'].shape}")  # (480, 640, 3)
print(f"Top image shape: {frame['observation.top'].shape}")      # (480, 640, 3)
```

## 存储空间估算

### 3 相机配置的存储需求

假设：
- 分辨率：640x480
- FPS：30
- Episode 长度：10 秒
- Episodes 数量：100

**每个 episode 的存储**：
- 视频（3 个相机）：约 30 MB × 3 = 90 MB
- 状态数据：约 1 MB
- **总计**：约 91 MB/episode

**100 episodes 总存储**：
- 约 9.1 GB

### 优化存储空间

1. **降低分辨率**
   ```python
   width=320, height=240  # 减少 75% 存储
   ```

2. **降低 FPS**
   ```python
   fps=15  # 减少 50% 存储
   ```

3. **使用更高的压缩**
   - LeRobot 默认使用 H.264 编码
   - 可以调整压缩参数

## 数据集上传到 HuggingFace Hub

```bash
# 上传数据集
lerobot-upload \
    --repo-id username/my_dataset \
    --local-dir /path/to/dataset
```

## 常见问题

### Q1: 3 个相机会不会导致录制变慢？

**A**: 可能会，取决于：
- CPU/GPU 性能
- USB 带宽（使用 USB 3.0）
- 磁盘写入速度

**优化建议**：
- 使用 SSD 而不是 HDD
- 降低分辨率或 FPS
- 使用硬件编码

### Q2: 可以只保存部分相机吗？

**A**: 可以，在配置中只包含需要的相机：

```python
cameras={
    "wrist": CameraConfig(...),  # 只保存手腕相机
}
```

### Q3: 数据保存在哪里？

**A**: 默认保存在：
```
~/.cache/huggingface/lerobot/datasets/username___my_dataset/
```

可以通过环境变量修改：
```bash
export HF_HOME=/path/to/custom/location
```

### Q4: 如何查看已录制的数据？

**A**: 使用 LeRobot 的可视化工具：

```bash
# 可视化数据集
lerobot-visualize --repo-id username/my_dataset
```

## 总结

### 关键点

1. ✅ **自动保存**：配置 3 个相机后，LeRobot 自动为每个相机保存视频
2. ✅ **独立视频流**：每个相机的视频独立保存在 `videos/相机名/` 目录
3. ✅ **统一时间戳**：所有相机和状态数据使用统一的时间戳
4. ✅ **高效存储**：使用 MP4 (H.264) 压缩视频，Parquet 存储状态

### 下一步

1. 配置 3 个 RealSense 相机
2. 运行 `lerobot-record` 录制数据
3. 检查数据集结构
4. 使用数据训练策略
