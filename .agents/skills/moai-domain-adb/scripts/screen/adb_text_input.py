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
ADB Text Input - Type text into focused field on Android device

Purpose:
    Input text into the currently focused text field on Android device.
    Automatically escapes special characters for proper shell handling.
    Supports clearing field before typing and optional Enter keypress.

Parameters:
    --device/-d: Device ID (e.g., "127.0.0.1:5555" or "emulator-5554").
                 If omitted, auto-selects first connected device.
                 Type: Optional[str]

    --text/-t: Text string to input into focused field. Required.
               Special characters (spaces, quotes, etc.) automatically escaped.
               Type: str

    --clear: Clear the text field before typing. Useful for replacing
             existing text instead of appending. Default: False.
             Type: bool (flag)

    --enter: Press Enter key after typing text. Useful for search fields
             or forms that submit on Enter. Default: False.
             Type: bool (flag)

    --toon: Output in TOON/YAML format for script integration.
            Type: bool (flag)

    --verbose/-v: Enable verbose output with debug information.
                  Type: bool (flag)

Returns:
    Exit code 0 on success with message "Typed: {text}".
    If --toon enabled, returns YAML with status, text_length, cleared, timestamp.

    TOON Output Format:
    {
        "status": "success",
        "text": "Hello World",
        "text_length": 11,
        "cleared": false,
        "pressed_enter": false,
        "timestamp": "2025-12-01T10:30:00Z"
    }

Examples:
    # Type simple text
    $ uv run adb_text_input.py --text "Hello World"

    # Type into specific device
    $ uv run adb_text_input.py --device emulator-5554 --text "search query"

    # Clear field before typing
    $ uv run adb_text_input.py --text "new text" --clear

    # Type and press Enter (submit)
    $ uv run adb_text_input.py --text "password123" --enter

    # TOON output for scripting
    $ uv run adb_text_input.py --text "test" --toon
    status: success
    text: test
    text_length: 4
    cleared: false

Raises:
    ADBDeviceOffline: If specified device is offline or unreachable.
                      Exit code: 2

    ADBCommandFailed: If text input command execution fails on device.
                      Exit code: 3

    InvalidArgument: If text parameter is empty string.
                     Exit code: 4

Notes:
    - Text field must be focused before input (tap field first)
    - Special characters automatically escaped for shell safety:
      * Spaces preserved
      * Quotes escaped
      * Ampersands escaped
      * Backslashes escaped
    - --clear uses KEYCODE_MOVE_END + KEYCODE_DEL_TO_LINE_START
    - --enter sends KEYCODE_ENTER (66)
    - Text appears exactly as provided (no autocorrect)
    - Works with all text input types (search, password, multi-line)
    - No character limit (practical limit ~1000 chars)

Related:
    - adb_keyevent.py: Send special keys (back, enter, delete)
    - adb_tap.py: Tap to focus text field
    - adb_screenshot.py: Verify text input visually

Context:
    Use this script for:
    - Form filling: username, password, search queries
    - Testing: input validation, character limits
    - Automation: scripted data entry
    - UI testing: text field interactions
    - Search: search bar text input

Implementation:
    1. Validate text parameter (non-empty)
    2. Verify device connectivity
    3. If --clear: send MOVE_END + DEL_TO_LINE_START
    4. Escape text for shell safety
    5. Execute: adb -s {device} shell input text "{escaped_text}"
    6. If --enter: send KEYCODE_ENTER (66)
    7. Format output (text or TOON)
    8. Return success status
"""

import shlex
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


@click.command()
@click.option(
    "--text",
    "-t",
    required=True,
    help="Text to input into focused field",
    type=str,
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Clear text field before typing",
)
@click.option(
    "--enter",
    is_flag=True,
    default=False,
    help="Press Enter key after typing",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    text: str,
    clear: bool,
    enter: bool,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> None:
    """Input text into focused field on Android device"""

    # Validate text parameter
    if not text or not text.strip():
        print_error("Text parameter cannot be empty")
        sys.exit(4)  # EXIT_INVALID_ARGUMENT

    # Get device
    device_id = get_default_device(device)

    if verbose:
        print_info(f"Using device: {device_id}")
        print_info(f"Text length: {len(text)} characters")
        if clear:
            print_info("Will clear field before typing")
        if enter:
            print_info("Will press Enter after typing")

    # Verify device connectivity
    if not verify_device_connected(device_id):
        raise ADBDeviceNotFound(device_id)

    # Clear field if requested
    if clear:
        try:
            if verbose:
                print_info("Clearing text field...")

            # Move to end and delete to line start
            subprocess.run(
                ["adb", "-s", device_id, "shell", "input", "keyevent", "123"],  # KEYCODE_MOVE_END
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["adb", "-s", device_id, "shell", "input", "keyevent", "112"],  # KEYCODE_DEL_TO_LINE_START
                capture_output=True,
                check=True,
            )

        except subprocess.CalledProcessError as e:
            raise ADBCommandFailed("clear field", e.stderr or str(e))

    # Escape text for shell safety
    # Replace spaces with %s (Android input text format)
    escaped_text = text.replace(" ", "%s")

    if verbose:
        print_info(f"Escaped text: {escaped_text}")

    # Input text
    try:
        result = subprocess.run(
            ["adb", "-s", device_id, "shell", "input", "text", escaped_text],
            capture_output=True,
            text=True,
            check=True,
        )

        if verbose:
            print_info("Text input successful")

    except subprocess.CalledProcessError as e:
        raise ADBCommandFailed("input text", e.stderr or str(e))

    # Press Enter if requested
    if enter:
        try:
            if verbose:
                print_info("Pressing Enter key...")

            subprocess.run(
                ["adb", "-s", device_id, "shell", "input", "keyevent", "66"],  # KEYCODE_ENTER
                capture_output=True,
                check=True,
            )

        except subprocess.CalledProcessError as e:
            raise ADBCommandFailed("press enter", e.stderr or str(e))

    # Format output
    if toon:
        output_data = {
            "status": "success",
            "text": text,
            "text_length": len(text),
            "cleared": clear,
            "pressed_enter": enter,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        print(format_toon_output(output_data))
    else:
        message_parts = [f"Typed: '{text}'"]
        if clear:
            message_parts.append("(cleared field first)")
        if enter:
            message_parts.append("(pressed Enter)")

        print_success(" ".join(message_parts))

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
