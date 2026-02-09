"""Feetech leader teleoperator implementation.

This module implements a generic Feetech-based leader arm using STS3215 servos.
"""

import logging

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..teleoperator import Teleoperator
from .config_feetech_leader import FeetechLeaderConfig

logger = logging.getLogger(__name__)


class FeetechLeader(Teleoperator):
    """Generic Feetech leader teleoperator for STS3215-based arms.

    This class provides a teleoperator interface for Feetech-based leader arms
    with 6 DOF joints plus a gripper.

    Example:
        ```python
        from lerobot.teleoperators.feetech_leader import FeetechLeader, FeetechLeaderConfig

        config = FeetechLeaderConfig(
            port="/dev/ttyACM0",
            motor_ids=[1, 2, 3, 4, 5, 6],
            gripper_id=7,
        )

        with FeetechLeader(config) as leader:
            obs = leader.get_observation()
            print(f"Joint positions: {obs}")
        ```
    """

    config_class = FeetechLeaderConfig
    name = "feetech_leader"

    def __init__(self, config: FeetechLeaderConfig):
        """Initialize the Feetech leader teleoperator.

        Args:
            config: Configuration for the Feetech leader.
        """
        super().__init__(config)
        self.config = config

        # Determine normalization mode
        norm_mode_body = MotorNormMode.DEGREES if config.use_degrees else MotorNormMode.RANGE_M100_100

        # Build motors dictionary
        motors = {}

        # Add arm joints
        for i, motor_id in enumerate(config.motor_ids):
            motors[f"joint_{i}"] = Motor(motor_id, config.motor_model, norm_mode_body)

        # Add gripper
        motors["gripper"] = Motor(config.gripper_id, config.motor_model, MotorNormMode.RANGE_0_100)

        # Create motor bus
        self.bus = FeetechMotorsBus(
            port=config.port,
            motors=motors,
            calibration=self.calibration,
        )

    @property
    def action_features(self) -> dict[str, type]:
        """Define the action space for the leader.

        Returns:
            Dictionary mapping motor names to their types.
        """
        return {f"{motor}.pos": float for motor in self.bus.motors}

    @property
    def feedback_features(self) -> dict[str, type]:
        """Define the feedback space for the leader.

        Returns:
            Empty dictionary (no feedback for leader).
        """
        return {}

    @property
    def is_connected(self) -> bool:
        """Check if the leader is connected.

        Returns:
            True if connected, False otherwise.
        """
        return self.bus.is_connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """Connect to the Feetech leader arm.

        Args:
            calibrate: If True, run calibration if needed.
        """
        self.bus.connect()

        if not self.is_calibrated and calibrate:
            logger.info(
                "Mismatch between calibration values in the motor and the calibration file or no calibration file found"
            )
            self.calibrate()

        self.configure()
        logger.info(f"{self} connected.")

    @property
    def is_calibrated(self) -> bool:
        """Check if the leader is calibrated.

        Returns:
            True if calibrated, False otherwise.
        """
        return self.bus.is_calibrated

    def calibrate(self) -> None:
        """Calibrate the leader arm.

        This method runs the calibration procedure for the Feetech motors.
        """
        if self.calibration:
            # Calibration file exists, ask user whether to use it or run new calibration
            user_input = input(
                f"Press ENTER to use provided calibration file associated with the id {self.id}, "
                f"or type 'c' and press ENTER to run calibration: "
            )
            if user_input.strip().lower() != "c":
                logger.info(f"Writing calibration file associated with the id {self.id} to the motors")
                self.bus.write_calibration(self.calibration)
                return

        logger.info(f"\nRunning calibration of {self}")
        self.bus.disable_torque()

        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

        input(
            "Move the arm to the zero position (all joints at 0 degrees, gripper open), "
            "then press ENTER to continue..."
        )

        # Read and save calibration
        calibration = self.bus.read_calibration()
        self.bus.write_calibration(calibration)

        if self.config.calibration_dir:
            self.bus.save_calibration(self.config.calibration_dir / f"{self.id}.json")
            logger.info(f"Calibration saved to {self.config.calibration_dir / f'{self.id}.json'}")

        logger.info("Calibration complete")

    def configure(self) -> None:
        """Configure the leader arm motors.

        This method sets the motors to position control mode and enables torque.
        """
        # Set all motors to position mode
        for motor in self.bus.motors:
            self.bus.write("Operating_Mode", motor, OperatingMode.POSITION.value)

        # Disable torque for leader arm (so it can be moved freely)
        self.bus.disable_torque()

        logger.info("Leader arm configured (torque disabled for free movement)")

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from the leader arm."""
        self.bus.disconnect()
        logger.info(f"{self} disconnected.")

    def get_observation(self) -> dict[str, float]:
        """Get current observation from the leader arm.

        Returns:
            Dictionary containing motor positions.
        """
        if not self.is_connected:
            raise RuntimeError("Leader is not connected. Call connect() first.")

        observation = {}

        # Read all motor positions
        for motor_name in self.bus.motors:
            observation[f"{motor_name}.pos"] = self.bus.read("Present_Position", motor_name)

        return observation

    def get_action(self) -> dict[str, float]:
        """Get current action from the leader arm.

        This is an alias for get_observation() for teleoperator compatibility.

        Returns:
            Dictionary containing motor positions as actions.
        """
        return self.get_observation()

    def send_feedback(self, feedback: dict[str, float]) -> None:
        """Send feedback to the leader arm.

        For a leader arm, feedback is typically not used, so this is a no-op.

        Args:
            feedback: Feedback dictionary (ignored for leader arms).
        """
        # Leader arms don't need feedback, so this is a no-op
        pass
