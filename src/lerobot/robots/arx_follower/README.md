# ARX-X5 Follower Robot Integration

This module integrates the ARX-X5 robotic arm as a follower robot in the LeRobot framework.

## Overview

The ARX-X5 is a 6-DOF robotic arm with an integrated gripper that communicates via CAN bus. This integration wraps the ARX SDK to provide a LeRobot-compatible interface.

## Features

- **6 DOF arm control**: Position control for all 6 joints in radians
- **Gripper control**: Independent gripper position control (0-1000 range)
- **Camera support**: Intel RealSense camera integration
- **Safety limits**: Optional max relative target limits for safe operation
- **Gravity compensation**: Automatic gravity compensation mode on disconnect

## Prerequisites

### 1. ARX SDK Installation

The ARX SDK must be installed and accessible. By default, the integration expects it at:

```
/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python
```

You can specify a different path in the configuration.

### 2. CAN Bus Setup

The ARX-X5 communicates via CAN bus. Ensure your CAN interface is properly configured:

```bash
# Check if CAN interface exists
ip link show can0

# Bring up CAN interface (if needed)
sudo ip link set can0 up type can bitrate 1000000

# Verify CAN is working
candump can0
```

### 3. Permissions

Ensure your user has permission to access the CAN interface:

```bash
# Add user to dialout group (may vary by system)
sudo usermod -a -G dialout $USER

# Or set CAN permissions
sudo chmod 666 /dev/can0
```

## Usage

### Basic Example

```python
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig

# Create configuration
config = ARXFollowerConfig(
    can_port="can0",
    arx_type=0,  # 0=standard X5, 1=master X5, 2=2025 X5
)

# Use robot
with ARXFollower(config) as robot:
    # Get observation
    obs = robot.get_observation()
    print(f"Joint positions: {[obs[f'joint_{i}.pos'] for i in range(6)]}")
    print(f"Gripper position: {obs['gripper.pos']}")

    # Send action
    action = {
        "joint_0.pos": 0.0,
        "joint_1.pos": 0.0,
        "joint_2.pos": 0.0,
        "joint_3.pos": 0.0,
        "joint_4.pos": 0.0,
        "joint_5.pos": 0.0,
        "gripper.pos": 500.0,  # Half open
    }
    robot.send_action(action)
```

### With Camera

```python
from lerobot.cameras.configs import CameraConfig

config = ARXFollowerConfig(
    can_port="can0",
    cameras={
        "camera_wrist": CameraConfig(
            type="realsense",
            serial_number="123456789",  # Your RealSense serial
            width=640,
            height=480,
            fps=30,
        )
    }
)

with ARXFollower(config) as robot:
    obs = robot.get_observation()
    image = obs["camera_wrist"]  # numpy array (480, 640, 3)
```

### With Safety Limits

```python
config = ARXFollowerConfig(
    can_port="can0",
    max_relative_target=0.1,  # Limit action delta to 0.1 radians
)
```

## Configuration Options

### ARXFollowerConfig

| Parameter                      | Type        | Default     | Description                       |
| ------------------------------ | ----------- | ----------- | --------------------------------- |
| `can_port`                     | str         | "can0"      | CAN interface name                |
| `arx_type`                     | int         | 0           | ARX arm type (0/1/2)              |
| `control_dt`                   | float       | 0.05        | Control loop timestep (20Hz)      |
| `max_relative_target`          | float\|None | None        | Safety limit for action magnitude |
| `gripper_open_pos`             | int         | 1000        | Gripper fully open position       |
| `gripper_close_pos`            | int         | 0           | Gripper fully closed position     |
| `cameras`                      | dict        | {}          | Camera configurations             |
| `disable_torque_on_disconnect` | bool        | False       | Disable torque on disconnect      |
| `arx_sdk_path`                 | str         | (see above) | Path to ARX SDK                   |

## Observation Space

The robot provides the following observations:

- `joint_0.pos` through `joint_5.pos`: Joint positions in radians (float)
- `gripper.pos`: Gripper position 0-1000 (float)
- Camera images: numpy arrays (height, width, 3) for each configured camera

## Action Space

The robot accepts the following actions:

- `joint_0.pos` through `joint_5.pos`: Target joint positions in radians (float)
- `gripper.pos`: Target gripper position 0-1000 (float)

## Integration with LeRobot Scripts

### Recording Data

```bash
lerobot-record \
    --robot-type arx_follower \
    --robot-config '{"can_port": "can0"}' \
    --repo-id username/arx_dataset
```

### Replaying Data

```bash
lerobot-replay \
    --robot-type arx_follower \
    --robot-config '{"can_port": "can0"}' \
    --repo-id username/arx_dataset
```

## Troubleshooting

### "Failed to import ARX SDK"

- Verify the ARX SDK is installed at the configured path
- Check that the path contains `bimanual/` directory
- Ensure all ARX SDK dependencies are installed

### "Permission denied" on CAN interface

- Check CAN interface permissions: `ls -l /dev/can0`
- Add user to appropriate group: `sudo usermod -a -G dialout $USER`
- Log out and back in for group changes to take effect

### "No such device" for CAN

- Verify CAN interface exists: `ip link show can0`
- Bring up CAN interface: `sudo ip link set can0 up type can bitrate 1000000`
- Check kernel modules: `lsmod | grep can`

### Gripper position not updating in observations

The ARX SDK may not provide a method to read gripper position. In this case, the integration tracks the last sent gripper position. This is normal behavior.

## Architecture Notes

This integration follows a direct SDK wrapper approach:

- **No custom motor bus**: The ARX SDK's `SingleArm` class already handles CAN communication
- **Dynamic import**: The ARX SDK is imported dynamically to avoid hard dependencies
- **Gravity compensation**: The arm is set to gravity compensation mode for safe operation
- **Absolute encoders**: The ARX-X5 uses absolute encoders, so calibration is not required

## Future Enhancements

Potential improvements for future versions:

1. **Velocity control**: Add joint velocity observations and actions
2. **Torque feedback**: Add joint torque/current observations
3. **Cartesian control**: Add end-effector position control via kinematics
4. **Dual arm support**: Create BiARXFollower for bimanual setups
5. **Force sensing**: Integrate force/torque sensor if available

## References

- ARX SDK: `/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python`
- LeRobot Robot base class: `src/lerobot/robots/robot.py`
- Similar implementations: SO follower, OpenArm follower
