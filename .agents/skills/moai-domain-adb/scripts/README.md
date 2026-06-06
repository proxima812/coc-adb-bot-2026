# ADB Automation Scripts

Single-file UV scripts for ADB automation with BlueStacks and Android devices.

## Quick Start

### Installation & Setup

1. **Prerequisites installed**:
   - BlueStacks or physical Android device
   - ADB enabled in device settings
   - Python 3.12+ with UV installed

2. **Connect device**:
   ```bash
   uv run scripts/connection/adb_connect.py
   uv run scripts/connection/adb_device_status.py
   ```

## Script Categories (36 Total)

### 🔌 Connection (4 scripts)
Device connection management and status checking.

- **`adb_connect.py`** - Connect to BlueStacks/device via IP:port
- **`adb_disconnect.py`** - Disconnect device gracefully
- **`adb_restart_server.py`** - Restart ADB server to fix connection issues
- **`adb_device_status.py`** - Check connection status and list all devices

### 📱 Screen (6 scripts)
Screen capture and touch interaction.

- **`adb_screenshot.py`** - Capture screenshot to file
- **`adb_tap.py`** - Tap at coordinates (single or multiple taps)
- **`adb_swipe.py`** - Swipe gestures (preset or custom coordinates)
- **`adb_keyevent.py`** - Send key events (back, home, menu, power, volume)
- **`adb_text_input.py`** - Input text into focused field
- **`adb_screenrecord.py`** - Record screen video to MP4 file

### 📦 App (5 scripts)
App lifecycle management.

- **`adb_app_start.py`** - Start app by package name with optional wait
- **`adb_app_stop.py`** - Force stop running app
- **`adb_app_list.py`** - List installed apps (user/system/all)
- **`adb_app_install.py`** - Install APK file to device
- **`adb_app_uninstall.py`** - Uninstall app by package name

### ℹ️ Info (4 scripts)
Device information and diagnostics.

- **`adb_device_info.py`** - Device specifications (model, Android version, API level)
- **`adb_display_info.py`** - Display resolution, DPI, and orientation
- **`adb_running_app.py`** - Get current foreground app package
- **`adb_battery_info.py`** - Battery status (level, temperature, health, charging)

### ⚡ Performance (3 scripts)
Monitoring and profiling tools.

- **`adb_cpu_monitor.py`** - Real-time CPU load monitoring
- **`adb_memory_monitor.py`** - Memory usage monitoring by app
- **`adb_logcat_filter.py`** - Filter logcat by tag/priority with live follow

### 🤖 Automation (4 scripts)
Game loops and workflow automation.

- **`adb_game_loop.py`** - Execute repeating JSON action sequence
- **`adb_wait_for_app.py`** - Wait for app to start with timeout
- **`adb_click_sequence.py`** - Execute action sequence once
- **`adb_screenshot_compare.py`** - Compare screenshots with similarity score

### 🛠️ Utils (3 scripts)
Generic ADB utilities.

- **`adb_shell.py`** - Execute arbitrary shell commands on device
- **`adb_push.py`** - Push file from local to device
- **`adb_pull.py`** - Pull file from device to local

### 🔧 Monitoring (7 scripts)
Advanced development and testing tools.

- **`adb_bot_generator.py`** - Generate game bot scripts from templates
- **`adb_config_validator.py`** - Validate ADB configuration files
- **`adb_deployment_helper.py`** - Deploy apps and configs to multiple devices
- **`adb_device_analyzer.py`** - Analyze device capabilities and performance
- **`adb_game_tester.py`** - Automated game testing with screenshots
- **`adb_performance_profiler.py`** - Profile app performance metrics
- **`adb_template_creator.py`** - Create script templates for new automation

## Standard CLI Options

All scripts support these options:

- **`--device/-d DEVICE`** - Device ID (defaults to first connected device)
- **`--toon`** - Output in TOON/YAML format for automation
- **`--verbose/-v`** - Verbose output with detailed logging
- **`--help`** - Show command help and usage examples

## BlueStacks Configuration

