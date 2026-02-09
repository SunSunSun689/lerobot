#!/bin/bash
# 安全遥操作系统启动脚本 v2.0
# 基于 DoRobot-vr 实现

set -e

echo "=========================================="
echo "安全遥操作系统 v2.0"
echo "基于 DoRobot-vr 实现"
echo "=========================================="
echo ""

# 切换到项目目录
cd /home/dora/lerobot

# 设置 PYTHONPATH
export PYTHONPATH=/home/dora/lerobot/src:$PYTHONPATH

# 设置 ARX SDK 库路径
ARX_SDK_PATH="/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
export LD_LIBRARY_PATH="${ARX_SDK_PATH}/bimanual/lib/arx_x5_src:${ARX_SDK_PATH}/bimanual/lib:${ARX_SDK_PATH}/bimanual/api/arx_x5_src:${ARX_SDK_PATH}/bimanual/api:${LD_LIBRARY_PATH}"

# 检查硬件连接
echo "检查硬件连接..."
echo ""

# 检查 CAN 总线
if ip link show can0 &>/dev/null; then
    echo "✓ CAN 总线 (can0) 已连接"
else
    echo "✗ CAN 总线 (can0) 未找到"
    exit 1
fi

# 检查主臂串口
if [ -e /dev/ttyACM2 ]; then
    echo "✓ 主臂串口 (/dev/ttyACM2) 已连接"
else
    echo "✗ 主臂串口 (/dev/ttyACM2) 未找到"
    exit 1
fi

echo ""
echo "硬件检查完成！"
echo ""
echo "=========================================="
echo "安全机制说明"
echo "=========================================="
echo ""
echo "1. 零位对齐"
echo "   - 启动后等待10帧记录初始位置"
echo "   - 所有运动都是相对于初始位置的"
echo "   - 避免启动时的突然跳跃"
echo ""
echo "2. 低通滤波"
echo "   - 平滑关节运动"
echo "   - 不同关节使用不同截止频率"
echo "   - 基座2Hz，腕部5Hz"
echo ""
echo "3. 死区过滤"
echo "   - 忽略小于阈值的变化"
echo "   - 减少抖动和噪声"
echo ""
echo "4. 软限位保护"
echo "   - 限制关节在安全范围内"
echo "   - 防止超出机械限位"
echo ""
echo "=========================================="
echo "启动遥操作..."
echo "=========================================="
echo ""
echo "⚠️  重要提示："
echo "  - 启动后请保持主臂静止10帧（约0.5秒）"
echo "  - 等待看到 '✓ 零位已记录' 后再移动"
echo "  - 请缓慢移动主臂测试"
echo ""
echo "按 Ctrl+C 停止遥操作"
echo ""

# 运行安全遥操作系统
python3 teleoperate_safe_v2.py

echo ""
echo "=========================================="
echo "遥操作已停止"
echo "=========================================="
