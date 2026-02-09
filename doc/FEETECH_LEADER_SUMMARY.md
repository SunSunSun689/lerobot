# Feetech 主臂集成总结

## 概述

成功将 Feetech STS3215 主臂集成到 LeRobot 框架中，可以与 ARX-X5 从臂配合使用进行遥操作。

## 实现内容

### 1. 核心文件

#### 配置类

- **文件**: `src/lerobot/teleoperators/feetech_leader/config_feetech_leader.py`
- **类**: `FeetechLeaderConfig`
- **功能**:
  - 配置串口端口（默认 /dev/ttyACM0）
  - 配置电机 ID（6 个关节 + 1 个夹爪）
  - 配置归一化模式（角度或 -100~100 范围）
  - 配置电机型号（默认 sts3215）

#### 主臂类

- **文件**: `src/lerobot/teleoperators/feetech_leader/feetech_leader.py`
- **类**: `FeetechLeader`
- **功能**:
  - 连接到 Feetech 电机总线
  - 读取主臂关节位置
  - 支持校准
  - 实现 Teleoperator 接口

#### 模块导出

- **文件**: `src/lerobot/teleoperators/feetech_leader/__init__.py`
- **导出**: `FeetechLeader`, `FeetechLeaderConfig`

#### 注册

- **文件**: `src/lerobot/teleoperators/__init__.py`
- **修改**: 添加 Feetech 主臂导出

### 2. 硬件配置

#### 发现的电机

- **数量**: 7 个 STS3215 电机
- **ID**: 1, 2, 3, 4, 5, 6, 7
- **型号编号**: 777 (STS3215)
- **波特率**: 1000000
- **串口**: /dev/ttyACM0

#### 电机分配

- **关节 0-5**: 电机 ID 1-6（6 自由度机械臂）
- **夹爪**: 电机 ID 7

### 3. 校准文件

#### 原始校准文件

- **位置**: `/home/dora/DoRobot-vr/operating_platform/robot/components/arm_normal_so101_v1/.calibration/SO101-leader.json`
- **电机 ID**: 0-6（原始）

#### 适配后的校准文件

- **位置**: `/home/dora/.cache/huggingface/lerobot/calibration/teleoperators/feetech_leader/feetech_leader_default.json`
- **电机 ID**: 1-7（适配后）
- **内容**: 包含每个电机的 homing_offset, range_min, range_max

### 4. 测试脚本

#### 电机扫描

- **文件**: `scan_feetech_motors.py`
- **功能**: 扫描串口上的 Feetech 电机

#### STS3215 测试

- **文件**: `test_sts3215.py`
- **功能**: 使用底层 SDK 测试 STS3215 连接

#### 主臂测试

- **文件**: `test_feetech_leader.py`
- **功能**: 测试 FeetechLeader 类的基本功能
- **状态**: ✅ 测试通过

#### 校准脚本

- **文件**: `calibrate_feetech_leader.py`
- **功能**: 交互式校准主臂

#### 遥操作演示

- **文件**: `teleoperate_demo.py`
- **功能**: 演示主臂控制从臂的遥操作

## 使用方法

### 基本使用

```python
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig

# 创建配置
config = FeetechLeaderConfig(
    port="/dev/ttyACM0",
    motor_ids=[1, 2, 3, 4, 5, 6],
    gripper_id=7,
    id="feetech_leader_default",
)

# 使用主臂
with FeetechLeader(config) as leader:
    # 读取位置
    obs = leader.get_observation()
    print(f"关节位置: {obs}")
```

### 与 ARX 从臂配合使用

```python
from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig

# 配置主臂和从臂
leader_config = FeetechLeaderConfig(
    port="/dev/ttyACM0",
    motor_ids=[1, 2, 3, 4, 5, 6],
    gripper_id=7,
    id="feetech_leader_default",
)

follower_config = ARXFollowerConfig(can_port="can0")

# 连接
with FeetechLeader(leader_config) as leader, \
     ARXFollower(follower_config) as follower:

    while True:
        # 读取主臂位置
        leader_obs = leader.get_observation()

        # 映射到从臂动作（需要根据实际情况调整映射）
        follower_action = map_leader_to_follower(leader_obs)

        # 发送到从臂
        follower.send_action(follower_action)
```

### 使用 LeRobot CLI

