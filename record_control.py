#!/usr/bin/env python3
"""录制控制脚本 - 在另一个终端运行，发送控制指令"""

import sys
from pathlib import Path

CONTROL_DIR = Path("/tmp/lerobot_control")
CONTROL_DIR.mkdir(exist_ok=True)

SAVE_FLAG = CONTROL_DIR / "save_episode"
EXIT_FLAG = CONTROL_DIR / "exit_recording"

def show_menu():
    print("=" * 60)
    print("LeRobot 录制控制")
    print("=" * 60)
    print()
    print("可用命令:")
    print("  s - 保存当前 episode")
    print("  e - 保存并退出录制")
    print("  q - 退出控制程序（不影响录制）")
    print()

def send_command(cmd):
    if cmd == 's':
        SAVE_FLAG.touch()
        print("✓ 已发送保存指令")
    elif cmd == 'e':
        EXIT_FLAG.touch()
        print("✓ 已发送退出指令")
    elif cmd == 'q':
        print("退出控制程序")
        sys.exit(0)
    else:
        print("✗ 未知命令")

def main():
    show_menu()

    print("等待输入命令...")
    print()

    try:
        while True:
            cmd = input("命令 [s/e/q]: ").strip().lower()
            send_command(cmd)
            print()
    except KeyboardInterrupt:
        print("\n退出控制程序")
    except EOFError:
        print("\n退出控制程序")

if __name__ == "__main__":
    main()
