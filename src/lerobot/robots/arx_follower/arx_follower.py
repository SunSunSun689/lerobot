"""ARX-X5 follower robot implementation for LeRobot.

This module implements the ARXFollower class, which wraps the ARX SDK to provide
a LeRobot-compatible interface for the ARX-X5 robotic arm.
"""

import logging
import os
import sys
from functools import cached_property

import numpy as np

from lerobot.cameras.utils import make_cameras_from_configs
from lerobot.robots.arx_follower.config_arx_follower import ARXFollowerConfig
from lerobot.robots.robot import Robot, RobotAction, RobotObservation

logger = logging.getLogger(__name__)


class ARXFollower(Robot):
    """ARX-X5 follower robot implementation.

    This class wraps the ARX SDK's SingleArm class to provide a LeRobot-compatible
    interface for the ARX-X5 robotic arm. The arm has 6 joints and an integrated
    gripper, and communicates via CAN bus.

    The robot uses radians for joint positions (matching ARX SDK native format)
    and a 0-1000 range for gripper position.

    Example:
        ```python
        from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig

        config = ARXFollowerConfig(
            can_port="can0",
            cameras={
                "camera_wrist": CameraConfig(
                    type="realsense",
                    serial_number="123456789",
                    width=640,
                    height=480,
                )
            }
        )

        with ARXFollower(config) as robot:
            obs = robot.get_observation()
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
        ```

    Note:
        The ARX SDK must be installed and accessible at the path specified in
        the configuration. CAN bus permissions must be properly configured.
    """

    config_class = ARXFollowerConfig
    name = "arx_follower"

    def __init__(self, config: ARXFollowerConfig):
        """Initialize the ARX follower robot.

        Args:
            config: Configuration for the ARX follower robot.
        """
        super().__init__(config)
        self.config = config

        # Setup ARX SDK environment
        sdk_path = config.arx_sdk_path
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)

        # Setup LD_LIBRARY_PATH for ARX shared libraries
        lib_paths = [
            f"{sdk_path}/bimanual/api/arx_x5_src",
            f"{sdk_path}/bimanual/api",
            f"{sdk_path}/bimanual/lib/arx_x5_src",
            f"{sdk_path}/bimanual/lib",
            "/usr/local/lib",
        ]
        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        new_ld_path = ":".join(lib_paths + ([current_ld_path] if current_ld_path else []))
        os.environ["LD_LIBRARY_PATH"] = new_ld_path

        # Import ARX SDK (dynamic import after path setup)
        try:
            from bimanual import SingleArm
        except ImportError as e:
            raise ImportError(
                f"Failed to import ARX SDK from {sdk_path}. "
                f"Please ensure the ARX SDK is installed at the specified path. "
                f"Error: {e}"
            ) from e

        # Initialize ARX arm
        logger.info(f"Initializing ARX-X5 arm on {config.can_port}")
        arx_config = {
            "can_port": config.can_port,
            "arx_type": config.arx_type,
            "num_joints": 7,  # 6 joints + 1 gripper
            "dt": config.control_dt,
        }
        self.arm = SingleArm(arx_config)

        # Initialize cameras
        self.cameras = make_cameras_from_configs(config.cameras)

        # Track last gripper position (in case SDK doesn't provide read method)
        self._last_gripper_pos = config.gripper_open_pos

        # Connection state
        self._is_connected = False

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        """Define the observation space for the ARX follower.

        Returns:
            Dictionary mapping feature names to their types. Includes:
            - 6 joint positions in radians (joint_0.pos through joint_5.pos)
            - Gripper position in 0-1000 range (gripper.pos)
            - Camera images from configured cameras
        """
        features = {
            "joint_0.pos": float,
            "joint_1.pos": float,
            "joint_2.pos": float,
            "joint_3.pos": float,
            "joint_4.pos": float,
            "joint_5.pos": float,
            "gripper.pos": float,
        }

        # Add camera features
        for name, camera in self.cameras.items():
            # RealSense cameras output RGB images (3 channels)
            channels = 3
            features[name] = (camera.height, camera.width, channels)

        return features

    @cached_property
    def action_features(self) -> dict[str, type]:
        """Define the action space for the ARX follower.

        Returns:
            Dictionary mapping action feature names to their types. Includes:
            - 6 joint position targets in radians
            - Gripper position target in 0-1000 range
        """
        return {
            "joint_0.pos": float,
            "joint_1.pos": float,
            "joint_2.pos": float,
            "joint_3.pos": float,
            "joint_4.pos": float,
            "joint_5.pos": float,
            "gripper.pos": float,
        }

    def connect(self, calibrate: bool = True) -> None:
        """Connect to the ARX-X5 arm and cameras.

        Args:
            calibrate: If True, run calibration (currently not needed for ARX-X5).
        """
        if self._is_connected:
            logger.warning("ARX follower is already connected")
            return

        logger.info("Connecting to ARX-X5 arm")

        # Enable arm - set to gravity compensation mode for safe operation
        # The ARX SDK's SingleArm is already connected via CAN in __init__
        try:
            self.arm.gravity_compensation()
            logger.info("ARX-X5 arm enabled in gravity compensation mode")
        except AttributeError:
            # If gravity_compensation method doesn't exist, try go_home
            try:
                self.arm.go_home()
                logger.info("ARX-X5 arm moved to home position")
            except AttributeError:
                logger.warning("Could not enable arm - no gravity_compensation or go_home method")

        # Connect cameras
        for name, camera in self.cameras.items():
            logger.info(f"Connecting camera: {name}")
            camera.connect()

        self._is_connected = True
        logger.info("ARX follower connected successfully")

    def get_observation(self) -> RobotObservation:
        """Get current observation from the robot.

        Returns:
            Dictionary containing:
            - Joint positions (joint_0.pos through joint_5.pos) in radians
            - Gripper position (gripper.pos) in 0-1000 range
            - Camera images from all configured cameras
        """
        if not self._is_connected:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        observation = {}

        # Read joint positions from ARX arm
        try:
            joint_positions = self.arm.get_joint_positions()

            # ARX SDK returns 7 values: 6 joints + 1 gripper
            if len(joint_positions) == 7:
                # Extract first 6 as joint positions
                for i in range(6):
                    observation[f"joint_{i}.pos"] = float(joint_positions[i])
                # 7th value is gripper position
                observation["gripper.pos"] = float(joint_positions[6])
                self._last_gripper_pos = joint_positions[6]
            elif len(joint_positions) == 6:
                # Old behavior: only 6 joints, read gripper separately
                for i, pos in enumerate(joint_positions):
                    observation[f"joint_{i}.pos"] = float(pos)

                # Try to read gripper position separately
                try:
                    gripper_pos = self.arm.get_catch_pos()
                    observation["gripper.pos"] = float(gripper_pos)
                    self._last_gripper_pos = gripper_pos
                except AttributeError:
                    # SDK doesn't have get_catch_pos, use last sent position
                    observation["gripper.pos"] = float(self._last_gripper_pos)
                    logger.debug("Using last sent gripper position (SDK doesn't provide read method)")
            else:
                raise ValueError(f"Expected 6 or 7 joint positions, got {len(joint_positions)}")

        except Exception as e:
            logger.error(f"Failed to read joint positions: {e}")
            raise

        # Read camera images
        for name, camera in self.cameras.items():
            observation[name] = camera.async_read()

        return observation

    def send_action(self, action: RobotAction) -> RobotAction:
        """Send action commands to the robot.

        Args:
            action: Dictionary containing target positions for joints and gripper.

        Returns:
            The actual action sent to the robot (after safety checks).
        """
        if not self._is_connected:
            raise RuntimeError("Robot is not connected. Call connect() first.")

        # Extract joint positions
        joint_positions = [
            action["joint_0.pos"],
            action["joint_1.pos"],
            action["joint_2.pos"],
            action["joint_3.pos"],
            action["joint_4.pos"],
            action["joint_5.pos"],
        ]

        # Extract gripper position
        gripper_pos = action["gripper.pos"]

        # Apply safety limits if configured
        if self.config.max_relative_target is not None:
            current_obs = self.get_observation()
            current_positions = [current_obs[f"joint_{i}.pos"] for i in range(6)]

            for i in range(6):
                delta = joint_positions[i] - current_positions[i]
                if abs(delta) > self.config.max_relative_target:
                    logger.warning(
                        f"Joint {i} action delta {delta:.3f} exceeds limit "
                        f"{self.config.max_relative_target:.3f}, clamping"
                    )
                    joint_positions[i] = current_positions[i] + np.sign(delta) * self.config.max_relative_target

        # Send joint positions to arm
        try:
            self.arm.set_joint_positions(joint_positions)
        except Exception as e:
            logger.error(f"Failed to send joint positions: {e}")
            raise

        # Send gripper position
        try:
            # Clamp gripper position to valid range
            gripper_pos = max(self.config.gripper_close_pos, min(self.config.gripper_open_pos, gripper_pos))
            self.arm.set_catch_pos(int(gripper_pos))
            self._last_gripper_pos = gripper_pos
        except Exception as e:
            logger.error(f"Failed to send gripper position: {e}")
            raise

        # Return the actual action sent (after safety checks)
        return {
            "joint_0.pos": joint_positions[0],
            "joint_1.pos": joint_positions[1],
            "joint_2.pos": joint_positions[2],
            "joint_3.pos": joint_positions[3],
            "joint_4.pos": joint_positions[4],
            "joint_5.pos": joint_positions[5],
            "gripper.pos": gripper_pos,
        }

    def disconnect(self) -> None:
        """Disconnect from the ARX-X5 arm and cameras."""
        if not self._is_connected:
            logger.warning("ARX follower is not connected")
            return

        logger.info("Disconnecting ARX follower")

        # Set arm to gravity compensation mode if configured
        if not self.config.disable_torque_on_disconnect:
            try:
                self.arm.gravity_compensation()
                logger.info("ARX-X5 arm set to gravity compensation mode")
            except AttributeError:
                logger.warning("Could not set gravity compensation mode on disconnect")

        # Disconnect cameras
        for name, camera in self.cameras.items():
            logger.info(f"Disconnecting camera: {name}")
            camera.disconnect()

        self._is_connected = False
        logger.info("ARX follower disconnected")

    def calibrate(self) -> None:
        """Calibrate the robot.

        Note:
            ARX-X5 uses absolute encoders, so calibration is not required.
            This method is a no-op for compatibility with the Robot interface.
        """
        logger.info("ARX-X5 uses absolute encoders, calibration not required")

    def configure(self) -> None:
        """Configure the robot motors.

        Note:
            ARX SDK handles motor configuration internally.
            This method is a no-op for compatibility with the Robot interface.
        """
        logger.info("ARX SDK handles motor configuration, no action needed")

    @property
    def is_connected(self) -> bool:
        """Check if the robot is connected.

        Returns:
            True if connected, False otherwise.
        """
        return self._is_connected

    @property
    def is_calibrated(self) -> bool:
        """Check if the robot is calibrated.

        ARX-X5 uses absolute encoders, so calibration is not required.
        This always returns True.

        Returns:
            True (always calibrated).
        """
        return True

