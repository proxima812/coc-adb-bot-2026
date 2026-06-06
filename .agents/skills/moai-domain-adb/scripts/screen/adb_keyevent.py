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
ADB Keyevent - Send key events to Android device

Purpose:
    Send system key events (back, home, menu, power, volume, enter, delete)
    to Android devices. Supports both key names and raw Android key codes.
    Provides repeated keypress support via --count option.

Parameters:
    --device/-d: Device ID (e.g., "127.0.0.1:5555" or "emulator-5554").
                 If omitted, auto-selects first connected device.
                 Type: Optional[str]

    --key/-k: Key name or Android keycode to send. Supported names:
              back, home, menu, power, volume_up, volume_down, enter, delete.
              Also accepts raw keycode numbers (e.g., "4" for BACK).
              Required. Type: str

    --count/-c: Number of times to repeat the keyevent. Default: 1.
                Useful for rapid multiple presses (e.g., volume_up x3).
                Type: int

    --toon: Output in TOON/YAML format for script integration.
            Type: bool (flag)

    --verbose/-v: Enable verbose output with debug information.
                  Type: bool (flag)

Returns:
    Exit code 0 on success with message "Sent {count}x {key} event".
    If --toon enabled, returns YAML with status, key, count, timestamp.

    TOON Output Format:
    {
        "status": "success",
        "key": "back",
        "keycode": 4,
        "count": 1,
        "timestamp": "2025-12-01T10:30:00Z"
    }

Examples:
    # Press back button
    $ uv run adb_keyevent.py --key back

    # Press home button on specific device
    $ uv run adb_keyevent.py --device emulator-5554 --key home

    # Press volume up 3 times
    $ uv run adb_keyevent.py --key volume_up --count 3

    # Press raw keycode 66 (ENTER)
    $ uv run adb_keyevent.py --key 66

    # TOON output for scripting
    $ uv run adb_keyevent.py --key back --toon
    status: success
    key: back
    keycode: 4
    count: 1

Raises:
    ADBDeviceOffline: If specified device is offline or unreachable.
                      Exit code: 2

    ADBCommandFailed: If keyevent command execution fails on device.
                      Exit code: 3

    InvalidArgument: If key name is invalid or keycode out of range.
                     Exit code: 4

Notes:
    - Supported key names map to standard Android keycodes:
      * back (4), home (3), menu (82), power (26)
      * volume_up (24), volume_down (25)
      * enter (66), delete (67)
    - Raw keycodes accepted as numeric strings (e.g., "4")
    - Count parameter enables rapid repeated presses
    - No delay between repeated presses (instant)
    - Some keys may require special permissions (power button)
    - Works with both emulators and physical devices

Related:
    - adb_text_input.py: Type text into focused field
    - adb_tap.py: Tap screen coordinates
    - adb_swipe.py: Swipe gestures

Context:
    Use this script for:
    - Navigation: back, home, menu buttons
    - System control: power, volume keys
    - Input: enter, delete keys
    - Testing: repeated key presses
    - Automation: scripted key sequences

Implementation:
    1. Parse key parameter (name or numeric keycode)
    2. Verify device connectivity
    3. For each count iteration:
       - Execute: adb -s {device} shell input keyevent {keycode}
    4. Format output (text or TOON)
    5. Return success status
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

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

# No need to import adb_auto_player - using subprocess directly
import subprocess

# Android key codes mapping
KEYEVENTS = {
    "back": 4,
    "home": 3,
    "menu": 82,
    "power": 26,
    "volume_up": 24,
    "volume_down": 25,
    "enter": 66,
    "delete": 67,
}


@click.command()
@click.option(
    "--key",
    "-k",
    required=True,
    help="Key name (back, home, menu, power, volume_up, volume_down, enter, delete) or keycode number",
    type=str,
)
@click.option(
    "--count",
    "-c",
    default=1,
    help="Number of times to repeat keyevent (default: 1)",
    type=int,
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    key: str, count: int, device: Optional[str], toon: bool, verbose: bool
) -> None:
    """Send key event to Android device"""

    # Validate count parameter
    if count < 1:
        print_error(f"Invalid count: must be >= 1, got {count}")
        sys.exit(4)  # EXIT_INVALID_ARGUMENT

    # Parse key parameter (name or numeric keycode)
    if key.isdigit():
        keycode = int(key)
        key_name = f"keycode_{keycode}"

        if verbose:
            print_info(f"Using raw keycode: {keycode}")
    elif key in KEYEVENTS:
        keycode = KEYEVENTS[key]
        key_name = key

        if verbose:
            print_info(f"Mapped key '{key}' to keycode {keycode}")
    else:
        available = ", ".join(KEYEVENTS.keys())
        print_error(f"Unknown key: {key}. Available keys: {available}")
        sys.exit(4)  # EXIT_INVALID_ARGUMENT

    # Get device
    device_id = get_default_device(device)

    if verbose:
        print_info(f"Using device: {device_id}")

    # Verify device connectivity
    if not verify_device_connected(device_id):
        raise ADBDeviceNotFound(device_id)

    # Send keyevent(s)
    try:
        for i in range(count):
            if verbose and count > 1:
                print_info(f"Sending keyevent {i+1}/{count}...")

            # Execute: adb -s {device} shell input keyevent {keycode}
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "input", "keyevent", str(keycode)],
                capture_output=True,
                text=True,
                check=True,
            )

    except subprocess.CalledProcessError as e:
        raise ADBCommandFailed("input keyevent", e.stderr or str(e))

    # Format output
    if toon:
        output_data = {
            "status": "success",
            "key": key_name,
            "keycode": keycode,
            "count": count,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        print(format_toon_output(output_data))
    else:
        if count == 1:
            print_success(f"Sent {key_name} event")
        else:
            print_success(f"Sent {count}x {key_name} events")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
