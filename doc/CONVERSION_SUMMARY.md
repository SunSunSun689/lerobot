# LeRobot数据格式转换总结

## 转换完成 ✓

已成功将LeRobot格式数据转换为交付标准的JSONL格式。

## 转换脚本

**脚本位置**: `/home/dora/lerobot/convert_lerobot_to_delivery.py`

### 使用方法

```bash
# 使用默认路径
python3 convert_lerobot_to_delivery.py

# 自定义输入输出路径
python3 convert_lerobot_to_delivery.py \
  --input /path/to/lerobot/data \
  --output /path/to/output \
  --task-name my_task_name
```

### 默认参数

- **输入目录**: `/home/dora/lerobot/data`
- **输出目录**: `/home/dora/lerobot/data-converted`
- **任务名称**: `leader_follower_x5`

## 输入格式 (LeRobot)

```
data/
├── data/
│   └── chunk-000/
│       └── file-000.parquet
├── videos/
│   ├── observation.images.top/
│   │   └── chunk-000/
│   │       └── file-000.mp4
│   ├── observation.images.wrist/
│   │   └── chunk-000/
│   │       └── file-000.mp4
│   └── observation.images.front/
│       └── chunk-000/
│           └── file-000.mp4
└── meta/
    └── info.json
```

## 输出格式 (交付标准)

```
data-converted/
├── task_desc.json
├── meta/
│   └── task_info.json
└── data/
    └── episode_000000/
        ├── meta/
        │   └── episode_meta.json
        ├── states/
        │   └── states.jsonl
        └── videos/
            ├── global_realsense_rgb.mp4
            ├── arm_realsense_rgb.mp4
            └── front_realsense_rgb.mp4
```

## 转换结果验证

### Episode 000000

- **帧数**: 3595帧
- **时长**: 119.8秒
- **帧率**: 30 FPS
- **states.jsonl**: 3595行 (每帧一行)

### 视频文件

| 原始名称                 | 转换后名称               | 大小 |
| ------------------------ | ------------------------ | ---- |
| observation.images.top   | global_realsense_rgb.mp4 | 11M  |
| observation.images.wrist | arm_realsense_rgb.mp4    | 11M  |
| observation.images.front | front_realsense_rgb.mp4  | 12M  |

### states.jsonl 数据格式

每行包含以下字段:

```json
{
  "joint_positions": [6个关节位置],
  "joint_velocities": [6个关节速度],
  "end_effector_pose": [末端执行器位姿 x,y,z,rx,ry,rz],
  "gripper_width": 夹爪宽度,
  "gripper_velocity": 夹爪速度,
  "timestamp": 时间戳
}
```

## 关键特性

1. **自动episode分组**: 从LeRobot的单文件格式中按`episode_index`自动分组
2. **FK计算**: 使用正运动学计算器计算末端执行器位姿
3. **速度计算**: 从相邻帧的位置差和时间差计算关节速度和夹爪速度
4. **帧率计算**: 从时间戳自动计算实际帧率
5. **相机映射**:
   - top → global_realsense_rgb.mp4
   - wrist → arm_realsense_rgb.mp4
   - front → front_realsense_rgb.mp4

## 注意事项

- FK计算器需要在`/home/dora/DoRobot-vr/scripts/fk_calculator.py`
- 如果FK计算器不可用，会使用占位符`[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]`
- 所有数值都转换为Python原生类型以确保JSON序列化兼容性

## 下一步

转换后的数据可以直接用于:

- 模型训练
- 数据分析
- 可视化工具
- 交付给其他团队
