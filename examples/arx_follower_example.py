#!/usr/bin/env python3
"""Example usage of ARX-X5 follower robot.

This script demonstrates how to use the ARXFollower class for basic robot control.

Requirements:
- ARX SDK installed
- CAN bus configured and accessible
- ARX-X5 arm connected and powered on
"""

import time
from pathlib import Path

from lerobot.cameras.configs import CameraConfig
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig


def example_basic_control():
    """Example: Basic robot control without cameras."""
    print("=" * 60)
    print("Example 1: Basic Control")
    print("=" * 60)

    config = ARXFollowerConfig(
        can_port="can0",
        arx_type=0,
        control_dt=0.05,
    )

    with ARXFollower(config) as robot:
        print("Robot connected!")

        # Get initial observation
        obs = robot.get_observation()
        print(f"\nInitial joint positions (radians):")
        for i in range(6):
            print(f"  Joint {i}: {obs[f'joint_{i}.pos']:.3f}")
        print(f"  Gripper: {obs['gripper.pos']:.0f}")

        # Move to home position (all zeros)
        print("\nMoving to home position...")
        action = {
            "joint_0.pos": 0.0,
            "joint_1.pos": 0.0,
            "joint_2.pos": 0.0,
            "joint_3.pos": 0.0,
            "joint_4.pos": 0.0,
            "joint_5.pos": 0.0,
            "gripper.pos": 500.0,
        }
        robot.send_action(action)
        time.sleep(2.0)

        # Get final observation
        obs = robot.get_observation()
        print(f"\nFinal joint positions (radians):")
        for i in range(6):
            print(f"  Joint {i}: {obs[f'joint_{i}.pos']:.3f}")


def example_with_camera():
    """Example: Robot control with camera."""
    print("\n" + "=" * 60)
    print("Example 2: With Camera")
    print("=" * 60)

    config = ARXFollowerConfig(
        can_port="can0",
        cameras={
            "camera_wrist": CameraConfig(
                type="realsense",
                serial_number="your_serial_here",  # Replace with your serial
                width=640,
                height=480,
                fps=30,
            )
        }
    )

    with ARXFollower(config) as robot:
        print("Robot and camera connected!")

        # Get observation with camera
        obs = robot.get_observation()
        print(f"\nObservation keys: {list(obs.keys())}")
        print(f"Camera image shape: {obs['camera_wrist'].shape}")


def example_with_safety_limits():
    """Example: Robot control with safety limits."""
    print("\n" + "=" * 60)
    print("Example 3: With Safety Limits")
    print("=" * 60)

    config = ARXFollowerConfig(
        can_port="can0",
        max_relative_target=0.1,  # Limit to 0.1 rad per action
    )

    with ARXFollower(config) as robot:
        print("Robot connected with safety limits!")

        # Get current position
        obs = robot.get_observation()
        current_pos = obs["joint_0.pos"]
        print(f"\nCurrent joint 0 position: {current_pos:.3f} rad")

        # Try to move by large amount (will be clamped)
        large_target = current_pos + 1.0  # 1 radian change
        print(f"Requesting large move to: {large_target:.3f} rad")

        action = {
            "joint_0.pos": large_target,
            "joint_1.pos": obs["joint_1.pos"],
            "joint_2.pos": obs["joint_2.pos"],
            "joint_3.pos": obs["joint_3.pos"],
            "joint_4.pos": obs["joint_4.pos"],
            "joint_5.pos": obs["joint_5.pos"],
            "gripper.pos": obs["gripper.pos"],
        }

        actual_action = robot.send_action(action)
        print(f"Actual target sent: {actual_action['joint_0.pos']:.3f} rad")
        print(f"(Clamped to {current_pos + 0.1:.3f} rad due to safety limit)")


def example_gripper_control():
    """Example: Gripper control."""
    print("\n" + "=" * 60)
    print("Example 4: Gripper Control")
    print("=" * 60)

    config = ARXFollowerConfig(
        can_port="can0",
        gripper_open_pos=1000,
        gripper_close_pos=0,
    )

    with ARXFollower(config) as robot:
        print("Robot connected!")

        # Get current state
        obs = robot.get_observation()
        joint_positions = {f"joint_{i}.pos": obs[f"joint_{i}.pos"] for i in range(6)}

        # Open gripper
        print("\nOpening gripper...")
        action = {**joint_positions, "gripper.pos": 1000.0}
        robot.send_action(action)
        time.sleep(1.0)

        # Close gripper
        print("Closing gripper...")
        action = {**joint_positions, "gripper.pos": 0.0}
        robot.send_action(action)
        time.sleep(1.0)

        # Half open
        print("Half opening gripper...")
        action = {**joint_positions, "gripper.pos": 500.0}
        robot.send_action(action)
        time.sleep(1.0)


def main():
    """Run all examples."""
    print("\nARX-X5 Follower Robot Examples")
    print("=" * 60)
    print("\nNote: These examples require:")
    print("  1. ARX SDK installed")
    print("  2. CAN bus configured (can0)")
    print("  3. ARX-X5 arm connected and powered on")
    print("\nPress Ctrl+C to stop at any time.")
    print()

    try:
        # Run examples
        example_basic_control()

        # Uncomment to run other examples:
        # example_with_camera()
        # example_with_safety_limits()
        # example_gripper_control()

        print("\n" + "=" * 60)
        print("Examples completed successfully!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
