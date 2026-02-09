"""Feetech leader teleoperator configuration."""

from dataclasses import dataclass

from ..config import TeleoperatorConfig


@TeleoperatorConfig.register_subclass("feetech_leader")
@dataclass
class FeetechLeaderConfig(TeleoperatorConfig):
    """Configuration for Feetech leader teleoperator.

    This configuration is for a generic Feetech-based leader arm using STS3215 servos.

    Attributes:
        port: Serial port to connect to the arm (e.g., "/dev/ttyACM0")
        use_degrees: Whether to use degrees for angles (default: False, uses -100 to 100 range)
        motor_ids: List of motor IDs for the arm joints (default: [1, 2, 3, 4, 5, 6])
        gripper_id: Motor ID for the gripper (default: 7)
        motor_model: Motor model name (default: "sts3215")
    """

    # Port to connect to the arm
    port: str = "/dev/ttyACM0"

    # Whether to use degrees for angles
    use_degrees: bool = False

    # Motor IDs for arm joints (6 DOF)
    motor_ids: list[int] = None

    # Gripper motor ID
    gripper_id: int = 7

    # Motor model
    motor_model: str = "sts3215"

    def __post_init__(self):
        # Set default motor IDs if not provided
        if self.motor_ids is None:
            self.motor_ids = [1, 2, 3, 4, 5, 6]
