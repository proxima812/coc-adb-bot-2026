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
ADB Swipe - Swipe gesture on Android device screen

Purpose:
    Send swipe/drag gesture from start to end coordinates.
    Supports custom duration and preset directions (up/down/left/right).
    Coordinates are in pixels relative to screen resolution.
    Supports TOON/YAML output for automation pipelines.

Parameters:
    --device/-d: Device serial number (optional, uses default if not specified)
    --start: Start coordinates as "x,y" (required unless using preset)
    --end: End coordinates as "x,y" (required unless using preset)
    --duration: Swipe duration in milliseconds (default: 300)
    --preset: Preset direction (up/down/left/right) - overrides start/end
    --toon: Enable TOON/YAML output format for automation
    --verbose/-v: Enable verbose logging for debugging

Returns:
    Text mode: Success message with start/end coordinates and duration
    TOON mode: YAML with {status, swipe: {start, end, duration}, timestamp}
    Exit code: 0 (success), 2 (device offline), 3 (ADB command failed), 4 (invalid input)

Examples:
    # Custom coordinates (vertical swipe from bottom to top)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --start 500,1500 --end 500,500 --duration 300

    # Preset direction (swipe up on standard 1080x1920 screen)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --preset up

    # Horizontal swipe (scroll left)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --start 800,960 --end 200,960 --duration 200

    # Slow swipe (1 second duration)
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --preset down --duration 1000

    # Specify device
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --device emulator-5554 \\
        --preset right

    # Automation with TOON output
    $ uv run .claude/skills/moai-domain-adb/scripts/screen/adb_swipe.py \\
        --toon \\
        --start 100,200 --end 900,200 \\
        --duration 500

Raises:
    ADBError(EXIT_DEVICE_OFFLINE): Device disconnected or offline
    ADBError(EXIT_ADB_COMMAND_FAILED): Swipe command failed
    ADBError(EXIT_INVALID_INPUT): Invalid coordinates or missing parameters

Notes:
    - Coordinates start at (0,0) in top-left corner
    - Duration controls swipe speed (shorter = faster)
    - Typical durations: 200-500ms for UI scrolling
    - Presets are optimized for 1080x1920 resolution (BlueStacks default):
        * up: (540,1500) → (540,500) - scroll content upward
        * down: (540,500) → (540,1500) - scroll content downward
        * left: (800,960) → (200,960) - swipe left/scroll right
        * right: (200,960) → (800,960) - swipe right/scroll left
    - Preset overrides --start and --end if provided
    - Swipe direction affects content scrolling (opposite to finger movement)

Related:
    - adb_tap.py: Tap at screen coordinates
    - adb_screenshot.py: Capture screen before/after swipe
    - adb_scroll.py: Scroll by content amount

Context:
    Use this when you need to:
    - Scroll through lists, menus, or content
    - Navigate between screens with swipe gestures
    - Simulate drag-and-drop operations
    - Trigger swipe-based UI interactions (refresh, dismiss, etc.)

Implementation:
    1. Resolve device serial (default or specified)
    2. Verify device is connected and online
    3. Parse preset (if provided) or validate start/end coordinates
    4. Convert coordinate strings to (x,y) tuples
    5. Validate coordinates (x >= 0, y >= 0)
    6. Create AdbDeviceWrapper instance
    7. Execute swipe command via device.swipe()
    8. Convert duration from milliseconds to seconds
    9. Return swipe confirmation with coordinates
    10. Format output as text or TOON based on flags

Exit Codes:
    0 - Swipe successful
    2 - Device offline/disconnected
    3 - ADB swipe command failed
    4 - Invalid coordinates or parameters
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import click
from rich.console import Console

# Add adbautoplayer to path
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "adbautoplayer" / "src-tauri" / "src-python"))

from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper
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

# Preset gestures for 1080x1920 resolution (BlueStacks default)
PRESETS = {
    "up": {"start": (540, 1500), "end": (540, 500), "duration": 300},
    "down": {"start": (540, 500), "end": (540, 1500), "duration": 300},
    "left": {"start": (800, 960), "end": (200, 960), "duration": 300},
    "right": {"start": (200, 960), "end": (800, 960), "duration": 300},
}


def parse_coordinates(coord_str: str) -> Tuple[int, int]:
    """Parse coordinate string 'x,y' into tuple (x, y)"""
    try:
        parts = coord_str.split(",")
        if len(parts) != 2:
            raise ValueError("Coordinates must be in format 'x,y'")
        x, y = int(parts[0].strip()), int(parts[1].strip())
        if x < 0 or y < 0:
            raise ValueError("Coordinates must be non-negative")
        return x, y
    except ValueError as e:
        raise ADBError(
            f"Invalid coordinates '{coord_str}': {e}",
            exit_code=EXIT_INVALID_INPUT,
        )


@click.command()
@click.option(
    "--start",
    default=None,
    type=str,
    help="Start coordinates as 'x,y' (required unless using preset)",
)
@click.option(
    "--end",
    default=None,
    type=str,
    help="End coordinates as 'x,y' (required unless using preset)",
)
@click.option(
    "--duration",
    default=300,
    type=int,
    help="Swipe duration in milliseconds (default: 300)",
)
@click.option(
    "--preset",
    default=None,
    type=click.Choice(["up", "down", "left", "right"], case_sensitive=False),
    help="Preset direction (up/down/left/right)",
)
@toon_output_option
@verbose_option
@handle_adb_errors
def swipe(
    start: Optional[str],
    end: Optional[str],
    duration: int,
    preset: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """Swipe gesture on Android device screen"""

    # Handle preset
    if preset:
        preset_lower = preset.lower()
        preset_data = PRESETS[preset_lower]
        start_coords = preset_data["start"]
        end_coords = preset_data["end"]
        duration = preset_data["duration"]

        if verbose:
            print_info(f"Using preset '{preset_lower}': {start_coords} → {end_coords}")
    else:
        # Validate coordinates provided
        if not start or not end:
            raise ADBError(
                "Start and end coordinates required (or use --preset)",
                exit_code=EXIT_INVALID_INPUT,
            )

        # Parse coordinates
        start_coords = parse_coordinates(start)
        end_coords = parse_coordinates(end)

    # Validate duration
    if duration <= 0:
        raise ADBError(
            f"Invalid duration: {duration}ms (must be > 0)",
            exit_code=EXIT_INVALID_INPUT,
        )

    if verbose:
        print_info(
            f"Swiping from {start_coords} to {end_coords} over {duration}ms"
        )

    # Create device wrapper
    try:
        device_wrapper = AdbDeviceWrapper.create_from_settings()
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to initialize device: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Perform swipe
    try:
        start_x, start_y = start_coords
        end_x, end_y = end_coords

        device_wrapper.swipe(
            Coordinates(x=start_x, y=start_y),
            Coordinates(x=end_x, y=end_y),
            duration / 1000.0,  # Convert ms to seconds
        )
    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        raise ADBError(
            f"Failed to swipe from {start_coords} to {end_coords}: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Output result
    if toon:
        output_data = {
            "status": "success",
            "swipe": {
                "start": {"x": start_coords[0], "y": start_coords[1]},
                "end": {"x": end_coords[0], "y": end_coords[1]},
                "duration_ms": duration,
            },
            "timestamp": datetime.now().isoformat(),
        }
        print(format_toon_output(output_data))
    else:
        print_success(
            f"Swiped from {start_coords} to {end_coords} over {duration}ms"
        )

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(swipe())
