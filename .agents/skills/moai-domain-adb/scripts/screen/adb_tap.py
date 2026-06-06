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
ADB Tap - Tap at screen coordinates on Android device

Purpose:
    Send tap/click event at specified screen coordinates.
    Supports multiple taps with custom delays between taps.
    Coordinates are in pixels relative to screen resolution.
    Supports TOON/YAML output for automation pipelines.

Parameters:
    --device/-d: Device serial number (optional, uses default if not specified)
    --x: X coordinate in pixels (required)
    --y: Y coordinate in pixels (required)
    --count: Number of taps to perform (default: 1)
    --delay: Delay between taps in seconds (default: 0.5)
    --toon: Enable TOON/YAML output format for automation
    --verbose/-v: Enable verbose logging for debugging

Returns:
    Text mode: Success message with coordinates and tap count
    TOON mode: YAML with {status, coordinates: {x, y}, count, timestamp}
    Exit code: 0 (success), 2 (device offline), 3 (ADB command failed), 4 (invalid coordinates)

Examples:
    # Single tap
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_tap.py \\
        --x 500 --y 1000

    # Multiple taps with delay (simulates rapid clicking)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_tap.py \\
        --x 500 --y 1000 \\
        --count 5 --delay 1

    # Double tap (quick succession)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_tap.py \\
        --x 500 --y 1000 \\
        --count 2 --delay 0.1

    # Specify device
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_tap.py \\
        --device emulator-5554 \\
        --x 540 --y 960

    # Automation with TOON output
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_tap.py \\
        --toon \\
        --x 100 --y 200 \\
        --count 3

Raises:
    ADBError(EXIT_DEVICE_OFFLINE): Device disconnected or offline
    ADBError(EXIT_ADB_COMMAND_FAILED): Tap command failed
    ADBError(EXIT_INVALID_INPUT): Invalid coordinates (negative or out of range)

Notes:
    - Coordinates start at (0,0) in top-left corner
    - X increases right, Y increases downward
    - Coordinates should match device screen resolution (e.g., 1080x1920)
    - Count must be >= 1 (validation automatic)
    - Delay between taps helps with UI responsiveness
    - Multiple taps with 0 delay may be throttled by system

Related:
    - adb_swipe.py: Swipe gesture between coordinates
    - adb_screenshot.py: Capture screen after tap
    - adb_longpress.py: Long press at coordinates

Context:
    Use this when you need to:
    - Click buttons or UI elements during automation
    - Simulate user touch input in games/apps
    - Trigger actions at specific screen positions
    - Perform repeated clicking (farming, collecting rewards)

Implementation:
    1. Resolve device serial (default or specified)
    2. Verify device is connected and online
    3. Validate coordinates (x >= 0, y >= 0)
    4. Create AdbController instance
    5. Loop count times:
        a. Send tap command via controller.tap()
        b. Wait delay seconds between taps
    6. Return tap confirmation with coordinates
    7. Format output as text or TOON based on flags

Exit Codes:
    0 - Tap successful
    2 - Device offline/disconnected
    3 - ADB tap command failed
    4 - Invalid coordinates
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
import click
from rich.console import Console

# Add adbautoplayer to path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "adbautoplayer" / "src-tauri" / "src-python"))

from adb_auto_player.device.adb.adb_controller import AdbController
from adb_auto_player.models.geometry import Coordinates
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError

# Import common utilities
COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))

from cli_utils import toon_output_option, verbose_option, print_success, print_error, print_info, format_toon_output
from error_handlers import handle_adb_errors, ADBError, EXIT_SUCCESS, EXIT_DEVICE_OFFLINE, EXIT_ADB_COMMAND_FAILED

console = Console()

# Custom exit code for invalid input
EXIT_INVALID_INPUT = 4


@click.command()
@click.option(
    "--x",
    required=True,
    type=int,
    help="X coordinate in pixels",
)
@click.option(
    "--y",
    required=True,
    type=int,
    help="Y coordinate in pixels",
)
@click.option(
    "--count",
    default=1,
    type=int,
    help="Number of taps to perform (default: 1)",
)
@click.option(
    "--delay",
    default=0.5,
    type=float,
    help="Delay between taps in seconds (default: 0.5)",
)
@toon_output_option
@verbose_option
@handle_adb_errors
def tap(
    x: int,
    y: int,
    count: int,
    delay: float,
    toon: bool,
    verbose: bool,
) -> int:
    """Tap at screen coordinates on Android device"""

    # Validate coordinates
    if x < 0 or y < 0:
        raise ADBError(
            f"Invalid coordinates: x={x}, y={y} (must be >= 0)",
            exit_code=EXIT_INVALID_INPUT,
        )

    # Validate count
    if count < 1:
        raise ADBError(
            f"Invalid count: {count} (must be >= 1)",
            exit_code=EXIT_INVALID_INPUT,
        )

    if verbose:
        print_info(f"Tapping at ({x}, {y}) {count} time(s) with {delay}s delay")

    # Create controller
    try:
        controller = AdbController()
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to initialize ADB controller: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Perform taps
    coordinates = Coordinates(x=x, y=y)

    try:
        for i in range(count):
            if verbose:
                print_info(f"Tap {i + 1}/{count} at ({x}, {y})")

            controller.tap(coordinates)

            # Delay between taps (skip after last tap)
            if i < count - 1:
                time.sleep(delay)
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to tap at ({x}, {y}): {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Output result
    if toon:
        output_data = {
            "status": "success",
            "coordinates": {"x": x, "y": y},
            "count": count,
            "timestamp": datetime.now().isoformat(),
        }
        print(format_toon_output(output_data))
    else:
        tap_text = "tap" if count == 1 else "taps"
        print_success(f"Tapped at ({x}, {y}) {count} {tap_text}")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(tap())