### Default Settings
- **Host**: 127.0.0.1
- **Port**: 5555
- **Device ID**: 127.0.0.1:5555

### Multiple Instances
- Instance 1: 127.0.0.1:5555
- Instance 2: 127.0.0.1:5557
- Instance 3: 127.0.0.1:5559

Connect to specific instance:
```bash
uv run scripts/connection/adb_connect.py --device 127.0.0.1:5557
```

## Common Usage Examples

### Connection Management

#### Check Connection Status
```bash
# List all connected devices
uv run scripts/connection/adb_device_status.py

# Verbose output with detailed info
uv run scripts/connection/adb_device_status.py --verbose

# TOON/YAML output for automation
uv run scripts/connection/adb_device_status.py --toon
```

#### Connect to Device
```bash
# Connect to default BlueStacks (127.0.0.1:5555)
uv run scripts/connection/adb_connect.py

# Connect to specific instance
uv run scripts/connection/adb_connect.py --device 127.0.0.1:5557

# Connect with verbose logging
uv run scripts/connection/adb_connect.py --verbose
```

#### Disconnect Device
```bash
# Disconnect default device
uv run scripts/connection/adb_disconnect.py

# Disconnect specific device
uv run scripts/connection/adb_disconnect.py --device 127.0.0.1:5557
```

#### Restart ADB Server
```bash
# Restart server to fix connection issues
uv run scripts/connection/adb_restart_server.py --verbose
```

### Screen Interaction

#### Take Screenshot
```bash
# Save to default location
uv run scripts/screen/adb_screenshot.py

# Save to specific file
uv run scripts/screen/adb_screenshot.py --output before.png

# Capture from specific device
uv run scripts/screen/adb_screenshot.py --device 127.0.0.1:5557 --output instance2.png
```

#### Tap at Coordinates
```bash
# Single tap at position
uv run scripts/screen/adb_tap.py --x 500 --y 1000

# Multiple taps (5 times)
uv run scripts/screen/adb_tap.py --x 500 --y 1000 --count 5

# Tap with delay between taps
uv run scripts/screen/adb_tap.py --x 500 --y 1000 --count 3 --delay 1.5
```

#### Swipe Gestures
```bash
# Preset swipe directions
uv run scripts/screen/adb_swipe.py --preset up
uv run scripts/screen/adb_swipe.py --preset down
uv run scripts/screen/adb_swipe.py --preset left
uv run scripts/screen/adb_swipe.py --preset right

# Custom swipe with coordinates
uv run scripts/screen/adb_swipe.py --start 500,1500 --end 500,500 --duration 300

# Fast swipe (100ms duration)
uv run scripts/screen/adb_swipe.py --start 500,1500 --end 500,500 --duration 100
```

#### Send Key Events
```bash
# Common keys
uv run scripts/screen/adb_keyevent.py --key back
uv run scripts/screen/adb_keyevent.py --key home
uv run scripts/screen/adb_keyevent.py --key menu
uv run scripts/screen/adb_keyevent.py --key power

# Volume controls
uv run scripts/screen/adb_keyevent.py --key volume_up
uv run scripts/screen/adb_keyevent.py --key volume_down
uv run scripts/screen/adb_keyevent.py --key volume_mute
```

#### Input Text
```bash
# Type text into focused field
uv run scripts/screen/adb_text_input.py --text "Hello World"

# Type with special characters (use quotes)
uv run scripts/screen/adb_text_input.py --text "user@example.com"

# Type multiple words
uv run scripts/screen/adb_text_input.py --text "Search query here"
```

#### Record Screen Video
```bash
# Record 30 seconds (default)
uv run scripts/screen/adb_screenrecord.py

# Record specific duration
uv run scripts/screen/adb_screenrecord.py --duration 60

# Save to specific file
uv run scripts/screen/adb_screenrecord.py --output gameplay.mp4 --duration 120
```

### App Management

#### List Installed Apps
```bash
# List all user apps
uv run scripts/app/adb_app_list.py

# Filter by name
uv run scripts/app/adb_app_list.py --filter afk
uv run scripts/app/adb_app_list.py --filter "Google"

# List system apps
uv run scripts/app/adb_app_list.py --system

# List all apps (user + system)
uv run scripts/app/adb_app_list.py --all

# TOON output for automation
uv run scripts/app/adb_app_list.py --toon
```

