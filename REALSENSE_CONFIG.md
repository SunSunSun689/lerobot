# ARX 从臂 + 3 个 RealSense D435 相机配置

## 配置示例（使用示例序列号）

### Python 配置

```python
from lerobot.robots.arx_follower import ARXFollowerConfig
from lerobot.cameras.configs import CameraConfig

config = ARXFollowerConfig(
    can_port="can0",
    arx_type=0,
    cameras={
        # 手腕相机（第一人称视角）
        "wrist": CameraConfig(
            type="realsense",
            serial_number="123456789",  # 替换为真实序列号
            width=640,
            height=480,
            fps=30,
        ),
        # 前置相机（第三人称视角）
        "front": CameraConfig(
            type="realsense",
            serial_number="234567890",  # 替换为真实序列号
            width=640,
            height=480,
            fps=30,
        ),
        # 顶部相机（俯视视角）
        "top": CameraConfig(
            type="realsense",
            serial_number="345678901",  # 替换为真实序列号
            width=640,
            height=480,
            fps=30,
        ),
    },
)
```

### 使用配置

```python
from lerobot.robots.arx_follower import ARXFollower

# 创建机器人实例
robot = ARXFollower(config)

# 连接
robot.connect(calibrate=False)

# 读取观测（包括 3 个相机图像）
obs = robot.get_observation()

# obs 包含:
# - joint_0.pos, ..., joint_5.pos, gripper.pos (关节位置)
# - wrist (numpy array, shape: (480, 640, 3))
# - front (numpy array, shape: (480, 640, 3))
# - top (numpy array, shape: (480, 640, 3))

# 断开连接
robot.disconnect()
```

## 如何获取真实序列号

### 方法 1：使用 RealSense Viewer（推荐）

```bash
# 启动 RealSense Viewer
realsense-viewer
```

在图形界面中：
1. 左侧会列出所有连接的相机
2. 每个相机显示型号和序列号
3. 点击相机可以看到预览
4. 记录 3 个序列号

### 方法 2：使用命令行工具

```bash
# 列出所有 RealSense 设备
rs-enumerate-devices | grep "Serial Number"
```

### 方法 3：使用 Python 脚本

```bash
# 运行检测脚本
python3 detect_realsense_cameras.py
```

## 替换序列号的步骤

### 步骤 1：连接相机并获取序列号

```bash
# 启动 RealSense Viewer
realsense-viewer

# 记录序列号，例如:
# 相机 1: 123456789 (wrist)
# 相机 2: 234567890 (front)
# 相机 3: 345678901 (top)
```

### 步骤 2：更新配置文件

编辑 `config_arx_realsense.py`，将示例序列号替换为真实序列号：

```python
cameras={
    "wrist": CameraConfig(
        type="realsense",
        serial_number="您的wrist相机序列号",  # 替换这里
        width=640,
        height=480,
        fps=30,
    ),
    "front": CameraConfig(
        type="realsense",
        serial_number="您的front相机序列号",  # 替换这里
        width=640,
        height=480,
        fps=30,
    ),
    "top": CameraConfig(
        type="realsense",
        serial_number="您的top相机序列号",  # 替换这里
        width=640,
        height=480,
        fps=30,
    ),
}
```

### 步骤 3：测试配置

```bash
# 测试配置
python3 config_arx_realsense.py
```

## 完整的遥操作配置

### Feetech 主臂 + ARX 从臂 + 3 个 RealSense 相机

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

# 配置从臂 + 3 个 RealSense 相机
follower_config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "wrist": CameraConfig(
            type="realsense",
            serial_number="123456789",  # 替换
            width=640,
            height=480,
            fps=30,
        ),
        "front": CameraConfig(
            type="realsense",
            serial_number="234567890",  # 替换
            width=640,
            height=480,
            fps=30,
        ),
        "top": CameraConfig(
            type="realsense",
            serial_number="345678901",  # 替换
            width=640,
            height=480,
            fps=30,
        ),
    },
)

# 使用
with FeetechLeader(leader_config) as leader, \
     ARXFollower(follower_config) as follower:

    while True:
        # 读取主臂位置
        leader_obs = leader.get_observation()

        # 映射到从臂动作
        follower_action = map_leader_to_follower(leader_obs)

        # 发送到从臂
        follower.send_action(follower_action)

        # follower_obs 包含 3 个相机图像
        follower_obs = follower.get_observation()
```

## 使用 lerobot-record 录制数据

```bash
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
    --repo-id username/dataset_name
```

## RealSense D435 高级选项

### 启用深度图

```python
CameraConfig(
    type="realsense",
    serial_number="123456789",
    width=640,
    height=480,
    fps=30,
    # 如果需要深度信息（需要检查 LeRobot 是否支持）
    # use_depth=True,
)
```

### 不同分辨率选项

RealSense D435 支持多种分辨率：

| 分辨率 | 用途 | 性能 |
|--------|------|------|
| 1920x1080 | 高质量 | 低 FPS |
| 1280x720 | 平衡 | 中等 FPS |
| 640x480 | 标准（推荐） | 30 FPS |
| 424x240 | 低质量 | 高 FPS |

## 故障排除

### 相机无法连接

```bash
# 检查 USB 连接
lsusb | grep Intel

# 检查权限
sudo usermod -a -G video $USER
# 注销并重新登录

# 重启 RealSense 服务
sudo systemctl restart udev
```

### 序列号错误

- 确保序列号完全匹配（区分大小写）
- 使用 `realsense-viewer` 确认序列号
- 检查相机是否已连接

### 性能问题

- 降低分辨率（640x480 → 424x240）
- 降低 FPS（30 → 15）
- 使用 USB 3.0 端口
- 减少相机数量进行测试

## 文件清单

- ✅ `config_arx_realsense.py` - 配置示例和测试脚本
- ✅ `detect_realsense_cameras.py` - 检测 RealSense 相机
- ✅ `REALSENSE_CONFIG.md` - 本文档

## 下一步

1. **连接相机**：连接 3 个 RealSense D435 相机
2. **获取序列号**：运行 `realsense-viewer` 或 `detect_realsense_cameras.py`
3. **更新配置**：替换示例序列号为真实序列号
4. **测试配置**：运行 `python3 config_arx_realsense.py`
5. **开始录制**：使用 `lerobot-record` 录制数据
