# Module 1: ADB Fundamentals

**Level**: Beginner → Intermediate
**Prerequisites**: None
**Estimated Learning Time**: 30-45 minutes
**Hands-On Practice**: 10-15 minutes

---

## 1️⃣ What is ADB?

ADB (Android Debug Bridge) is a versatile command-line tool that lets you communicate with a device or Android Virtual Machine (AVD).

**Core Capabilities**:
- ✅ Install and debug applications
- ✅ Access device shell and run arbitrary commands
- ✅ Transfer files to/from device
- ✅ View real-time system logs
- ✅ Control device input (taps, swipes, keystrokes)
- ✅ Capture screenshots and videos

**Architecture**:

```
HOST (Your Computer)
    ↓
┌───────────────────────┐
│   ADB Client (CLI)    │ ← You run: adb shell, adb push, etc.
└───────────────────────┘
    ↓ TCP/USB Connection
┌───────────────────────┐
│   ADB Daemon (adbd)   │ ← Runs on device
└───────────────────────┘
    ↓
DEVICE (Android Phone/Emulator)
    ↓
┌───────────────────────┐
│  Shell Environment    │
│  (Linux Command Line) │
└───────────────────────┘
```

---

## 2️⃣ Setting Up ADB

### Installation

**macOS** (using Homebrew):
```bash
brew install android-platform-tools
adb --version  # Verify installation
```

**Linux** (Ubuntu/Debian):
```bash
sudo apt-get install adb
adb --version
```

**Windows** (using Chocolatey):
```bash
choco install adb
adb --version
```

### Verify Installation

```bash
# Check ADB version and available commands
adb version

# Start ADB daemon
adb start-server

# Check daemon status
adb kill-server
adb start-server  # Restart
```

---

## 3️⃣ Device Connection

### Connect Physical Device

**Prerequisites**:
1. Enable **Developer Mode**: Settings → About Phone → Tap "Build Number" 7x
2. Enable **USB Debugging**: Settings → Developer Options → USB Debugging
3. Connect via USB cable

**Authenticate Connection**:
```bash
# List all connected devices
adb devices

# First connection may require on-device confirmation
# (Accept the RSA key fingerprint on your device)

# Verify connection
adb devices -l  # Long format with device details
```

**Output Example**:
```
List of attached devices
emulator-5554          device product:sdk_google_arm64 model:Android_SDK_built_for_x86_64 device:generic_x86_64
192.168.1.100:5555    device product:walleye model:Pixel_2 device:walleye
```

### Connect to Emulator

**Android Emulator (Android Studio)**:
```bash
# Emulator auto-starts ADB server on port 5554
adb devices
# Should show: emulator-5554 device

# If not visible, manually connect:
adb connect localhost:5554
```

**Connect to Remote Device** (WiFi):
```bash
# Requires USB first to enable network mode
adb tcpip 5555

# Then disconnect USB and connect via IP
adb connect 192.168.1.100:5555

# Disconnect when done
adb disconnect 192.168.1.100:5555
```

---

## 4️⃣ Core ADB Commands

### Device Information

```bash
# Get device property
adb shell getprop ro.build.version.sdk        # API level
adb shell getprop ro.product.manufacturer     # Manufacturer
adb shell getprop ro.product.model            # Device model
adb shell getprop ro.serialnumber             # Serial number
adb shell wm size                             # Screen resolution
adb shell getprop ro.boot.bootloader          # Bootloader version

# Get all properties
adb shell getprop
```

### Shell Execution

```bash
# Execute single command
adb shell date                    # Get device time
adb shell ps                      # List processes
adb shell df -h                   # Disk usage

# Run interactive shell (press Ctrl+D to exit)
adb shell
  $ ls /sdcard
  $ exit

# Execute with environment variables
adb shell "PATH=/system/bin:/vendor/bin ls /system/bin"
```

### File Operations

```bash
# Push file TO device
adb push local_file.txt /sdcard/remote_file.txt

# Pull file FROM device
adb pull /sdcard/screenshot.png ./local_screenshot.png

# List directory on device
adb shell ls -la /sdcard/

# Create directory on device
adb shell mkdir /sdcard/bots

# Delete file on device
adb shell rm /sdcard/old_file.txt
```

### Input Control

```bash
# Tap (click)
adb shell input tap 540 960       # Tap at coordinates (540, 960)

# Swipe (drag)
adb shell input swipe 100 500 100 100 500  # Swipe from (100,500) to (100,100), duration 500ms

# Key press
adb shell input keyevent 26       # Power button (keyevent 26)
adb shell input keyevent 3        # Home button
adb shell input keyevent 4        # Back button

# Text input (type)
adb shell input text "Hello World"

# Common keycodes:
# 3 = Home, 4 = Back, 26 = Power, 82 = Menu
# 113 = Volume Down, 115 = Volume Up, 121 = Volume Mute
```

### App Management

```bash
# Install APK
adb install app.apk
adb install -r app.apk            # Replace existing

# Uninstall app
adb uninstall com.example.app

# List installed packages
adb shell pm list packages
adb shell pm list packages -3     # Third-party apps only

# Check if app is installed
adb shell pm list packages | grep "game"

# Start activity
adb shell am start -n com.example.app/.MainActivity

# Force stop app
adb shell am force-stop com.example.app

# Get app PID
adb shell pidof com.example.app
```

