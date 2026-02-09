"""Configuration for ARX-X5 follower robot.

This module defines the configuration dataclass for the ARX-X5 robotic arm
when used as a follower robot in the LeRobot framework.
"""

from dataclasses import dataclass, field

from lerobot.cameras.configs import CameraConfig
from lerobot.robots.robot import RobotConfig


@RobotConfig.register_subclass("arx_follower")
@dataclass
class ARXFollowerConfig(RobotConfig):
    """Configuration for ARX-X5 follower robot.

    The ARX-X5 is a 6-DOF robotic arm with an integrated gripper that communicates
    via CAN bus. This configuration wraps the ARX SDK for use in LeRobot.

    Attributes:
        can_port: CAN interface name (e.g., "can0", "can1")
        arx_type: ARX arm type (0=standard X5, 1=master X5, 2=2025 X5)
        control_dt: Control loop timestep in seconds (default 20Hz)
        max_relative_target: Optional safety limit for action magnitude in radians
        gripper_open_pos: Gripper position when fully open (0-1000 range)
        gripper_close_pos: Gripper position when fully closed (0-1000 range)
        cameras: Dictionary of camera configurations
        disable_torque_on_disconnect: Whether to disable torque on disconnect
            (ARX uses gravity compensation mode by default)
        arx_sdk_path: Path to ARX SDK installation directory
    """

    # CAN configuration
    can_port: str = "can0"
    arx_type: int = 0  # 0=standard X5, 1=master X5, 2=2025 X5

    # Control parameters
    control_dt: float = 0.05  # 20Hz default
    max_relative_target: float | None = None  # Safety limit for action magnitude

    # Gripper configuration
    gripper_open_pos: int = 1000
    gripper_close_pos: int = 0

    # Camera configuration
    cameras: dict[str, CameraConfig] = field(default_factory=dict)

    # Connection behavior
    disable_torque_on_disconnect: bool = False  # ARX uses gravity compensation mode

    # ARX SDK path
    arx_sdk_path: str = "/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python"
