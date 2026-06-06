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
ADB Game Loop - Execute repeating JSON automation sequences.

Purpose:
    Execute predefined JSON sequences with loop control. Supports infinite
    loops, custom delays, and comprehensive error recovery. Perfect for
    game automation, daily quests, and repetitive task automation.

Parameters:
    --device/-d: Device ID (optional, auto-selects if omitted). Type: str
    --sequence/-s: JSON sequence file path (required). Type: Path
    --loops/-l: Number of loops to execute (default: 10). Type: int
    --infinite/-i: Run infinitely until Ctrl+C (flag). Type: bool
    --delay: Seconds to wait between loops (default: 0). Type: float
    --toon: Output in TOON/YAML format (flag). Type: bool
    --verbose/-v: Verbose output with debug info (flag). Type: bool

Returns:
    Exit code 0 on success, non-zero on failure.
    TOON output: {status, loops_completed, total_actions, errors, duration_seconds}

Examples:
    # Execute sequence 10 times (default)
    $ uv run adb_game_loop.py --sequence daily_quest.json

    # Run infinitely with 5-second delay
    $ uv run adb_game_loop.py -s farming.json --infinite --delay 5

    # Verbose mode with TOON output
    $ uv run adb_game_loop.py -s quest.json -v --toon

Raises:
    ADBError: When device is offline or ADB command fails
    json.JSONDecodeError: When JSON sequence is malformed
    FileNotFoundError: When sequence file doesn't exist

Notes:
    - JSON format: {"name": "...", "steps": [{"action": "tap", ...}]}
    - Supported actions: tap, swipe, wait, screenshot, keyevent, text_input
    - Error recovery: Continues on tap failures, exits on critical errors
    - Ctrl+C interruption is handled gracefully
    - Progress tracking via Rich progress bar

Related:
    - adb_click_sequence.py: Single execution variant
    - adb_wait_for_app.py: Wait for app readiness
    - adb_screenshot_compare.py: Verify screen state

Context:
    Part of automation/ category in moai-domain-adb skill. Enables
    repeatable game automation workflows with loop control.

Implementation:
    1. Load and validate JSON sequence
    2. Initialize ADB device connection
    3. Execute loop with progress tracking
    4. Handle errors and interruptions
    5. Output results (human or TOON)
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from PIL import Image
from rich.console import Console
from rich.progress import Progress

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
        Validate JSON sequence structure and content. Ensures all required
        fields exist and action types are supported.

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
        - Each step requires "action" field
        - Tap requires x, y coordinates
        - Swipe requires start, end coordinates

    Related:
        - execute_action(): Executes validated actions
        - load_sequence(): Calls this for validation

    Context:
        Validation occurs before execution to prevent runtime errors.

    Implementation:
        1. Check for "steps" field
        2. Validate steps is list
        3. Check each step has "action"
        4. Validate action-specific fields
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
    verbose: bool = False,
) -> bool:
    """
    Purpose:
        Execute a single action from JSON sequence. Supports tap, swipe,
        wait, screenshot, keyevent, and text input actions.

    Parameters:
        controller: ADB controller instance. Type: AdbController
        device: ADB device wrapper instance. Type: AdbDeviceWrapper
        action: Action dictionary from JSON. Type: Dict[str, Any]
        verbose: Enable verbose output (default: False). Type: bool

    Returns:
        True if action succeeded, False if failed. Type: bool

    Examples:
        >>> controller = AdbController()
        >>> device = AdbDeviceWrapper.create_from_settings()
        >>> action = {"action": "tap", "x": 500, "y": 1000, "delay": 1}
        >>> execute_action(controller, device, action)
        True

    Raises:
        No exceptions. Catches and logs errors internally.

    Notes:
        - Tap: Single or multi-tap with count parameter
        - Swipe: Duration in milliseconds, converted to seconds
        - Wait: Sleep for specified duration
        - Screenshot: Save to output path if provided
        - Keyevent: Supports named keys (back, home, menu, etc.)
        - Text input: Uses ADB shell input text
        - Delay: Applied after action if specified

    Related:
        - validate_json_sequence(): Validates before execution
        - main(): Calls this for each step

    Context:
        Core execution engine for game loop automation.

    Implementation:
        1. Extract action type
        2. Execute action-specific logic
        3. Apply delay if specified
        4. Handle errors gracefully
    """
    action_type = action.get("action", "tap")

    if verbose:
        print_info(f"Executing action: {action_type}")

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
        print_warning(f"{action_type} action failed: {e}")
        return False


