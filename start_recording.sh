#!/bin/bash
# LeRobot 数据录制启动脚本
# ARX-X5 + Feetech Leader + 3 RealSense 相机

set -e

echo "=========================================="
echo "LeRobot 数据录制系统"
echo "=========================================="
echo ""

# 切换到项目目录
cd /home/dora/lerobot

# 设置环境变量
export PYTHONPATH=/home/dora/lerobot/src:$PYTHONPATH

# 设置 ARX SDK 库路径
ARX_SDK_PATH="/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
export LD_LIBRARY_PATH="${ARX_SDK_PATH}/bimanual/lib/arx_x5_src:${ARX_SDK_PATH}/bimanual/lib:${ARX_SDK_PATH}/bimanual/api/arx_x5_src:${ARX_SDK_PATH}/bimanual/api:${LD_LIBRARY_PATH}"

# 检查硬件连接
echo "检查硬件连接..."
echo ""

if ip link show can0 &>/dev/null; then
    echo "✓ CAN 总线 (can0) 已连接"
else
    echo "✗ CAN 总线 (can0) 未找到"
    exit 1
fi

if [ -e /dev/ttyACM2 ]; then
    echo "✓ 主臂串口 (/dev/ttyACM2) 已连接"
else
    echo "✗ 主臂串口 (/dev/ttyACM2) 未找到"
    exit 1
fi

CAMERA_COUNT=$(rs-enumerate-devices 2>/dev/null | grep -c "Serial Number" || echo "0")
if [ "$CAMERA_COUNT" -ge 3 ]; then
    echo "✓ RealSense 相机已连接 ($CAMERA_COUNT 个)"
else
    echo "⚠ RealSense 相机数量不足 (检测到 $CAMERA_COUNT 个，需要 3 个)"
fi

echo ""
echo "硬件检查完成！"
echo ""

# 显示配置信息
echo "=========================================="
echo "录制配置"
echo "=========================================="
echo ""
echo "从臂: ARX-X5 (CAN: can0)"
echo "主臂: Feetech Leader (/dev/ttyACM2)"
echo "相机:"
echo "  - wrist: 346522074669"
echo "  - front: 347622073355"
echo "  - top:   406122070147"
echo ""
echo "数据集配置:"
echo "  - 查看/编辑: record_config.yaml"
echo ""

# 询问是否修改配置
read -p "是否需要修改配置? (y/n, 默认n): " modify_config
if [ "$modify_config" = "y" ] || [ "$modify_config" = "Y" ]; then
    echo ""
    echo "请编辑 record_config.yaml 文件，然后重新运行此脚本"
    echo "主要配置项:"
    echo "  - dataset.repo_id: 数据集名称 (格式: 用户名/数据集名)"
    echo "  - dataset.num_episodes: 录制的episode数量"
    echo "  - dataset.single_task: 任务描述"
    exit 0
fi

echo ""
echo "=========================================="
echo "开始录制"
echo "=========================================="
echo ""
echo "操作说明:"
echo "  1. 每个episode开始时会提示"
echo "  2. 移动主臂进行遥操作"
echo "  3. 按 Ctrl+C 结束当前episode"
echo "  4. 系统会提示重置环境"
echo "  5. 重复直到完成所有episodes"
echo ""
echo "数据保存位置:"
echo "  ~/.cache/huggingface/lerobot/datasets/"
echo ""
read -p "按 Enter 开始录制..."

# 运行 lerobot-record
python3 -m lerobot.scripts.lerobot_record --config record_config.yaml

echo ""
echo "=========================================="
echo "录制完成"
echo "=========================================="
echo ""
echo "数据已保存到:"
echo "  ~/.cache/huggingface/lerobot/datasets/"
echo ""
echo "查看数据集:"
echo "  lerobot-visualize --repo-id <your_dataset_name>"
echo ""
