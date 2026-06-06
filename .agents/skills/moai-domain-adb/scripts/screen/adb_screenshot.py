#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0.0",
#     "pydantic>=2.12.4",
#     "anyio>=4.11.0",
#     "adbutils>=2.12.0",
#     "opencv-python>=4.12.0",
#     "av>=16.0.1",
#     "pillow>=12.0.0",
#     "pytesseract>=0.3.13",
#     "psutil>=7.1.3",
#     "numpy>=2.2.6",
# ]
# ///
"""
ADB Screenshot - Capture screenshot from Android device

Purpose:
    Capture screenshot from connected Android device and save to file.
    Auto-generates timestamped filename if output path not specified.
    Supports TOON/YAML output for automation pipelines.
    Returns image resolution and save location.

Parameters:
    --device/-d: Device serial number (optional, uses default if not specified)
    --output/-o: Output path for PNG file (auto-generates if not provided)
    --toon: Enable TOON/YAML output format for automation
    --verbose/-v: Enable verbose logging for debugging

Returns:
    Text mode: Success message with file path and resolution
    TOON mode: YAML with {status, file_path, resolution, timestamp}
    Exit code: 0 (success), 2 (device offline), 3 (ADB command failed), 4 (file write error)

Examples:
    # Auto-generate filename (screenshot_YYYYMMDD_HHMMSS.png)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_screenshot.py

    # Save to specific path
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_screenshot.py \\
        --output /tmp/screen.png

    # Specify device
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_screenshot.py \\
        --device emulator-5554 \\
        --output screen.png

    # Automation with TOON output
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_screenshot.py \\
        --toon \\
        --output latest.png

Raises:
    ADBError(EXIT_DEVICE_OFFLINE): Device disconnected or offline
    ADBError(EXIT_ADB_COMMAND_FAILED): Screenshot capture failed
    ADBError(EXIT_FILE_WRITE_ERROR): Cannot write output file

Notes:
    - Output directory is created automatically if it doesn't exist
    - Default filename uses timestamp: screenshot_YYYYMMDD_HHMMSS.png
    - Supports PNG format only (standard ADB screenshot format)
    - Resolution detected automatically from captured image
    - File path is always absolute in output (resolved path)

Related:
    - adb_tap.py: Tap at screen coordinates
    - adb_swipe.py: Swipe gesture between coordinates
    - adb_screen_record.py: Record screen video

Context:
    Use this when you need to:
    - Capture current device screen state for debugging
    - Take screenshots during automated testing
    - Document UI states or error conditions
    - Verify game/app visual state in automation

Implementation:
    1. Resolve device serial (default or specified)
    2. Verify device is connected and online
    3. Generate output path (auto or user-specified)
    4. Execute ADB screenshot command via device wrapper
    5. Save PIL Image to PNG file
    6. Return file path and image resolution
    7. Format output as text or TOON based on flags

Exit Codes:
    0 - Screenshot captured successfully
    2 - Device offline/disconnected
    3 - ADB screenshot command failed
    4 - File write error
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import click
from rich.console import Console

# Add adbautoplayer to path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "adbautoplayer" / "src-tauri" / "src-python"))

from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError

# Import common utilities
COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))

from cli_utils import toon_output_option, verbose_option, print_success, print_error, print_info, format_toon_output
from error_handlers import handle_adb_errors, ADBError, EXIT_SUCCESS, EXIT_DEVICE_OFFLINE, EXIT_ADB_COMMAND_FAILED

console = Console()

# Custom exit code for file errors
EXIT_FILE_WRITE_ERROR = 4


@click.command()
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Output path for PNG file (auto-generates if not provided)",
)
@toon_output_option
@verbose_option
@handle_adb_errors
def screenshot(
    output: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """Capture screenshot from Android device and save to file"""

    # Generate output path if not specified
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"screenshot_{timestamp}.png"

    output_path = Path(output).resolve()

    # Create parent directory if needed
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ADBError(
            f"Cannot create directory {output_path.parent}: {e}",
            exit_code=EXIT_FILE_WRITE_ERROR,
        )

    if verbose:
        print_info(f"Capturing screenshot to: {output_path}")

    # Create device wrapper
    try:
        device_wrapper = AdbDeviceWrapper.create_from_settings()
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to initialize device: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Take screenshot
    try:
        screenshot_img = device_wrapper.screenshot()

        if screenshot_img is None:
            raise ADBError(
                "Screenshot capture returned None",
                exit_code=EXIT_ADB_COMMAND_FAILED,
            )
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to capture screenshot: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Save to file
    try:
        screenshot_img.save(str(output_path))
    except Exception as e:
        raise ADBError(
            f"Failed to save screenshot to {output_path}: {e}",
            exit_code=EXIT_FILE_WRITE_ERROR,
        )

    # Get image resolution
    resolution = f"{screenshot_img.size[0]}x{screenshot_img.size[1]}"

    # Output result
    if toon:
        output_data = {
            "status": "success",
            "file_path": str(output_path),
            "resolution": resolution,
            "timestamp": datetime.now().isoformat(),
        }
        print(format_toon_output(output_data))
    else:
        print_success(f"Screenshot saved to: {output_path}")
        print_info(f"Resolution: {resolution}")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(screenshot())