#### Start App
```bash
# Start by package name
uv run scripts/app/adb_app_start.py --package com.afk.journey

# Short option
uv run scripts/app/adb_app_start.py -p com.afk.journey

# Start and wait for launch
uv run scripts/app/adb_app_start.py -p com.afk.journey --wait

# Wait with timeout
uv run scripts/app/adb_app_start.py -p com.afk.journey --wait --timeout 10
```

#### Stop App
```bash
# Force stop by package name
uv run scripts/app/adb_app_stop.py --package com.afk.journey

# Short option
uv run scripts/app/adb_app_stop.py -p com.afk.journey

# Stop with verbose logging
uv run scripts/app/adb_app_stop.py -p com.afk.journey --verbose
```

#### Install APK
```bash
# Install from local file
uv run scripts/app/adb_app_install.py --apk myapp.apk

# Install to specific device
uv run scripts/app/adb_app_install.py --apk myapp.apk --device 127.0.0.1:5557

# Install with verbose logging
uv run scripts/app/adb_app_install.py --apk myapp.apk --verbose
```

#### Uninstall App
```bash
# Uninstall by package name
uv run scripts/app/adb_app_uninstall.py --package com.example.app

# Short option
uv run scripts/app/adb_app_uninstall.py -p com.example.app

# Keep data directory
uv run scripts/app/adb_app_uninstall.py -p com.example.app --keep-data
```

### Device Information

#### Get Device Specifications
```bash
# Basic device info
uv run scripts/info/adb_device_info.py

# Verbose output with all details
uv run scripts/info/adb_device_info.py --verbose

# TOON output
uv run scripts/info/adb_device_info.py --toon
```

#### Display Information
```bash
# Get screen resolution and DPI
uv run scripts/info/adb_display_info.py

# Verbose output
uv run scripts/info/adb_display_info.py --verbose

# TOON output
uv run scripts/info/adb_display_info.py --toon
```

#### Get Running App
```bash
# Get current foreground app
uv run scripts/info/adb_running_app.py

# Verbose output
uv run scripts/info/adb_running_app.py --verbose

# TOON output for automation
uv run scripts/info/adb_running_app.py --toon
```

#### Battery Status
```bash
# Get battery information
uv run scripts/info/adb_battery_info.py

# Verbose output with all details
uv run scripts/info/adb_battery_info.py --verbose

# TOON output
uv run scripts/info/adb_battery_info.py --toon
```

### Performance Monitoring

#### Monitor CPU Usage
```bash
# Monitor for 60 seconds (default)
uv run scripts/performance/adb_cpu_monitor.py

# Custom duration
uv run scripts/performance/adb_cpu_monitor.py --duration 120

# Monitor specific app
uv run scripts/performance/adb_cpu_monitor.py --package com.afk.journey --duration 60

# With verbose logging
uv run scripts/performance/adb_cpu_monitor.py --verbose --duration 30
```

#### Monitor Memory Usage
```bash
# Monitor system memory
uv run scripts/performance/adb_memory_monitor.py

# Custom duration
uv run scripts/performance/adb_memory_monitor.py --duration 120

# Monitor specific app
uv run scripts/performance/adb_memory_monitor.py --package com.afk.journey --duration 60

# With verbose logging
uv run scripts/performance/adb_memory_monitor.py --verbose --duration 30
```

#### Filter Logcat
```bash
# Filter by tag
uv run scripts/performance/adb_logcat_filter.py --tag MyApp

# Filter by priority (V=Verbose, D=Debug, I=Info, W=Warn, E=Error, F=Fatal)
uv run scripts/performance/adb_logcat_filter.py --priority E

# Filter by both tag and priority
uv run scripts/performance/adb_logcat_filter.py --tag MyApp --priority W

# Follow live (continuous mode)
uv run scripts/performance/adb_logcat_filter.py --tag MyApp --follow

# Clear buffer before filtering
uv run scripts/performance/adb_logcat_filter.py --tag MyApp --clear

# Save to file
uv run scripts/performance/adb_logcat_filter.py --tag MyApp --output logs.txt
```

