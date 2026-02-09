#!/bin/bash
# 安全遥操作 + LeRobot 数据录制 - 一键启动脚本
# 自动设置环境变量并启动录制

set -e  # 遇到错误立即退出

echo "=========================================="
echo "安全遥操作 + LeRobot 数据录制"
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
if [ -e /dev/ttyACM0 ]; then
    echo "✓ 主臂串口 (/dev/ttyACM0) 已连接"
else
    echo "✗ 主臂串口 (/dev/ttyACM0) 未找到"
    exit 1
fi

# 检查 RealSense 相机
CAMERA_COUNT=$(rs-enumerate-devices 2>/dev/null | grep -c "Serial Number" || echo "0")
if [ "$CAMERA_COUNT" -ge 3 ]; then
    echo "✓ RealSense 相机已连接 ($CAMERA_COUNT 个)"
else
    echo "⚠ RealSense 相机数量不足 (检测到 $CAMERA_COUNT 个，需要 3 个)"
fi

echo ""
echo "硬件检查完成！"
echo ""
echo "=========================================="
echo "启动安全遥操作录制..."
echo "=========================================="
echo ""
echo "录制配置:"
echo "  - 时长: 20秒"
echo "  - 帧率: 30 FPS"
echo "  - 相机: 3个 RealSense"
echo "  - 数据格式: LeRobot 标准格式 (Parquet + 视频)"
echo "  - 安全机制: 零位对齐 + 低通滤波 + 软限位"
echo ""
echo "⚠️  重要提示："
echo "  启动后请保持主臂静止约0.5秒"
echo "  等待 '✓ 零位已记录' 提示后再移动主臂"
echo ""
echo "按 Ctrl+C 停止录制"
echo ""

# 运行安全遥操作录制系统（LeRobot 格式 + 安全功能）
python3 safe_record_lerobot_v2.py

echo ""
echo "=========================================="
echo "录制已停止"
echo "=========================================="
