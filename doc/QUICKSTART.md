# ARX-X5 Quick Start Guide

## Installation Complete ✅

The ARX-X5 follower robot has been successfully integrated into LeRobot.

## Quick Test (No Hardware Required)

```bash
cd /home/dora/lerobot
python3 test_arx_integration.py
```

## Hardware Setup

### 1. CAN Bus Setup
```bash
# Check CAN interface
ip link show can0

# Bring up CAN (if needed)
sudo ip link set can0 up type can bitrate 1000000

# Verify
candump can0
```

### 2. Permissions
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### 3. ARX SDK Path
Default: `/home/dora/DoRobot-before/ARX_X5/py/arx_x5_python`

If different, specify in config:
```python
config = ARXFollowerConfig(
    can_port="can0",
    arx_sdk_path="/your/path/to/arx_sdk"
)
```

## Basic Usage

### Python Script
```python
from lerobot.robots.arx_follower import ARXFollower, ARXFollowerConfig

config = ARXFollowerConfig(can_port="can0")

with ARXFollower(config) as robot:
    # Get observation
    obs = robot.get_observation()
    print(f"Joints: {[obs[f'joint_{i}.pos'] for i in range(6)]}")

    # Send action
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

### With LeRobot CLI
```bash
# Record dataset
lerobot-record \
    --robot-type arx_follower \
    --robot-config '{"can_port": "can0"}' \
    --repo-id username/arx_dataset

# Replay dataset
lerobot-replay \
    --robot-type arx_follower \
    --robot-config '{"can_port": "can0"}' \
    --repo-id username/arx_dataset
```

## Configuration Options

```python
ARXFollowerConfig(
    can_port="can0",              # CAN interface
    arx_type=0,                   # 0=standard, 1=master, 2=2025
    control_dt=0.05,              # 20Hz control rate
    max_relative_target=0.1,      # Safety limit (radians)
    gripper_open_pos=1000,        # Gripper open position
    gripper_close_pos=0,          # Gripper close position
    cameras={                     # Optional cameras
        "camera_wrist": CameraConfig(
            type="realsense",
            serial_number="123456789",
            width=640,
            height=480,
            fps=30,
        )
    },
    arx_sdk_path="/path/to/sdk", # ARX SDK path
)
```

## Observation Space

- `joint_0.pos` ... `joint_5.pos`: Joint positions (radians)
- `gripper.pos`: Gripper position (0-1000)
- Camera images (if configured)

## Action Space

- `joint_0.pos` ... `joint_5.pos`: Target joint positions (radians)
- `gripper.pos`: Target gripper position (0-1000)

## Examples

See detailed examples in:
- `examples/arx_follower_example.py`
- `src/lerobot/robots/arx_follower/README.md`

## Troubleshooting

### Import Error
```bash
# Make sure you're in the lerobot directory
cd /home/dora/lerobot

# Set PYTHONPATH
export PYTHONPATH=/home/dora/lerobot/src:$PYTHONPATH
```

### CAN Permission Denied
```bash
sudo chmod 666 /dev/can0
# Or add user to dialout group (see above)
```

### ARX SDK Not Found
Check the path in config matches your ARX SDK installation:
```python
config = ARXFollowerConfig(
    arx_sdk_path="/correct/path/to/arx_sdk"
)
```

## Next Steps

1. **Test Hardware Connection**
   ```bash
   cd /home/dora/lerobot
   python3 examples/arx_follower_example.py
   ```

2. **Record First Dataset**
   ```bash
   lerobot-record \
       --robot-type arx_follower \
       --robot-config '{"can_port": "can0"}' \
       --repo-id test/arx_first_dataset
   ```

3. **Train a Policy**
   Follow LeRobot training documentation with your dataset

## Support

- Full documentation: `src/lerobot/robots/arx_follower/README.md`
- Implementation summary: `ARX_INTEGRATION_SUMMARY.md`
- LeRobot docs: https://github.com/huggingface/lerobot

## Files Created

```
src/lerobot/robots/arx_follower/
├── __init__.py
├── config_arx_follower.py
├── arx_follower.py
└── README.md

examples/
└── arx_follower_example.py

test_arx_integration.py
ARX_INTEGRATION_SUMMARY.md
QUICKSTART.md (this file)
```
