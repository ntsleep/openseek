# Seek Lite

Open-source Python CLI for the Seek Lite BLE tracker (SFST212, SnappWish LLC). No official app, no embedded trackers.

## Install

```bash
uv sync
```

This creates a virtual environment and installs all dependencies. Then use `uv run` to execute commands:

```bash
uv run seeklite ring --duration 3
```

Or activate the venv and use the commands directly:

```bash
source .venv/bin/activate
seeklite ring --duration 3
```

## Usage

Set your tracker's MAC address with any of these methods (checked in order):

```bash
# 1. .env file (recommended)
echo "SEEK_MAC=AA:BB:CC:DD:EE:FF" > .env

# 2. Environment variable
export SEEK_MAC=AA:BB:CC:DD:EE:FF

# 3. --address flag (overrides all)
seeklite ring --address AA:BB:CC:DD:EE:FF
```

### Commands

```bash
# Ring the tracker for 3 seconds
seeklite ring

# Ring for 10 seconds
seeklite ring --duration 10

# Stop an active alert
seeklite stop

# Read battery and device info
seeklite info

# Subscribe to live FFC6 notifications (Ctrl+C to quit)
seeklite monitor

# Check if tracker is advertising
seeklite scan

# Force-disconnect a stuck connection
seeklite disconnect
```

### python -m seeklite

```bash
uv run python -m seeklite ring --duration 3
```

## Protocol

Authentication is required before any alert write — see `project_decription.md` for full protocol details.