@click.command()
@click.option(
    "--sequence",
    "-s",
    required=True,
    type=click.Path(exists=True),
    help="JSON sequence file path",
)
@click.option(
    "--loops",
    "-l",
    default=10,
    type=int,
    help="Number of loops (default: 10)",
)
@click.option(
    "--infinite",
    "-i",
    is_flag=True,
    help="Run infinitely until Ctrl+C",
)
@click.option(
    "--delay",
    default=0.0,
    type=float,
    help="Delay between loops in seconds (default: 0)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    sequence: str,
    loops: int,
    infinite: bool,
    delay: float,
    device: Optional[str],
    toon: bool,
    verbose: bool,
):
    """
    Purpose:
        Execute JSON automation sequence with loop control. Main entry point
        for game loop automation.

    Parameters:
        sequence: Path to JSON sequence file. Type: str
        loops: Number of loops to execute. Type: int
        infinite: Run infinitely flag. Type: bool
        delay: Seconds between loops. Type: float
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
        KeyboardInterrupt: Handled gracefully

    Notes:
        - Progress bar shows loop completion
        - Errors in actions don't stop execution
        - Ctrl+C interruption is graceful
        - TOON output includes comprehensive stats

    Related:
        - execute_action(): Executes each step
        - validate_json_sequence(): Validates sequence

    Context:
        Main entry point called via Click CLI.

    Implementation:
        1. Load and validate JSON sequence
        2. Initialize device connection
        3. Execute loops with progress tracking
        4. Handle interruptions and errors
        5. Output results (human or TOON)
    """
    start_time = time.time()
    errors_encountered = 0
    total_actions = 0

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

        # Initialize device
        device_id = device or get_default_device()
        if not verify_device_connected(device_id):
            raise ADBError(f"Device {device_id} is offline", EXIT_DEVICE_OFFLINE)

        # Create controller and device wrapper
        controller = AdbController()
        device_wrapper = AdbDeviceWrapper.create_from_settings()

        # Determine total loops
        total_loops = float("inf") if infinite else loops
        loop_count = 0

        try:
            with Progress() as progress:
                task = progress.add_task(
                    "[cyan]Executing loops...",
                    total=None if infinite else loops,
                )

                while loop_count < total_loops:
                    loop_count += 1

                    for step in steps:
                        total_actions += 1
                        if not execute_action(controller, device_wrapper, step, verbose):
                            errors_encountered += 1

                    if not infinite:
                        progress.update(task, completed=loop_count)

                    # Apply inter-loop delay
                    if loop_count < total_loops and delay > 0:
                        time.sleep(delay)

            duration = time.time() - start_time

            # Output results
            if toon:
                output_data = {
                    "status": "success",
                    "loops_completed": loop_count,
                    "total_actions": total_actions,
                    "errors_encountered": errors_encountered,
                    "duration_seconds": round(duration, 2),
                }
                print(format_toon_output(output_data))
            else:
                print_success(f"Completed {loop_count} loop(s)")
                print_info(f"Total actions: {total_actions}")
                if errors_encountered > 0:
                    print_warning(f"Errors encountered: {errors_encountered}")
                print_info(f"Duration: {duration:.2f}s")

            sys.exit(EXIT_SUCCESS)

        except KeyboardInterrupt:
            duration = time.time() - start_time

            if toon:
                output_data = {
                    "status": "interrupted",
                    "loops_completed": loop_count,
                    "total_actions": total_actions,
                    "errors_encountered": errors_encountered,
                    "duration_seconds": round(duration, 2),
                }
                print(format_toon_output(output_data))
            else:
                print_warning(f"Interrupted after {loop_count} loop(s)")
                print_info(f"Total actions: {total_actions}")

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
