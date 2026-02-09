# 安全录制系统使用指南

## ✅ 安全特性

### 1. 零位对齐
- 启动后等待 10 帧（约 0.5 秒）记录初始位置
- 所有运动都是相对于初始位置的
- **避免启动时的突然跳跃**

### 2. 低通滤波
- 平滑关节运动，避免抖动
- 不同关节使用不同截止频率：
  - joint_0 (基座): 2 Hz
  - joint_1 (肩部): 3 Hz
  - joint_2 (肘部): 4 Hz
  - joint_3-5 (腕部): 5 Hz

### 3. 软限位保护
- 限制关节在安全范围内
- 防止超出机械限位
- 限位范围：
  - joint_0: -140° 到 170°
  - joint_1: -5° 到 200°
  - joint_2: -5° 到 170°
  - joint_3: -70° 到 70°
  - joint_4: -80° 到 80°
  - joint_5: -95° 到 95°

### 4. 方向映射
- joint_0 (底座): 正常方向
- joint_1 (肩部): **反向** (主臂向上 → 从臂向下)
- joint_2-5: 正常方向

## 🚀 使用方法

### 启动录制
```bash
cd /home/dora/lerobot
bash start_safe_record.sh
```

### 操作步骤
1. **启动脚本** - 等待硬件连接
2. **保持静止** - 启动后保持主臂静止约 0.5 秒
3. **等待提示** - 看到 "✓ 零位已记录" 后再移动
4. **开始遥操作** - 缓慢移动主臂测试
5. **自动停止** - 20 秒后自动停止并保存数据

### 手动停止
按 `Ctrl+C` 可以随时停止录制

## 📦 数据保存

### 保存位置
```
/home/dora/lerobot/recordings/safe_YYYYMMDD_HHMMSS/
├── wrist.mp4           # 手腕相机视频 (30 FPS)
├── front.mp4           # 前置相机视频 (30 FPS)
├── top.mp4             # 顶部相机视频 (30 FPS)
└── robot_states.csv    # 机器人状态数据
```

### CSV 数据格式
```csv
timestamp,frame,leader_j0,leader_j1,...,follower_j0,follower_j1,...
0.033,0,50.2,30.1,...,0.52,1.45,...
```

包含：
- 时间戳
- 帧号
- 主臂 6 个关节位置 + 夹爪
- 从臂 6 个关节位置 + 夹爪

## ⚠️ 安全注意事项

### 启动前
1. 确保主臂和从臂都在安全位置
2. 确保周围没有障碍物
3. 准备好紧急停止（Ctrl+C）

### 运行中
1. **启动后立即保持主臂静止 0.5 秒**
2. 等待 "✓ 零位已记录" 提示
3. 缓慢移动主臂测试响应
4. 如果从臂运动异常，立即按 Ctrl+C

### 异常处理
- 如果从臂突然运动 → 立即停止（Ctrl+C）
- 如果看到限位警告 → 减小主臂运动范围
- 如果相机无图像 → 检查相机连接

## 🔧 配置修改

### 修改录制时长
编辑 `safe_record_simple.py`:
```python
system = SafeRecordingSystem(output_dir, duration=20, fps=30)
                                              ↑ 修改这里
```

### 修改滤波器参数
编辑 `safe_record_simple.py` 中的 `lowpass_filters`:
```python
LowPassFilter1D(cutoff_freq=2.0, sample_rate=fps)
                           ↑ 修改截止频率
```

### 修改软限位
编辑 `safe_record_simple.py` 中的 `joint_limits`:
```python
self.joint_limits = [
    (-2.44, 2.97),  # joint_0
    ...
]
```

## 📊 数据分析

### 查看视频
```bash
vlc recordings/safe_YYYYMMDD_HHMMSS/wrist.mp4
```

### 分析帧率
```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=r_frame_rate \
  -of default=noprint_wrappers=1:nokey=1 \
  recordings/safe_YYYYMMDD_HHMMSS/wrist.mp4
```

### 查看 CSV 数据
```bash
head -20 recordings/safe_YYYYMMDD_HHMMSS/robot_states.csv
```

## 🆚 与 LeRobot 版本的对比

| 特性 | 安全版本 (当前) | LeRobot 版本 |
|------|----------------|--------------|
| 零位对齐 | ✅ 有 | ❌ 无 |
| 低通滤波 | ✅ 有 | ❌ 无 |
| 软限位 | ✅ 有 | ❌ 无 |
| 启动安全 | ✅ 无突然运动 | ❌ 会突然运动 |
| 数据格式 | MP4 + CSV | Parquet + 视频 |
| 训练兼容 | 需要转换 | ✅ 直接兼容 |

**结论**: 安全版本优先保证安全性，数据格式可以后期转换。

