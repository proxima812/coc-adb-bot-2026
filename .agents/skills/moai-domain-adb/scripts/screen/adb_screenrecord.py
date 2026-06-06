#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///
"""
ADB Screenrecord - Record screen video from Android device

Purpose:
    Record screen video from Android device and save to local filesystem.
    Supports configurable duration, bitrate, and resolution. Displays
    progress bar during recording. Automatically pulls video from device
    and cleans up temporary files.

Parameters:
    --device/-d: Device ID (e.g., "127.0.0.1:5555" or "emulator-5554").
                 If omitted, auto-selects first connected device.
                 Type: Optional[str]

    --output/-o: Output file path for video. If omitted, auto-generates
                 filename: screenrecord_{timestamp}.mp4. Parent directories
                 created automatically. Type: Optional[str]

    --duration: Recording duration in seconds. Range: 1-180.
                Default: 60. Android screenrecord limit: 180 seconds.
                Type: int

    --bitrate: Video bitrate in Mbps. Higher = better quality, larger file.
               Default: 20. Recommended: 4-20 Mbps. Format: number or "XM".
               Type: str

    --size: Video resolution as WIDTHxHEIGHT (e.g., "1280x720").
            If omitted, uses device native resolution.
            Type: Optional[str]

    --toon: Output in TOON/YAML format for script integration.
            Type: bool (flag)

    --verbose/-v: Enable verbose output with debug information.
                  Type: bool (flag)

Returns:
    Exit code 0 on success with message "Recording saved to {path}".
    If --toon enabled, returns YAML with status, file_path, duration, file_size.

    TOON Output Format:
    {
        "status": "success",
        "file_path": "/path/to/video.mp4",
        "duration": 60,
        "file_size": 15728640,
        "file_size_mb": 15.0,
        "timestamp": "2025-12-01T10:30:00Z"
    }

Examples:
    # Record 60 seconds (default)
    $ uv run adb_screenrecord.py

    # Record 30 seconds to specific file
    $ uv run adb_screenrecord.py --output demo.mp4 --duration 30

    # Record 2 minutes at 10 Mbps bitrate
    $ uv run adb_screenrecord.py --duration 120 --bitrate 10

    # Record at 720p resolution
    $ uv run adb_screenrecord.py --size 1280x720 --duration 60

    # TOON output for scripting
    $ uv run adb_screenrecord.py --duration 10 --toon
    status: success
    file_path: /path/to/screenrecord_1234567890.mp4
    duration: 10
    file_size: 5242880

Raises:
    ADBDeviceOffline: If specified device is offline or unreachable.
                      Exit code: 2

    ADBCommandFailed: If screenrecord command fails or file pull fails.
                      Exit code: 3

    InvalidArgument: If duration out of range (1-180) or size invalid.
                     Exit code: 4

Notes:
    - Android screenrecord maximum duration: 180 seconds (3 minutes)
    - Video saved to device /sdcard/ first, then pulled to local
    - Temporary device file automatically cleaned up after pull
    - Progress bar displays during recording
    - Recording can be interrupted with Ctrl+C (cancels gracefully)
    - Bitrate affects quality and file size:
      * 4 Mbps: Low quality, ~30 MB/min
      * 10 Mbps: Medium quality, ~75 MB/min
      * 20 Mbps: High quality, ~150 MB/min
    - Resolution defaults to device native (e.g., 1080p)
    - Video codec: H.264/AVC
    - Container format: MP4
    - Audio NOT recorded (screenrecord limitation)

Related:
    - adb_screenshot.py: Capture single frame
    - adb_tap.py: Interact with device during recording
    - adb_keyevent.py: Navigate device during recording

Context:
    Use this script for:
    - UI testing: Record test execution
    - Bug reports: Capture issue reproduction
    - Demos: Record feature demonstrations
    - Documentation: Create tutorial videos
    - Performance: Analyze UI performance visually

Implementation:
    1. Validate duration (1-180) and size format (WIDTHxHEIGHT)
    2. Generate output path if not provided
    3. Verify device connectivity
    4. Create device temp path: /sdcard/screenrecord_{timestamp}.mp4
    5. Execute: adb shell screenrecord --time-limit {duration} --bit-rate {bitrate}M {device_temp}
    6. Display progress bar for duration seconds
    7. Pull video: adb pull {device_temp} {output_path}
    8. Verify file exists and get size
    9. Clean up device temp file
    10. Format output (text or TOON)
    11. Return success status
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.progress import Progress

# Add common utilities to path
SCRIPT_DIR = Path(__file__).resolve().parent
COMMON_DIR = SCRIPT_DIR.parent / "common"
sys.path.insert(0, str(COMMON_DIR))

from adb_utils import get_default_device, verify_device_connected
from cli_utils import (
    console,
    device_option,
    format_toon_output,
    print_error,
    print_info,
    print_success,
    print_warning,
    toon_output_option,
    verbose_option,
)
from error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_SUCCESS,
    ADBCommandFailed,
    ADBDeviceNotFound,
    ADBError,
    handle_adb_errors,
)
from path_utils import setup_adbautoplayer_path

# Setup adbautoplayer Python path
setup_adbautoplayer_path()


@click.command()
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Output file path (default: screenrecord_{timestamp}.mp4)",
)
@click.option(
    "--duration",
    default=60,
    type=int,
    help="Recording duration in seconds (1-180, default: 60)",
)
@click.option(
    "--bitrate",
    default="20",
    type=str,
    help="Video bitrate in Mbps (default: 20)",
)
@click.option(
    "--size",
    default=None,
    type=str,
    help="Video size as WIDTHxHEIGHT (e.g., 1280x720)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    output: Optional[str],
    duration: int,
    bitrate: str,
    size: Optional[str],
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> None:
    """Record screen video from Android device"""

    # Validate duration
    if duration < 1 or duration > 180:
        print_error(f"Invalid duration: must be between 1-180 seconds, got {duration}")
        sys.exit(4)  # EXIT_INVALID_ARGUMENT

    # Validate size format if provided
    if size:
        if "x" not in size.lower():
            print_error(f"Invalid size format: must be WIDTHxHEIGHT (e.g., 1280x720), got '{size}'")
            sys.exit(4)  # EXIT_INVALID_ARGUMENT

        parts = size.lower().split("x")
        if len(parts) != 2:
            print_error(f"Invalid size format: must have exactly one 'x' separator, got '{size}'")
            sys.exit(4)  # EXIT_INVALID_ARGUMENT

        try:
            width = int(parts[0])
            height = int(parts[1])

            if width <= 0 or height <= 0:
                print_error(f"Invalid size: width and height must be positive, got {width}x{height}")
                sys.exit(4)  # EXIT_INVALID_ARGUMENT
        except ValueError:
            print_error(f"Invalid size: width and height must be integers, got '{size}'")
            sys.exit(4)  # EXIT_INVALID_ARGUMENT

    # Format bitrate
    if not bitrate.endswith("M"):
        bitrate = f"{bitrate}M"

    # Generate output path if not specified
    if not output:
        timestamp = int(time.time())
        output = f"screenrecord_{timestamp}.mp4"

        if verbose:
            print_info(f"Generated output filename: {output}")

    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if verbose:
        print_info(f"Output path: {output_path}")

    # Device temp path
    timestamp = int(time.time())
    device_temp = f"/sdcard/screenrecord_{timestamp}.mp4"

    if verbose:
        print_info(f"Device temp path: {device_temp}")

    # Get device
    device_id = get_default_device(device)

    if verbose:
        print_info(f"Using device: {device_id}")

    # Verify device connectivity
    if not verify_device_connected(device_id):
        raise ADBDeviceNotFound(device_id)

    # Build screenrecord command
    cmd = [
        "adb",
        "-s",
        device_id,
        "shell",
        "screenrecord",
        f"--time-limit {duration}",
        f"--bit-rate {bitrate}",
    ]

    if size:
        cmd.append(f"--size {size}")

    cmd.append(device_temp)

    if verbose:
        print_info(f"Recording command: {' '.join(cmd)}")

    # Start recording
    try:
        print_info(f"Recording {duration}s video at {bitrate} bitrate...")

        # Start recording in background
        recording_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for recording with progress bar
        with Progress() as progress:
            task = progress.add_task("[cyan]Recording...", total=duration)
            for _ in range(duration):
                time.sleep(1)
                progress.update(task, advance=1)

        # Wait for recording to finish
        recording_process.wait(timeout=10)

        if recording_process.returncode != 0:
            stderr = recording_process.stderr.read().decode()
            raise ADBCommandFailed("screenrecord", stderr)

    except subprocess.TimeoutExpired:
        recording_process.kill()
        raise ADBCommandFailed(
            "screenrecord",
            "Recording process timed out after completion",
        )
    except KeyboardInterrupt:
        recording_process.kill()
        print_warning("Recording interrupted")
        sys.exit(EXIT_ADB_COMMAND_FAILED)
    except Exception as e:
        raise ADBCommandFailed("screenrecord", str(e))

    # Pull video from device
    try:
        print_info("Pulling video from device...")

        pull_result = subprocess.run(
            ["adb", "-s", device_id, "pull", device_temp, str(output_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

        if verbose:
            print_info(f"Pull output: {pull_result.stdout}")

    except subprocess.CalledProcessError as e:
        raise ADBCommandFailed("adb pull", e.stderr or str(e))
    except subprocess.TimeoutExpired:
        raise ADBCommandFailed("adb pull", "Pull operation timed out (60s)")

    # Verify file exists
    if not output_path.exists():
        raise ADBCommandFailed(
            "file verification",
            f"Video file not created at {output_path}",
        )

    # Get file size
    file_size = output_path.stat().st_size
    size_mb = file_size / (1024 * 1024)

    if verbose:
        print_info(f"Video file size: {size_mb:.2f} MB")

    # Clean up device file
    try:
        subprocess.run(
            ["adb", "-s", device_id, "shell", "rm", device_temp],
            capture_output=True,
            timeout=10,
        )

        if verbose:
            print_info("Cleaned up device temp file")

    except Exception as e:
        if verbose:
            print_warning(f"Failed to clean up device temp file: {e}")

    # Format output
    if toon:
        output_data = {
            "status": "success",
            "file_path": str(output_path),
            "duration": duration,
            "file_size": file_size,
            "file_size_mb": round(size_mb, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        print(format_toon_output(output_data))
    else:
        print_success(f"Recording saved to {output_path}")
        print_info(f"Size: {size_mb:.1f} MB")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