### Logging

```bash
# View real-time logs
adb logcat
adb logcat | grep "my_tag"        # Filter by tag

# Save logs to file
adb logcat > logcat.txt

# Clear log buffer
adb logcat -c

# View logs with timestamps
adb logcat -v threadtime
```

### Screenshots & Screen Recording

```bash
# Capture screenshot
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png ./screen.png

# Record screen
adb shell screenrecord /sdcard/video.mp4   # Records for 3 minutes (max)

# Specify recording parameters
adb shell screenrecord --size 1280x720 /sdcard/video.mp4
```

---

## 5️⃣ Advanced Fundamentals

### Command Chaining

```bash
# Multiple commands in sequence (device-side)
adb shell "cmd1 && cmd2 && cmd3"
adb shell "input tap 540 960 && sleep 1 && input tap 540 1000"

# Sequential execution with delays (host-side)
adb shell input tap 540 960
sleep 1
adb shell input tap 540 1000
```

### Device State Checking

```bash
# Check if device is online
adb get-state           # Returns: offline, bootloader, or device

# Check if device is authorized (after pairing)
adb devices             # Shows "device" if authorized, "unauthorized" if not

# Verify connectivity with ping
adb shell ping -c 1 8.8.8.8

# Check network connectivity
adb shell netstat | head -20
```

### Performance Monitoring

```bash
# Monitor CPU usage
adb shell top -n 1 | head -20

# Memory usage
adb shell dumpsys meminfo | grep "Total"

# Battery status
adb shell dumpsys battery

# Disk space
adb shell df -h /sdcard
```

### Permissions

```bash
# Grant permission
adb shell pm grant com.example.app android.permission.CAMERA

# Revoke permission
adb shell pm revoke com.example.app android.permission.CAMERA

# Get app permissions
adb shell dumpsys package com.example.app | grep permission

# Get all dangerous permissions
adb shell pm list permissions -d
```

---

## 6️⃣ Error Handling & Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `error: device not found` | Device not connected | Check USB cable, run `adb devices` |
| `device unauthorized` | Device not trusted | Tap "Always allow" on device popup |
| `offline` | ADB daemon crashed | Run `adb kill-server && adb start-server` |
| `no space left on device` | Device storage full | Delete files: `adb shell rm /sdcard/*.tmp` |
| `permission denied` | Insufficient permissions | Use `adb root` (requires USB debugging) |

### Debug Techniques

```bash
# Enable verbose ADB logging
export ADB_DEBUG=1
adb devices

# Check ADB server status
adb status-window

# Restart ADB in verbose mode
adb kill-server
ADB_DEBUG=1 adb start-server
adb devices

# View ADB server socket (advanced)
netstat -an | grep 5037
```

### Connection Issues

```bash
# Connection refused
# → Check firewall, ensure port 5555 is open

# Device timeout
# → Check network connectivity, reduce workload

# USB connection unstable
# → Try different USB port, different USB cable

# Emulator connection
# → Ensure Android Studio is running
# → Check that emulator port matches (usually 5554)
```

---

## 7️⃣ Best Practices

✅ **DO**:
- Always check device is connected: `adb devices`
- Use device-side command chaining for atomic operations
- Implement retry logic for flaky connections
- Close ADB connections properly: `adb disconnect`
- Monitor device storage to avoid "no space" errors
- Use proper keycode values (reference Android documentation)

❌ **DON'T**:
- Run long-running commands without timeout
- Assume device state without verification
- Mix host-side and device-side shell operators
- Leave emulator running when not needed (consumes resources)
- Grant unnecessary permissions to apps
- Send rapid commands without delays (device may not keep up)

---

## 8️⃣ Quick Reference Table

| Task | Command |
|------|---------|
| List devices | `adb devices` |
| Get device info | `adb shell getprop` |
| Push file | `adb push local.txt /sdcard/remote.txt` |
| Pull file | `adb pull /sdcard/file.txt .` |
| Tap screen | `adb shell input tap X Y` |
| Swipe screen | `adb shell input swipe X1 Y1 X2 Y2` |
| Get screenshot | `adb shell screencap -p /sdcard/screen.png && adb pull /sdcard/screen.png` |
| Install app | `adb install app.apk` |
| Start app | `adb shell am start -n package/.Activity` |
| Force stop | `adb shell am force-stop package` |
| View logs | `adb logcat` |
| Clear logs | `adb logcat -c` |
| Device shell | `adb shell` |
| Disconnect | `adb disconnect` |

---

## Practice Exercise

**Level 1: Beginner**
1. Connect your device or emulator
2. Run `adb devices` and verify it shows as "device"
3. Take a screenshot using `adb shell screencap`
4. Pull it to your computer

**Level 2: Intermediate**
1. Get device API level using `getprop`
2. Install a test APK (download from apkmirror.com)
3. Tap the app icon at coordinates (540, 960)
4. View app logs with `adb logcat | grep "app"`

**Level 3: Advanced**
1. Create a shell script that:
   - Checks if device is connected
   - Gets screen resolution
   - Captures screenshot
   - Pulls screenshot locally
   - Analyzes image dimensions

---

**Status**: ✅ Foundational Knowledge Complete
**Next Module**: [device-management](./device-management.md)
