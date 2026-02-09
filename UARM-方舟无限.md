# u-ARM-config2（主臂)+ 方舟无限ARX-X5（丛臂）(仅一次采集)

## 运行环境准备
- 参考https://github.com/huggingface/lerobot.git

## 硬件准备
- 三个realsense相机，uarm主臂，ARX-X5丛臂，拓展坞
- top 相机直连电脑，其他全插入拓展坞
# 激活丛臂
根据sdk中的方法，开启丛臂的can通信，默认can0
## 运行数据保存文件
```bash
cd /home/dora/lerobot
python3 record_control.py
```
在终端 2 输入命令：
- 输入 `s` + Enter → 保存当前 episode，开始下一个
- 输入 `e` + Enter → 保存并退出录制
- 输入 `q` + Enter → 退出控制程序


## 执行遥操
- 给主臂串口加上权限
```bash
sudo chmod 777 /dev/ttyACM*
conda activate lerobot
cd /home/dora/lerobot
bash start_safe_record.sh
```
- 遥操tips1:joint0和joint3做了位置偏置，开始遥操后，会运动到指定的位置。主臂joint3（90度）与丛臂joint3（180度）运动范围相差大，主臂的中心值映射为丛臂的中心值，为了安全启动，在joint0开始运动的同时，把主臂抬高并向前。留给joint3安全运动的空间。
- 完成一轮数据采集后，根据丛臂的位置运动主臂。丛臂归位后主臂的joint3有角度。
- 摁 e,结束本次采集并保存数据
# 数据格式转换 
```bash
python3 convert_lerobot_to_delivery.py
```
- 根据需要修改数据输入的位置，默认/lerobot/data
