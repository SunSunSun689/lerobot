# LeRobot 数据集架构说明

## 📊 数据集概览

这是一个**机器人遥操作（teleoperation）数据集**，用于记录 Feetech 主臂（leader arm）控制 ARX-X5 从臂（follower arm）的操作数据。

数据集位置：`/home/dora/lerobot/data-converted/`

## 🗂️ 目录结构

```
data-converted/
├── task_desc.json          # 任务描述文件
├── meta/                   # 元数据目录
│   └── task_info.json      # 任务详细信息
└── data/                   # 数据目录
    └── episode_000000/     # 单个操作片段
        ├── meta/           # 片段元数据
        │   └── episode_meta.json
        ├── states/         # 状态数据
        │   └── states.jsonl
        └── videos/         # 视频数据
            ├── arm_realsense_rgb.mp4      (11MB)
            ├── front_realsense_rgb.mp4    (12MB)
            └── global_realsense_rgb.mp4   (11MB)
```

---

## 📄 文件详细说明

### 1. 根目录文件

#### task_desc.json

**作用**: 定义整个数据集的任务类型和标签

**内容结构**:

```json
{
  "task_name": "leader_follower_x5",
  "prompt": "Leader-follower teleoperation with Feetech leader arm and ARX-X5 follower arm",
  "scoring": "Data quality based on smoothness and accuracy of teleoperation",
  "task_tag": ["teleoperation", "leader-follower", "dual-arm", "ARX5"]
}
```

**字段说明**:

- `task_name`: 任务名称标识符
- `prompt`: 任务的自然语言描述
- `scoring`: 数据质量评分标准
- `task_tag`: 任务分类标签数组

---

### 2. meta/ 目录

#### meta/task_info.json

**作用**: 存储任务的技术配置信息和视频编码参数

**内容结构**:

```json
{
  "robot_id": "arx5_leader_follower",
  "task_desc": {
    /* 与 task_desc.json 相同 */
  },
  "video_info": {
    "fps": 30,
    "ext": "mp4",
    "encoding": {
      "vcodec": "libx264",
      "pix_fmt": "yuv420p"
    }
  }
}
```

**字段说明**:

- `robot_id`: 机器人系统标识符
- `task_desc`: 任务描述（与根目录的 task_desc.json 内容一致）
- `video_info`: 视频技术参数
  - `fps`: 帧率（30 帧/秒）
  - `ext`: 视频文件扩展名
  - `encoding`: 编码配置（H.264 编码，YUV420P 像素格式）

---

### 3. data/episode_XXXXXX/ 目录

每个 episode 目录代表一次完整的操作记录。目录名格式为 `episode_` + 6位数字索引。

#### 3.1 meta/episode_meta.json

**作用**: 记录该操作片段的基本信息

**内容结构**:

```json
{
  "episode_index": 0,
  "start_time": 0.0,
  "end_time": 119.80000305175781,
  "frames": 3595
}
```

**字段说明**:

- `episode_index`: 片段索引号
- `start_time`: 开始时间（秒）
- `end_time`: 结束时间（秒）
- `frames`: 总帧数

---

#### 3.2 states/states.jsonl

**作用**: 记录机器人每一帧的状态数据

**格式**: JSONL（JSON Lines），每行一个 JSON 对象

**单帧数据结构**:

```json
{
  "joint_positions": [0.00057, 0.01431, -0.00019, -0.00935, -0.00019, 0.01049],
  "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "end_effector_pose": [0.39997, 0.00023, 0.00474, -0.00019, 0.00477, 0.00057],
  "gripper_width": 0.1648,
  "gripper_velocity": 0.0,
  "timestamp": 0.0
}
```

**字段说明**:

- `joint_positions`: 6个关节的位置 [弧度]
- `joint_velocities`: 6个关节的速度 [弧度/秒]
- `end_effector_pose`: 末端执行器位姿 [x, y, z, rx, ry, rz]
  - x, y, z: 位置坐标 [米]
  - rx, ry, rz: 旋转角度 [弧度]
- `gripper_width`: 夹爪开合宽度 [米]
- `gripper_velocity`: 夹爪运动速度 [米/秒]
- `timestamp`: 时间戳 [秒]