### Automation Workflows

#### Execute Game Loop
```bash
# Run sequence 10 times
uv run scripts/automation/adb_game_loop.py --sequence daily.json --loops 10

# Short option
uv run scripts/automation/adb_game_loop.py -s daily.json -l 10

# Infinite loop
uv run scripts/automation/adb_game_loop.py -s farming.json --infinite

# Infinite with delay between loops (seconds)
uv run scripts/automation/adb_game_loop.py -s farming.json --infinite --delay 5

# With specific device
uv run scripts/automation/adb_game_loop.py -s daily.json -l 10 --device 127.0.0.1:5557
```

#### Wait for App to Start
```bash
# Wait up to 30 seconds (default)
uv run scripts/automation/adb_wait_for_app.py --package com.afk.journey

# Custom timeout
uv run scripts/automation/adb_wait_for_app.py --package com.afk.journey --timeout 60

# Check interval (seconds)
uv run scripts/automation/adb_wait_for_app.py --package com.afk.journey --timeout 30 --interval 2
```

#### Execute Click Sequence Once
```bash
# Execute sequence file once
uv run scripts/automation/adb_click_sequence.py --sequence tutorial.json

# Short option
uv run scripts/automation/adb_click_sequence.py -s tutorial.json

# With specific device
uv run scripts/automation/adb_click_sequence.py -s tutorial.json --device 127.0.0.1:5557
```

#### Compare Screenshots
```bash
# Compare two images
uv run scripts/automation/adb_screenshot_compare.py --before ref.png --after test.png

# Short options
uv run scripts/automation/adb_screenshot_compare.py -b ref.png -a test.png

# With threshold (0.0-1.0, default 0.95)
uv run scripts/automation/adb_screenshot_compare.py -b ref.png -a test.png --threshold 0.90

# TOON output with similarity score
uv run scripts/automation/adb_screenshot_compare.py -b ref.png -a test.png --toon
```

### File Transfer

#### Push File to Device
```bash
# Push file to device
uv run scripts/utils/adb_push.py --local myfile.txt --remote /sdcard/myfile.txt

# Short options
uv run scripts/utils/adb_push.py -l myfile.txt -r /sdcard/myfile.txt

# Push to specific device
uv run scripts/utils/adb_push.py -l myfile.txt -r /sdcard/myfile.txt --device 127.0.0.1:5557
```

#### Pull File from Device
```bash
# Pull file from device
uv run scripts/utils/adb_pull.py --remote /sdcard/screenshot.png --local screenshot.png

# Short options
uv run scripts/utils/adb_pull.py -r /sdcard/screenshot.png -l screenshot.png

# Pull from specific device
uv run scripts/utils/adb_pull.py -r /sdcard/screenshot.png -l screenshot.png --device 127.0.0.1:5557
```

#### Execute Shell Command
```bash
# Execute simple command
uv run scripts/utils/adb_shell.py --command "ls /sdcard"

# Short option
uv run scripts/utils/adb_shell.py -c "pm list packages"

# With timeout (seconds)
uv run scripts/utils/adb_shell.py -c "pm list packages" --timeout 10

# Complex command with quotes
uv run scripts/utils/adb_shell.py -c "dumpsys battery | grep level"
```

### Monitoring & Development

#### Generate Bot Scripts
```bash
# Generate bot from template
uv run scripts/adb_bot_generator.py --template daily_quests --output my_bot.json

# List available templates
uv run scripts/adb_bot_generator.py --list-templates

# Generate with customization
uv run scripts/adb_bot_generator.py --template farming --output farm_bot.json --customize
```

#### Validate Configuration
```bash
# Validate config file
uv run scripts/adb_config_validator.py --config config.json

# Validate with strict mode
uv run scripts/adb_config_validator.py --config config.json --strict

# Output validation report
uv run scripts/adb_config_validator.py --config config.json --report validation_report.txt
```

