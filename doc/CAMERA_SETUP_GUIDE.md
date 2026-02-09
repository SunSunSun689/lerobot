# 如何为 LeRobot 添加相机

## 检测到的相机

您的系统上有 **5 个可用相机**：

| 索引 | 分辨率  | FPS | 建议用途             |
| ---- | ------- | --- | -------------------- |
| 0    | 640x480 | 30  | wrist（手腕相机）    |
| 2    | 640x360 | 15  | front（前置相机）    |
| 6    | 640x400 | 25  | top（顶部相机）      |
| 8    | 640x400 | 25  | side（侧面相机）     |
| 10   | 640x480 | 30  | overhead（俯视相机） |

## LeRobot 默认相机配置

LeRobot 项目通常配置 **2 个相机**：

- **gripper/wrist**：手腕相机（第一人称视角）
- **front**：前置相机（第三人称视角）

但您可以配置任意数量的相机！

## 添加 3 个相机的步骤

### 步骤 1：确定相机位置

首先，确定哪个相机索引对应哪个物理相机：

```bash
# 运行相机检测脚本
python3 detect_cameras.py

# 输入 'y' 来测试每个相机
# 这会依次显示每个相机的预览
```

### 步骤 2：配置 ARX 从臂

#### 选项 A：3 相机配置（推荐）

```python
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.configs import CameraConfig

config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        # 手腕相机（第一人称视角）
        "wrist": CameraConfig(
            type="opencv",
            index_or_path=0,
            width=640,
            height=480,
            fps=30,
        ),
        # 前置相机（第三人称视角）
        "front": CameraConfig(
            type="opencv",
            index_or_path=2,
            width=640,
            height=360,
            fps=30,
        ),
        # 顶部相机（俯视视角）
        "top": CameraConfig(
            type="opencv",
            index_or_path=6,
            width=640,
            height=400,
            fps=30,
        ),
    },
)
```

#### 选项 B：4 相机配置

如果您想要 4 个相机：

```python
config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "wrist": CameraConfig(type="opencv", index_or_path=0, width=640, height=480, fps=30),
        "front": CameraConfig(type="opencv", index_or_path=2, width=640, height=360, fps=30),
        "top": CameraConfig(type="opencv", index_or_path=6, width=640, height=400, fps=30),
        "side": CameraConfig(type="opencv", index_or_path=8, width=640, height=400, fps=30),
    },
)
```

### 步骤 3：测试配置

```bash
# 测试 ARX 从臂 + 相机
python3 test_arx_with_cameras.py
```

### 步骤 4：在遥操作中使用

#### Python 脚本

```python
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig
from lerobot.cameras.configs import CameraConfig

# 配置主臂
leader_config = FeetechLeaderConfig(
    port="/dev/ttyACM0",
    motor_ids=[1, 2, 3, 4, 5, 6],
    gripper_id=7,
    id="feetech_leader_default",
)

# 配置从臂 + 3 相机
follower_config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "wrist": CameraConfig(type="opencv", index_or_path=0, width=640, height=480, fps=30),
        "front": CameraConfig(type="opencv", index_or_path=2, width=640, height=360, fps=30),
        "top": CameraConfig(type="opencv", index_or_path=6, width=640, height=400, fps=30),
    },
)

# 使用
with FeetechLeader(leader_config) as leader, \
     ARXFollower(follower_config) as follower:

    # 读取主臂位置
    leader_obs = leader.get_observation()

    # 读取从臂状态（包括相机图像）
    follower_obs = follower.get_observation()

    # follower_obs 包含:
    # - joint_0.pos, ..., joint_5.pos, gripper.pos
    # - wrist (图像数组)
    # - front (图像数组)
    # - top (图像数组)
```

#### 使用 LeRobot CLI

```bash
# 录制数据
lerobot-record \
    --robot-type arx_follower \
    --robot-config '{
        "can_port": "can0",
        "cameras": {
            "wrist": {"type": "opencv", "index_or_path": 0, "width": 640, "height": 480, "fps": 30},
            "front": {"type": "opencv", "index_or_path": 2, "width": 640, "height": 360, "fps": 30},
            "top": {"type": "opencv", "index_or_path": 6, "width": 640, "height": 400, "fps": 30}
        }
    }' \
    --repo-id username/dataset_name
```

## 相机命名约定

LeRobot 中常用的相机名称：

| 名称                | 用途     | 视角                         |
| ------------------- | -------- | ---------------------------- |
| `wrist` / `gripper` | 手腕相机 | 第一人称，看机械臂抓取的物体 |
| `front`             | 前置相机 | 第三人称，正面视角           |
| `top` / `overhead`  | 顶部相机 | 俯视视角，看整个工作区域     |
| `side`              | 侧面相机 | 侧面视角                     |
| `phone`             | 手机相机 | 移动视角（某些项目使用）     |

## 相机类型

LeRobot 支持多种相机类型：

### OpenCV 相机（USB 相机）

```python
CameraConfig(
    type="opencv",
    index_or_path=0,  # 相机索引或设备路径
    width=640,
    height=480,
    fps=30,
)
```

### Intel RealSense 相机

```python
CameraConfig(
    type="realsense",
    serial_number="123456789",  # RealSense 序列号
    width=640,
    height=480,
    fps=30,
)
```

## 性能考虑

### 相机数量 vs 性能

| 相机数量 | 数据量    | 推荐配置           |
| -------- | --------- | ------------------ |
| 1 相机   | ~30 MB/s  | 基本配置           |
| 2 相机   | ~60 MB/s  | 标准配置           |
| 3 相机   | ~90 MB/s  | 推荐配置           |
| 4+ 相机  | 120+ MB/s | 需要高性能 CPU/GPU |

### 优化建议

1. **降低分辨率**：如果性能不足，可以降低到 320x240
2. **降低 FPS**：从 30 FPS 降到 15 FPS
3. **使用硬件编码**：如果录制视频，使用 H.264 硬件编码

## 故障排除

### 相机无法打开

```bash
# 检查相机设备
ls -l /dev/video*

# 检查权限
sudo usermod -a -G video $USER
# 注销并重新登录

# 测试相机
python3 detect_cameras.py
```

### 相机延迟高

- 降低分辨率
- 降低 FPS
- 使用更快的 USB 端口（USB 3.0）
- 减少相机数量

### 图像质量差

- 调整相机焦距
- 改善照明条件
- 增加分辨率（如果性能允许）

## 完整示例

查看以下文件获取完整示例：

- `detect_cameras.py` - 检测和测试相机
- `test_arx_with_cameras.py` - 测试 ARX 从臂 + 相机
- `teleoperate_demo.py` - 主从臂遥操作示例

## 下一步

1. **确定相机位置**：运行 `python3 detect_cameras.py` 并测试
2. **修改配置**：根据实际相机索引修改配置
3. **测试配置**：运行 `python3 test_arx_with_cameras.py`
4. **开始录制**：使用 `lerobot-record` 录制数据
