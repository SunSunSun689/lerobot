# Dora - LeRobot 数据采集指南

> 完整的 ARX-X5 + Feetech Leader 遥操作数据采集文档

---

## 📋 目录

1. [系统概述](#系统概述)
2. [脚本说明](#脚本说明)
3. [使用流程](#使用流程)
4. [硬件配置](#硬件配置)
5. [控制命令](#控制命令)
6. [常见问题](#常见问题)

---

## 系统概述

### 硬件组成

- **主臂（Leader）**: Feetech STS3215 舵机臂
- **从臂（Follower）**: ARX-X5 机械臂
- **相机**: 3 个 RealSense 相机（wrist, front, top）
- **通信**: CAN 总线（从臂）+ 串口（主臂）

### 数据格式

- **LeRobot 标准格式**: Parquet + MP4 视频
- **帧率**: 30 FPS
- **安全机制**: 零位对齐 + 低通滤波 + 软限位保护

---

## 脚本说明

### 核心录制脚本

#### 1. `safe_record_lerobot_v2.py` ⭐ **推荐使用**

**功能**: 完整的安全遥操作录制系统

**特点**:

- ✅ 零位对齐（启动时记录初始位置）
- ✅ 低通滤波（平滑控制）
- ✅ 软限位保护（防止超出关节范围）
- ✅ 外部控制支持（配合 record_control.py）
- ✅ LeRobot 标准数据格式
- ✅ 支持多 episode 录制

**配置**:

- 最多录制: 10 个 episodes
- 每个 episode 最长: 5 分钟
- 数据保存路径: `lerobot/arx_safe_test`

#### 2. `safe_record_lerobot.py`

**功能**: 基础版安全遥操作录制

**特点**:

- ✅ 零位对齐
- ✅ LeRobot 标准格式
- ⚠️ 不支持外部控制
- ⚠️ 固定录制 1 个 episode

#### 3. `safe_record_simple.py`

**功能**: 简化版录制（避免复杂依赖）

**特点**:

- ✅ 零位对齐 + 低通滤波
- ✅ 直接保存 CSV + MP4
- ⚠️ 非 LeRobot 标准格式
- 适合快速测试

### 控制脚本

#### `record_control.py`

**功能**: 发送录制控制指令

**工作原理**:

- 通过创建 `/tmp/lerobot_control/` 目录下的标志文件发送指令
- 配合 `safe_record_lerobot_v2.py` 使用

**控制命令**:

- `s` - 保存当前 episode（结束当前，开始下一个）
- `e` - 保存并退出录制
- `q` - 退出控制程序（不影响录制）

### 启动脚本

#### `start_safe_record.sh`

**功能**: 一键启动安全遥操作录制

**自动执行**:

- ✅ 检查硬件连接（CAN、串口、相机）
- ✅ 设置环境变量（PYTHONPATH、LD_LIBRARY_PATH）
- ✅ 启动 `safe_record_lerobot_v2.py`

---

## 使用流程

### 标准录制流程（推荐）

#### 步骤 1: 启动录制系统

**终端 1 - 启动录制**:

```bash
cd /home/dora/lerobot
./start_safe_record.sh
```

**重要提示**:

- ⚠️ 启动后保持主臂静止约 0.5 秒
- ⚠️ 等待 "✓ 零位已记录" 提示后再移动主臂

#### 步骤 2: 启动控制程序

**终端 2 - 发送控制指令**:

```bash
cd /home/dora/lerobot
python3 record_control.py
```

#### 步骤 3: 开始录制

1. 在终端 1 看到 "✓ 零位已记录" 后，开始移动主臂
2. 从臂会跟随主臂运动
3. 相机同步录制视频

#### 步骤 4: 控制录制

在终端 2 输入命令：

- 输入 `s` + Enter → 保存当前 episode，开始下一个
- 输入 `e` + Enter → 保存并退出录制
- 输入 `q` + Enter → 退出控制程序

#### 步骤 5: 查看数据

录制完成后，数据保存在：

```
/home/dora/lerobot/data/lerobot/arx_safe_test/
├── data/
│   └── chunk-000/
│       └── file-*.parquet
└── videos/
    ├── observation.images.wrist/
    ├── observation.images.front/
    └── observation.images.top/
```

---

## 硬件配置

### 配置文件位置

**主配置文件**: `/home/dora/lerobot/safe_record_lerobot_v2.py`

### 1. 录制参数配置

**位置**: 第 278-284 行

```python
NUM_EPISODES = 10           # 最多录制的 episode 数量
FPS = 30                    # 帧率
EPISODE_TIME_SEC = 300      # 每个 episode 最长时间（秒）
RESET_TIME_SEC = 10         # 重置时间
TASK_DESCRIPTION = "ARX-X5 safe teleoperation"  # 任务描述
HF_REPO_ID = "lerobot/arx_safe_test"           # 数据集保存路径
```

### 2. 相机配置

**位置**: 第 293-307 行

```python
camera_config = {
    "wrist": RealSenseCameraConfig(
        serial_number_or_name="347622073355",  # 手腕相机序列号
        fps=FPS, width=640, height=480,
    ),
    "front": RealSenseCameraConfig(
        serial_number_or_name="346522074669",  # 前置相机序列号
        fps=FPS, width=640, height=480,
    ),
    "top": RealSenseCameraConfig(
        serial_number_or_name="406122070147",  # 顶部相机序列号
        fps=FPS, width=640, height=480,
    ),
}
```

**如何查找相机序列号**:

```bash
python3 detect_realsense_cameras.py
# 或
rs-enumerate-devices
```

### 3. 从臂（ARX Follower）配置

**位置**: 第 309-314 行

```python
follower_config = ARXFollowerConfig(
    can_port="can0",        # CAN 总线端口
    arx_type=0,             # ARX 机器人类型（0 = X5）
    cameras=camera_config,  # 相机配置
)
```

### 4. 主臂（Feetech Leader）配置

**位置**: 第 316-324 行

```python
leader_config = FeetechLeaderConfig(
    port="/dev/ttyACM2",              # 串口设备
    motor_ids=[1, 2, 3, 4, 5, 6],     # 电机 ID 列表
    gripper_id=7,                      # 夹爪 ID
    use_degrees=False,                 # 使用弧度（False）或角度（True）
    id="LeaderX5",                     # 标定文件名（LeaderX5.json）
    calibration_dir=Path("/home/dora/lerobot"),  # 标定文件目录
)
```

**如何查找串口**:

```bash
ls /dev/ttyACM*
# 或
python3 scan_feetech_motors.py
```

### 硬件配置修改场景

#### 场景 1: 更换相机

1. 运行 `python3 detect_realsense_cameras.py` 获取新序列号
2. 修改 `safe_record_lerobot_v2.py` 第 296、300、304 行的序列号
3. 同步修改相机名称（wrist/front/top）如果位置改变

#### 场景 2: 更换主臂串口

1. 运行 `ls /dev/ttyACM*` 查看可用串口
2. 修改 `safe_record_lerobot_v2.py` 第 319 行的 `port`
3. 修改 `start_safe_record.sh` 第 35 行的检查

#### 场景 3: 更换 CAN 端口

1. 修改 `safe_record_lerobot_v2.py` 第 311 行的 `can_port`
2. 修改 `start_safe_record.sh` 第 27 行的检查

#### 场景 4: 修改电机 ID

1. 运行 `python3 scan_feetech_motors.py` 扫描电机
2. 修改 `safe_record_lerobot_v2.py` 第 320-321 行的 `motor_ids` 和 `gripper_id`

### 硬件配置快速参考表

| 硬件组件       | 配置文件                    | 行号 | 当前值        |
| -------------- | --------------------------- | ---- | ------------- |
| 手腕相机序列号 | `safe_record_lerobot_v2.py` | 296  | 347622073355  |
| 前置相机序列号 | `safe_record_lerobot_v2.py` | 300  | 346522074669  |
| 顶部相机序列号 | `safe_record_lerobot_v2.py` | 304  | 406122070147  |
| CAN 端口       | `safe_record_lerobot_v2.py` | 311  | can0          |
| 主臂串口       | `safe_record_lerobot_v2.py` | 319  | /dev/ttyACM2  |
| 电机 ID        | `safe_record_lerobot_v2.py` | 320  | [1,2,3,4,5,6] |
| 夹爪 ID        | `safe_record_lerobot_v2.py` | 321  | 7             |

---

## 控制命令

### LeRobot 标准键盘控制

在 `safe_record_lerobot.py` 中使用（不推荐，功能有限）：

- **→ (右箭头)** - 提前退出当前 episode（保存并继续下一轮）
- **← (左箭头)** - 重新录制上一个 episode
- **Esc (退出键)** - 停止录制

### 文件控制系统（推荐）

在 `safe_record_lerobot_v2.py` + `record_control.py` 中使用：

| 命令 | 功能             | 说明                         |
| ---- | ---------------- | ---------------------------- |
| `s`  | 保存当前 episode | 结束当前 episode，开始下一个 |
| `e`  | 保存并退出录制   | 完全退出录制程序             |
| `q`  | 退出控制程序     | 不影响录制，只退出控制界面   |

### 控制文件位置

控制系统通过以下文件通信：

- `/tmp/lerobot_control/save_episode` - 保存 episode 标志
- `/tmp/lerobot_control/exit_recording` - 退出录制标志

---

## 常见问题

### Q1: 启动时提示 "CAN 总线未找到"

**解决方案**:

```bash
# 检查 CAN 设备
ip link show can0

# 如果不存在，设置 CAN 总线
sudo ip link set can0 type can bitrate 1000000
sudo ip link set up can0
```

### Q2: 启动时提示 "主臂串口未找到"

**解决方案**:

```bash
# 查看可用串口
ls /dev/ttyACM*

# 如果串口号不同，修改配置文件
# 编辑 safe_record_lerobot_v2.py 第 319 行
```

### Q3: 相机无法连接

**解决方案**:

```bash
# 检查相机连接
rs-enumerate-devices

# 查看相机序列号
python3 detect_realsense_cameras.py

# 如果序列号不匹配，修改配置文件
# 编辑 safe_record_lerobot_v2.py 第 296、300、304 行
```

### Q4: 从臂不跟随主臂运动

**可能原因**:

1. 未等待零位对齐完成（等待 "✓ 零位已记录" 提示）
2. 主臂初始位置与从臂差异过大
3. 关节限位保护触发

**解决方案**:

- 重启程序，确保启动时主臂静止
- 调整主臂初始位置，使其接近从臂当前位置
- 检查终端输出的限位警告信息

### Q5: 录制的数据在哪里？

**数据位置**:

```
/home/dora/lerobot/data/lerobot/arx_safe_test/
```

**数据结构**:

- `data/chunk-*/file-*.parquet` - 机器人状态数据
- `videos/observation.images.*/chunk-*/file-*.mp4` - 视频数据
- `meta_data/` - 元数据

### Q6: 如何查看录制的数据？

**方法 1: 使用 LeRobot 可视化工具**:

```bash
python -m lerobot.scripts.lerobot_dataset_viz \
    --repo-id lerobot/arx_safe_test \
    --root ./data
```

**方法 2: 直接读取 Parquet 文件**:

```python
import pandas as pd
import pyarrow.parquet as pq

# 读取数据
table = pq.read_table("data/chunk-000/file-000.parquet")
df = table.to_pandas()
print(df.head())
```

### Q7: 控制命令没有响应

**检查**:

1. 确认使用的是 `safe_record_lerobot_v2.py`（不是 v1）
2. 确认 `record_control.py` 正在运行
3. 检查 `/tmp/lerobot_control/` 目录是否存在

**解决方案**:

```bash
# 手动创建控制目录
mkdir -p /tmp/lerobot_control

# 重启录制程序
```

### Q8: 如何修改录制时长？

**修改配置**:
编辑 `safe_record_lerobot_v2.py` 第 281 行：

```python
EPISODE_TIME_SEC = 300  # 改为你想要的秒数
```

### Q9: 如何修改数据保存路径？

**修改配置**:
编辑 `safe_record_lerobot_v2.py` 第 284 行：

```python
HF_REPO_ID = "lerobot/arx_safe_test"  # 改为你的路径
```

数据会保存在：`/home/dora/lerobot/data/{HF_REPO_ID}/`

---

## 附录

### 相关脚本文件

| 文件名                        | 用途       | 位置                  |
| ----------------------------- | ---------- | --------------------- |
| `safe_record_lerobot_v2.py`   | 主录制脚本 | `/home/dora/lerobot/` |
| `record_control.py`           | 控制脚本   | `/home/dora/lerobot/` |
| `start_safe_record.sh`        | 启动脚本   | `/home/dora/lerobot/` |
| `detect_realsense_cameras.py` | 相机检测   | `/home/dora/lerobot/` |
| `scan_feetech_motors.py`      | 电机扫描   | `/home/dora/lerobot/` |

### 环境变量

录制系统需要以下环境变量（`start_safe_record.sh` 会自动设置）：

```bash
export PYTHONPATH=/home/dora/lerobot/src:$PYTHONPATH
export LD_LIBRARY_PATH=/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python/bimanual/lib/arx_x5_src:...
```

### 标定文件

主臂标定文件：`/home/dora/lerobot/LeaderX5.json`

**注意**: 配置中的 `id="LeaderX5"` 必须与标定文件名匹配。

---

## 更新日志

- **2026-02-09**: 创建文档，整理数据采集流程和硬件配置说明

---

**文档维护**: Dora
**最后更新**: 2026-02-09