#### Deploy to Multiple Devices
```bash
# Deploy app to all connected devices
uv run scripts/adb_deployment_helper.py --apk myapp.apk --all

# Deploy to specific devices
uv run scripts/adb_deployment_helper.py --apk myapp.apk --devices 127.0.0.1:5555,127.0.0.1:5557

# Deploy with config file
uv run scripts/adb_deployment_helper.py --apk myapp.apk --config deploy_config.json
```

#### Analyze Device
```bash
# Full device analysis
uv run scripts/adb_device_analyzer.py

# Analyze specific aspects
uv run scripts/adb_device_analyzer.py --aspects performance,battery,storage

# Output to report file
uv run scripts/adb_device_analyzer.py --output analysis_report.json
```

#### Test Game Automation
```bash
# Run game test suite
uv run scripts/adb_game_tester.py --test-suite daily_quests.json

# Test with screenshots
uv run scripts/adb_game_tester.py --test-suite tests.json --screenshots

# Test specific scenario
uv run scripts/adb_game_tester.py --scenario login_flow --iterations 10
```

#### Profile Performance
```bash
# Profile app performance
uv run scripts/adb_performance_profiler.py --package com.afk.journey --duration 60

# Profile with detailed metrics
uv run scripts/adb_performance_profiler.py --package com.afk.journey --duration 60 --detailed

# Save profiling data
uv run scripts/adb_performance_profiler.py --package com.afk.journey --output profile_data.json
```

#### Create Script Templates
```bash
# Create new script template
uv run scripts/adb_template_creator.py --name my_automation --category automation

# List available template types
uv run scripts/adb_template_creator.py --list-types

# Create with boilerplate
uv run scripts/adb_template_creator.py --name my_script --category screen --boilerplate
```

## JSON Sequence Format

For automation scripts (`adb_game_loop.py`, `adb_click_sequence.py`), use JSON format:

```json
{
  "name": "Daily Quest Automation",
  "description": "Automates daily quest collection",
  "steps": [
    {
      "action": "tap",
      "x": 500,
      "y": 1000,
      "delay": 2,
      "description": "Tap quest button"
    },
    {
      "action": "swipe",
      "start": [500, 1500],
      "end": [500, 500],
      "duration": 300,
      "description": "Swipe up to scroll"
    },
    {
      "action": "wait",
      "duration": 3,
      "description": "Wait for UI to load"
    },
    {
      "action": "screenshot",
      "output": "/tmp/quest_check.png",
      "description": "Capture current state"
    },
    {
      "action": "keyevent",
      "key": "back",
      "description": "Go back"
    },
    {
      "action": "text_input",
      "text": "Hello World",
      "description": "Type text"
    }
  ]
}
```

### Supported Actions

- **`tap`**: Tap at x, y coordinates
  - Required: `x`, `y`
  - Optional: `delay` (seconds after tap)

- **`swipe`**: Swipe gesture
  - Required: `start` (array [x, y]), `end` (array [x, y])
  - Optional: `duration` (milliseconds), `delay` (seconds after)

- **`wait`**: Pause execution
  - Required: `duration` (seconds)

- **`screenshot`**: Capture screen
  - Required: `output` (file path)

- **`keyevent`**: Send key event
  - Required: `key` (back, home, menu, power, volume_up, volume_down)
  - Optional: `delay` (seconds after)

- **`text_input`**: Type text
  - Required: `text` (string to type)
  - Optional: `delay` (seconds after)

## Architecture

### Common Utilities
All scripts use shared utilities for consistency:

- **`path_utils.py`**: Project root detection and path resolution
- **`adb_utils.py`**: ADB device operations and connection management
- **`cli_utils.py`**: Click decorators, Rich formatters, and output helpers
- **`error_handlers.py`**: Standardized error handling and exit codes

### Exit Codes
Scripts use standardized exit codes:

- **`0`** - Success
- **`2`** - Device offline or not found
- **`3`** - ADB command failed or execution error
- **`4`** - Invalid argument or configuration

### Output Formats

