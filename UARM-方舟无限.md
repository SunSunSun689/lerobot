# u-ARM-config2（主臂)+ 方舟无限ARX-X5（丛臂）

## 运行环境准备

- 参考https://github.com/huggingface/lerobot.git
- 下载ARX X5的sdk

## 硬件准备

- 三个realsense相机，uarm主臂，ARX-X5丛臂，拓展坞
- 一个相机直连电脑，另外两个插入拓展坞

# 激活丛臂

根据sdk中的方法，开启丛臂的can通信，默认can0

## 运行数据保存文件

```bash
cd /home/dora/lerobot
python3 record_control.py
```
在终端输入命令：
机械臂从零位运动到遥操初始位置之后，自动开始数据录制
- 输入 `s` → 保存当前 episode，机械臂会自动复位，复位环境，等待视频编码完成，终端有提示开始下一轮数据采集
- 输入 `n` → 开启下一轮数据录制
- 输入 `e` → 保存数据并退出录制

## 执行遥操

- 给主臂串口加上权限

```bash
sudo chmod 777 /dev/ttyACM*
cd lerobot
bash start_safe_record.sh
```
- 遥操tips1:遥操开始前，将主臂的第四个关节（运动范围90度）运动到45度【可以找个东西垫一下】，执行代码开始遥操，完成插花后，可以直接摁s键，会断开遥操 + ARX X5会自动复位 + 保存当前episode，把主臂也复位到初始位置【第四个关节保持45度】，复位环境，等待视频编码，根据终端输出，摁n键，开始下一轮数据采集，最后一轮直接摁e即可。
- 遥操tips2:joint0做了偏置，开始遥操后，机械臂会从零位【厂商预设】运动到遥操初始位置。


# 数据格式转换

```bash
python3 convert_devide.py
```
- 根据需要修改数据输入的位置，默认/lerobot/data