**数据特点**:

- 采样频率: ~30Hz
- 数据量: 每个 episode 包含数千条记录
- 时间同步: 与视频帧时间戳对齐

---

#### 3.3 videos/ 目录

**作用**: 存储多视角同步视频

**视频文件**:

1. **arm_realsense_rgb.mp4** - 手臂视角
   - 拍摄角度: 近距离观察机械臂操作
   - 用途: 捕捉精细动作细节

2. **front_realsense_rgb.mp4** - 正面视角
   - 拍摄角度: 正面观察工作区域
   - 用途: 记录任务执行过程

3. **global_realsense_rgb.mp4** - 全局视角
   - 拍摄角度: 俯视或广角视角
   - 用途: 提供整体场景信息

**视频参数**:

- 分辨率: 由 RealSense 相机配置决定
- 帧率: 30 fps
- 编码: H.264 (libx264)
- 像素格式: YUV420P
- 文件大小: 约 11-12 MB（取决于场景复杂度）

---

## 🎯 数据集用途

### 机器学习应用

1. **模仿学习（Imitation Learning）**
   - 训练机器人学习人类演示的操作轨迹
   - 使用状态-动作对进行监督学习

2. **行为克隆（Behavior Cloning）**
   - 直接学习状态到动作的映射关系
   - 适用于确定性任务

3. **强化学习（Reinforcement Learning）**
   - 作为专家演示数据（Expert Demonstrations）
   - 用于预训练或奖励塑形

4. **视觉-运动控制（Visuomotor Control）**
   - 结合视频和状态数据
   - 训练端到端的视觉伺服控制器

### 研究方向

- 多模态学习（视觉 + 本体感知）
- 时序建模（LSTM, Transformer）
- 扩散策略（Diffusion Policy）
- 视觉表征学习

---

## 📈 数据统计

### 当前数据集（episode_000000）

| 指标       | 数值                  |
| ---------- | --------------------- |
| 总时长     | 119.8 秒（约 2 分钟） |
| 总帧数     | 3595 帧               |
| 采样频率   | ~30 Hz                |
| 视频数量   | 3 个视角              |
| 视频总大小 | ~34 MB                |
| 状态数据量 | 3595 条记录           |

### 数据质量指标

- **时间同步**: 视频帧与状态数据时间戳对齐
- **采样一致性**: 状态数据和视频均为 30Hz
- **多视角覆盖**: 3个不同角度提供全面观察

---

## 🔧 数据格式兼容性

### LeRobot 框架

此数据集格式与 LeRobot 框架完全兼容，可直接用于：

- 数据加载和预处理
- 模型训练和评估
- 可视化和分析工具

### 扩展性

数据集结构支持：

- 添加更多 episode（episode_000001, episode_000002, ...）
- 增加额外的传感器数据（深度图、力传感器等）
- 自定义元数据字段

---

## 📝 使用建议

### 数据加载

```python
import json
import pandas as pd

# 加载任务信息
with open('task_desc.json') as f:
    task_desc = json.load(f)

# 加载状态数据
states = pd.read_json('data/episode_000000/states/states.jsonl', lines=True)

# 加载视频（使用 OpenCV 或其他库）
import cv2
cap = cv2.VideoCapture('data/episode_000000/videos/front_realsense_rgb.mp4')
```

### 数据验证

- 检查时间戳连续性
- 验证关节位置在合理范围内
- 确认视频帧数与状态记录数匹配

### 数据增强

- 时间序列增强（时间扭曲、速度调整）
- 视觉增强（颜色抖动、随机裁剪）
- 噪声注入（传感器噪声模拟）

---

## 🔗 相关文档

- [数据采集指南](./Dora-数据采集.md)
- [相机配置](./CAMERA_SETUP_GUIDE.md)
- [ARX 集成说明](./ARX_INTEGRATION_SUMMARY.md)
- [安全录制指南](./SAFE_RECORDING_GUIDE.md)

---

**文档版本**: 1.0
**最后更新**: 2026-02-09
**维护者**: LeRobot Team