#### Text Output (Default)
Rich-formatted console output with colors and tables:
```
✓ Device connected: 127.0.0.1:5555
✓ Model: BlueStacks Android
✓ Android version: 7.0
```

#### TOON Output (--toon flag)
YAML/structured format for automation and parsing:
```yaml
status: success
device:
  id: 127.0.0.1:5555
  model: BlueStacks Android
  android_version: "7.0"
```

## BlueStacks Setup Guide

### Enable ADB in BlueStacks

1. **Open BlueStacks Settings**
   - Click hamburger menu (☰) in top-right
   - Select "Settings"

2. **Enable Android Debug Bridge**
   - Go to "Advanced" tab
   - Enable "Android Debug Bridge (ADB)"
   - Note the port (default: 5555)

3. **Restart BlueStacks** (if prompted)

4. **Verify Connection**
   ```bash
   uv run scripts/connection/adb_connect.py
   uv run scripts/connection/adb_device_status.py
   ```

### Multiple BlueStacks Instances

Each instance uses a different port:
- Instance 1: 5555
- Instance 2: 5557
- Instance 3: 5559

Check instance port in Settings → Advanced → ADB Port

## Troubleshooting

### Connection Issues

**Problem**: Device not found or offline

**Solutions**:
```bash
# 1. Restart ADB server
uv run scripts/connection/adb_restart_server.py --verbose

# 2. Check device status
uv run scripts/connection/adb_device_status.py

# 3. Try reconnecting
uv run scripts/connection/adb_connect.py --verbose

# 4. Check BlueStacks ADB settings (Settings → Advanced)
```

### Permission Issues

**Problem**: ADB commands fail with permission denied

**Solutions**:
1. Enable ADB in device settings
2. Restart device
3. Try connecting again
4. Check BlueStacks documentation for ADB setup

### App Not Found

**Problem**: Cannot start app by package name

**Solutions**:
```bash
# 1. List all installed apps to find correct package name
uv run scripts/app/adb_app_list.py --filter "app name"

# 2. Verify app is installed
uv run scripts/app/adb_app_list.py --all | grep "package"

# 3. Try starting with correct package name
uv run scripts/app/adb_app_start.py -p com.correct.package
```

### Script Help

Every script has built-in help:
```bash
uv run scripts/{category}/{script}.py --help
```

Example:
```bash
uv run scripts/screen/adb_tap.py --help
uv run scripts/automation/adb_game_loop.py --help
```

## Performance Tips

### Batch Operations
Use JSON sequences instead of individual script calls for better performance:
```bash
# ❌ Slow - Multiple script calls
uv run scripts/screen/adb_tap.py --x 500 --y 1000
sleep 2
uv run scripts/screen/adb_swipe.py --preset up
sleep 2
uv run scripts/screen/adb_keyevent.py --key back

# ✅ Fast - Single sequence
uv run scripts/automation/adb_click_sequence.py --sequence my_actions.json
```

### Screenshot Timing
Add delays after taps to allow UI updates:
```json
{
  "action": "tap",
  "x": 500,
  "y": 1000,
  "delay": 2
}
```

### Multiple Devices
Use different BlueStacks ports for parallel automation:
```bash
# Terminal 1: Instance 1
uv run scripts/automation/adb_game_loop.py -s farming.json --device 127.0.0.1:5555 --infinite

# Terminal 2: Instance 2
uv run scripts/automation/adb_game_loop.py -s daily.json --device 127.0.0.1:5557 --infinite
```

### Error Recovery
Use wait actions to ensure operations complete:
```json
{
  "steps": [
    {"action": "tap", "x": 500, "y": 1000},
    {"action": "wait", "duration": 2},
    {"action": "screenshot", "output": "verify.png"}
  ]
}
```

## Contributing

### Adding New Scripts

Follow the IndieDevDan pattern (9-section structure):

1. **Purpose** - Script description
2. **Patterns** - Design patterns used
3. **Dependencies** - Required packages
4. **Architecture** - Component structure
5. **Operations** - Main operations
6. **Integration** - How it integrates
7. **Testing** - Test instructions
8. **Usage** - CLI examples
9. **License** - License info

