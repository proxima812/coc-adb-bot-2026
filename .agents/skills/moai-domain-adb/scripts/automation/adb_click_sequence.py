#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pillow>=10.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///
"""
ADB Click Sequence - Execute single JSON automation sequence.

Purpose:
    Execute JSON sequence once (single pass). Simpler alternative to
    adb_game_loop for one-time automation tasks. Perfect for setup
    sequences, tutorial skips, and non-repeating actions.

Parameters:
    --device/-d: Device ID (optional, auto-selects if omitted). Type: str
    --sequence/-s: JSON sequence file path (required). Type: Path
    --toon: Output in TOON/YAML format (flag). Type: bool
    --verbose/-v: Verbose output with debug info (flag). Type: bool

Returns:
    Exit code 0 on success, non-zero on failure.
    TOON output: {status, steps_executed, total_steps, errors}

Examples:
    # Execute sequence once
    $ uv run adb_click_sequence.py --sequence tutorial_skip.json

    # Verbose mode with TOON output
    $ uv run adb_click_sequence.py -s setup.json -v --toon

    # Specify device
    $ uv run adb_click_sequence.py -s clicks.json -d 127.0.0.1:5555

Raises:
    ADBError: When device is offline or ADB command fails
    json.JSONDecodeError: When JSON sequence is malformed
    FileNotFoundError: When sequence file doesn't exist

Notes:
    - JSON format same as adb_game_loop.py
    - Supported actions: tap, swipe, wait, screenshot, keyevent, text_input
    - Error recovery: Continues on tap failures, exits on critical errors
    - Step-by-step progress output
    - No loop control (single execution)

Related:
    - adb_game_loop.py: Repeating sequence variant
    - adb_wait_for_app.py: Wait before sequence
    - adb_screenshot_compare.py: Verify sequence result

Context:
    Part of automation/ category in moai-domain-adb skill. Provides
    simple one-time sequence execution for setup and tutorial tasks.

Implementation:
    1. Load and validate JSON sequence
    2. Initialize ADB device connection
    3. Execute each step sequentially
    4. Handle errors and continue
    5. Output results (human or TOON)
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import click
from PIL import Image
from rich.console import Console

# Common utilities import
from common.adb_utils import get_default_device, verify_device_connected
from common.cli_utils import (
    device_option,
    format_toon_output,
    print_error,
    print_info,
    print_success,
    print_warning,
    toon_output_option,
    verbose_option,
)
from common.error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_DEVICE_OFFLINE,
    EXIT_INVALID_ARGUMENT,
    EXIT_SUCCESS,
    ADBError,
    handle_adb_errors,
)
from common.path_utils import setup_adbautoplayer_path

# Setup path to adbautoplayer
setup_adbautoplayer_path()

from adb_auto_player.device.adb.adb_controller import AdbController
from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError
from adb_auto_player.models.geometry import Coordinates

console = Console()


def validate_json_sequence(sequence_data: Dict[str, Any]) -> bool:
    """
    Purpose:
        Validate JSON sequence structure. Ensures required fields exist
        and action types are supported.

    Parameters:
        sequence_data: Loaded JSON sequence dictionary. Type: Dict[str, Any]

    Returns:
        True if valid, False otherwise. Type: bool

    Examples:
        >>> data = {"name": "Test", "steps": [{"action": "tap", "x": 100, "y": 200}]}
        >>> validate_json_sequence(data)
        True

    Raises:
        No exceptions. Returns False on validation failure.

    Notes:
        - Required fields: "steps" (list)
        - Supported actions: tap, swipe, wait, screenshot, keyevent, text_input
        - Validation logic shared with adb_game_loop.py

    Related:
        - execute_action(): Executes validated actions
        - main(): Calls this before execution

    Context:
        Validation prevents runtime errors from malformed JSON.

    Implementation:
        Same logic as adb_game_loop.py validation.
    """
    if "steps" not in sequence_data:
        print_error("Sequence missing 'steps' field")
        return False

    steps = sequence_data.get("steps", [])
    if not isinstance(steps, list):
        print_error("'steps' must be a list")
        return False

    if len(steps) == 0:
        print_error("Sequence has no steps")
        return False

    supported_actions = {"tap", "swipe", "wait", "screenshot", "keyevent", "text_input"}

    for i, step in enumerate(steps):
        if "action" not in step:
            print_error(f"Step {i + 1} missing 'action' field")
            return False

        action = step["action"]
        if action not in supported_actions:
            print_error(f"Step {i + 1}: Unsupported action '{action}'")
            return False

        # Validate action-specific fields
        if action == "tap":
            if "x" not in step or "y" not in step:
                print_error(f"Step {i + 1}: tap requires 'x' and 'y' fields")
                return False

        if action == "swipe":
            if "start" not in step or "end" not in step:
                print_error(f"Step {i + 1}: swipe requires 'start' and 'end' fields")
                return False

    return True


def execute_action(
    controller: AdbController,
    device: AdbDeviceWrapper,
    action: Dict[str, Any],
    step_num: int,
    total_steps: int,
    verbose: bool = False,
) -> bool:
    """
    Purpose:
        Execute a single action from JSON sequence with progress feedback.
        Supports all standard automation actions.

    Parameters:
        controller: ADB controller instance. Type: AdbController
        device: ADB device wrapper instance. Type: AdbDeviceWrapper
        action: Action dictionary from JSON. Type: Dict[str, Any]
        step_num: Current step number (1-indexed). Type: int
        total_steps: Total number of steps. Type: int
        verbose: Enable verbose output (default: False). Type: bool

    Returns:
        True if action succeeded, False if failed. Type: bool

    Examples:
        >>> execute_action(controller, device, {"action": "tap", "x": 100, "y": 200}, 1, 5)
        True

    Raises:
        No exceptions. Catches and logs errors internally.

    Notes:
        - Progress shown as [step/total] prefix
        - Same action logic as adb_game_loop.py
        - Error recovery: logs warning but continues

    Related:
        - validate_json_sequence(): Validates before execution
        - main(): Calls this for each step

    Context:
        Core execution logic for single-pass sequences.

    Implementation:
        Same as adb_game_loop.py with progress output.
    """
    action_type = action.get("action", "tap")

    if not verbose:
        console.print(f"[dim]  [{step_num}/{total_steps}] {action_type}[/dim]")
    else:
        print_info(f"[{step_num}/{total_steps}] Executing {action_type}: {action}")

    try:
        if action_type == "tap":
            x = action.get("x")
            y = action.get("y")
            count = action.get("count", 1)

            for _ in range(count):
                controller.tap(Coordinates(x=x, y=y))
                if count > 1:
                    time.sleep(0.1)

        elif action_type == "swipe":
            start = action.get("start")
            end = action.get("end")
            duration = action.get("duration", 300) / 1000.0

            device.swipe(
                Coordinates(x=start[0], y=start[1]),
                Coordinates(x=end[0], y=end[1]),
                duration,
            )

        elif action_type == "wait":
            duration = action.get("duration", 1)
            if verbose:
                print_info(f"Waiting {duration}s")
            time.sleep(duration)

        elif action_type == "screenshot":
            output = action.get("output")
            if output:
                screenshot = device.screenshot()
                if screenshot:
                    screenshot.save(output)
                    if verbose:
                        print_info(f"Screenshot saved to {output}")

        elif action_type == "keyevent":
            key = action.get("key", "back")
            keycodes = {
                "back": 4,
                "home": 3,
                "menu": 82,
                "enter": 66,
                "delete": 67,
            }
            keycode = keycodes.get(key, int(key) if str(key).isdigit() else 4)
            controller.keyevent(keycode)

        elif action_type == "text_input":
            text = action.get("text", "")
            device.shell(f'input text "{text}"')

        # Apply delay after action
        delay = action.get("delay", 0)
        if delay:
            time.sleep(delay)

        return True

    except Exception as e:
        print_warning(f"{action_type} failed: {e}")
        return False


@click.command()
@click.option(
    "--sequence",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="JSON sequence file path",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    sequence: str,
    device: Optional[str],
    toon: bool,
    verbose: bool,
):
    """
    Purpose:
        Execute single JSON automation sequence. Main entry point for
        one-time automation tasks.

    Parameters:
        sequence: Path to JSON sequence file. Type: str
        device: Device ID (optional). Type: Optional[str]
        toon: TOON output flag. Type: bool
        verbose: Verbose output flag. Type: bool

    Returns:
        Exit code via sys.exit(). Type: int

    Examples:
        See module-level docstring for usage examples.

    Raises:
        ADBError: Converted from GenericAdbError exceptions
        json.JSONDecodeError: When JSON is malformed
        FileNotFoundError: When sequence file doesn't exist

    Notes:
        - Step-by-step progress output
        - Errors in actions don't stop execution
        - TOON output includes error count

    Related:
        - execute_action(): Executes each step
        - validate_json_sequence(): Validates sequence

    Context:
        Main entry point called via Click CLI.

    Implementation:
        1. Load and validate JSON sequence
        2. Initialize device connection
        3. Execute each step with progress
        4. Handle errors and continue
        5. Output results (human or TOON)
    """
    errors = 0

    try:
        # Load sequence file
        sequence_path = Path(sequence).resolve()
        if verbose:
            print_info(f"Loading sequence: {sequence_path}")

        with open(sequence_path) as f:
            sequence_data = json.load(f)

        # Validate sequence
        if not validate_json_sequence(sequence_data):
            sys.exit(EXIT_INVALID_ARGUMENT)

        sequence_name = sequence_data.get("name", "Unnamed Sequence")
        steps = sequence_data.get("steps", [])

        if not toon:
            print_success(f"Loaded: {sequence_name}")
            print_info(f"Steps: {len(steps)}")
            console.print("[cyan]Executing sequence...[/cyan]")

        # Initialize device
        device_id = device or get_default_device()
        if not verify_device_connected(device_id):
            raise ADBError(f"Device {device_id} is offline", EXIT_DEVICE_OFFLINE)

        # Create controller and device wrapper
        controller = AdbController()
        device_wrapper = AdbDeviceWrapper.create_from_settings()

        # Execute each step
        for i, step in enumerate(steps, 1):
            if not execute_action(controller, device_wrapper, step, i, len(steps), verbose):
                errors += 1

        # Output results
        if toon:
            output_data = {
                "status": "success" if errors == 0 else "completed_with_errors",
                "steps_executed": len(steps),
                "total_steps": len(steps),
                "errors": errors,
            }
            print(format_toon_output(output_data))
        else:
            print_success("Sequence completed")
            if errors > 0:
                print_warning(f"Errors encountered: {errors}")

        sys.exit(EXIT_SUCCESS)

    except GenericAdbUnrecoverableError as e:
        raise ADBError(f"Fatal ADB error: {e}", EXIT_ADB_COMMAND_FAILED)
    except GenericAdbError as e:
        raise ADBError(f"ADB error: {e}", EXIT_ADB_COMMAND_FAILED)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        sys.exit(EXIT_INVALID_ARGUMENT)
    except FileNotFoundError as e:
        print_error(f"Sequence file not found: {e}")
        sys.exit(EXIT_INVALID_ARGUMENT)


if __name__ == "__main__":
    main()