```bash
# 使用遥操作录制数据
lerobot-teleoperate \
    --leader-type feetech_leader \
    --leader-config '{"port": "/dev/ttyACM0", "id": "feetech_leader_default"}' \
    --follower-type arx_follower \
    --follower-config '{"can_port": "can0"}'
```

## 观测空间

主臂提供以下观测：

- `joint_0.pos` 到 `joint_5.pos`: 关节位置（-100 到 100 范围）
- `gripper.pos`: 夹爪位置（0 到 100 范围）

## 配置选项

### FeetechLeaderConfig

| 参数              | 类型      | 默认值         | 描述                                     |
| ----------------- | --------- | -------------- | ---------------------------------------- |
| `port`            | str       | "/dev/ttyACM0" | 串口端口                                 |
| `use_degrees`     | bool      | False          | 是否使用角度（False 使用 -100~100 范围） |
| `motor_ids`       | list[int] | [1,2,3,4,5,6]  | 关节电机 ID                              |
| `gripper_id`      | int       | 7              | 夹爪电机 ID                              |
| `motor_model`     | str       | "sts3215"      | 电机型号                                 |
| `id`              | str       | None           | 校准文件 ID                              |
| `calibration_dir` | Path      | None           | 校准文件目录                             |

## 测试结果

### ✅ 已完成

- 电机扫描和识别
- 主臂连接
- 位置读取
- 校准文件加载
- 基本功能测试

### ⏳ 待测试（需要硬件）

- 与 ARX 从臂的实际遥操作
- 数据录制
- 数据回放
- 长时间稳定性测试

## 文件结构

```
src/lerobot/teleoperators/feetech_leader/
├── __init__.py                      (导出)
├── config_feetech_leader.py         (配置类)
└── feetech_leader.py                (主臂类)

src/lerobot/teleoperators/
└── __init__.py                      (已修改，添加注册)

测试和示例脚本:
├── scan_feetech_motors.py           (扫描电机)
├── test_sts3215.py                  (底层测试)
├── test_feetech_leader.py           (主臂测试 ✅)
├── calibrate_feetech_leader.py      (校准脚本)
└── teleoperate_demo.py              (遥操作演示)

校准文件:
└── ~/.cache/huggingface/lerobot/calibration/teleoperators/feetech_leader/
    └── feetech_leader_default.json  (校准数据)
```

## 注意事项

### 坐标映射

主臂和从臂使用不同的坐标系统：

- **主臂**: -100 到 100 范围（归一化）
- **从臂**: 弧度制（-π 到 π）

需要根据实际机械臂配置进行适当的映射和缩放。

### 夹爪映射

- **主臂夹爪**: 0 到 100 范围
- **从臂夹爪**: 0 到 1000 范围

简单的线性映射：`follower_gripper = leader_gripper * 10`

### 控制频率

建议使用 20Hz 控制频率（每 50ms 一次循环）。

### 安全注意事项

1. 首次使用时，建议在安全环境中测试
2. 确保主臂和从臂的运动范围不会发生碰撞
3. 准备好紧急停止按钮
4. 从小幅度运动开始测试

## 下一步

1. **测试遥操作**: 运行 `teleoperate_demo.py` 测试主从臂配合
2. **调整映射**: 根据实际效果调整关节映射关系
3. **录制数据**: 使用 `lerobot-record` 录制演示数据
4. **训练策略**: 使用录制的数据训练机器人策略

## 故障排除

### 找不到电机

- 检查串口连接：`ls -l /dev/ttyACM0`
- 检查电机是否上电
- 运行 `python3 scan_feetech_motors.py` 扫描

### 校准错误

- 确保校准文件存在：`~/.cache/huggingface/lerobot/calibration/teleoperators/feetech_leader/feetech_leader_default.json`
- 检查电机 ID 是否匹配（1-7）

### 权限错误

```bash
sudo chmod 666 /dev/ttyACM0
# 或
sudo usermod -a -G dialout $USER
```

## 参考

- Feetech SDK: feetech-servo-sdk
- LeRobot Teleoperator 基类: `src/lerobot/teleoperators/teleoperator.py`
- SO Leader 参考实现: `src/lerobot/teleoperators/so_leader/`
- ARX Follower 实现: `src/lerobot/robots/arx_follower/`