### Code Standards

- Use Click for CLI arguments
- Use Rich for console output
- Import from `common/` utilities
- Document in this README
- Test with actual BlueStacks instance
- Follow PEP 8 style guide
- Use type hints
- Add docstrings

### Testing

```bash
# Test individual script
uv run scripts/connection/adb_connect.py --verbose

# Test automation sequence
uv run scripts/automation/adb_click_sequence.py -s test.json

# Test with TOON output
uv run scripts/info/adb_device_info.py --toon
```

## Dependencies

Scripts require:

### Core Dependencies
- **Python** 3.12+
- **click** >=8.1.0 - CLI argument parsing
- **rich** >=13.0.0 - Console formatting
- **pyyaml** >=6.0.0 - TOON output format
- **adbutils** >=2.12.0 - ADB operations

### Optional Dependencies
- **Pillow** - Screenshot comparison (automation scripts)
- **numpy** - Image processing (monitoring scripts)
- **pandas** - Data analysis (monitoring scripts)

Install all dependencies:
```bash
uv pip install click rich pyyaml adbutils Pillow numpy pandas
```

## Directory Structure

```
scripts/
├── common/                 # Shared utilities (4 files)
│   ├── __init__.py
│   ├── adb_utils.py       # ADB device operations
│   ├── cli_utils.py       # Click decorators and Rich formatters
│   ├── error_handlers.py  # Error handling and exit codes
│   └── path_utils.py      # Project root detection
│
├── connection/            # Connection management (4 scripts)
│   ├── adb_connect.py
│   ├── adb_device_status.py
│   ├── adb_disconnect.py
│   └── adb_restart_server.py
│
├── screen/                # Screen interaction (6 scripts)
│   ├── adb_keyevent.py
│   ├── adb_screenrecord.py
│   ├── adb_screenshot.py
│   ├── adb_swipe.py
│   ├── adb_tap.py
│   └── adb_text_input.py
│
├── app/                   # App lifecycle (5 scripts)
│   ├── adb_app_install.py
│   ├── adb_app_list.py
│   ├── adb_app_start.py
│   ├── adb_app_stop.py
│   └── adb_app_uninstall.py
│
├── info/                  # Device information (4 scripts)
│   ├── adb_battery_info.py
│   ├── adb_device_info.py
│   ├── adb_display_info.py
│   └── adb_running_app.py
│
├── automation/            # Workflow automation (4 scripts)
│   ├── adb_click_sequence.py
│   ├── adb_game_loop.py
│   ├── adb_screenshot_compare.py
│   └── adb_wait_for_app.py
│
├── performance/           # Monitoring (3 scripts)
│   ├── adb_cpu_monitor.py
│   ├── adb_logcat_filter.py
│   └── adb_memory_monitor.py
│
├── utils/                 # Generic utilities (3 scripts)
│   ├── adb_pull.py
│   ├── adb_push.py
│   └── adb_shell.py
│
├── adb_bot_generator.py           # Bot script generator
├── adb_config_validator.py        # Config validation
├── adb_deployment_helper.py       # Multi-device deployment
├── adb_device_analyzer.py         # Device analysis
├── adb_game_tester.py             # Game testing
├── adb_performance_profiler.py    # Performance profiling
├── adb_template_creator.py        # Template creation
│
└── README.md              # This file
```

## Examples Repository

See the `examples/` directory for:
- Sample JSON sequences
- Common automation patterns
- Game-specific scripts
- Testing scenarios
- Configuration templates

## License

These scripts leverage the AdbAutoPlayer project infrastructure.
See project LICENSE for details.

## Support

For issues, questions, or contributions:
1. Check this README for solutions
2. Review script help: `uv run scripts/{category}/{script}.py --help`
3. Test with verbose output: `--verbose`
4. Check BlueStacks ADB documentation

## Version

**Scripts Version**: 1.0.0
**Last Updated**: 2025-12-01
**Total Scripts**: 36 (29 core + 7 monitoring)
**Total Utilities**: 4 (common/)
