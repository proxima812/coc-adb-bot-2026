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
ADB Wait For App - Wait for app to launch and become active.

Purpose:
    Wait until specified app appears in foreground window. Useful for
    synchronization in automation sequences, ensuring app is ready before
    continuing execution.

Parameters:
    --device/-d: Device ID (optional, auto-selects if omitted). Type: str
    --package/-p: Package name to wait for (required). Type: str
    --timeout/-t: Timeout in seconds (default: 30). Type: int
    --activity/-a: Specific activity to wait for (optional). Type: str
    --toon: Output in TOON/YAML format (flag). Type: bool
    --verbose/-v: Verbose output with debug info (flag). Type: bool

Returns:
    Exit code 0 if app detected, non-zero otherwise.
    TOON output: {status, package, detected_at_seconds, activity_name}

Examples:
    # Wait up to 30 seconds for app
    $ uv run adb_wait_for_app.py --package com.afk.journey

    # Wait 60 seconds with verbose output
    $ uv run adb_wait_for_app.py -p com.game.app -t 60 -v

    # Wait for specific activity
    $ uv run adb_wait_for_app.py -p com.game.app -a .MainActivity

    # TOON output for script integration
    $ uv run adb_wait_for_app.py -p com.game.app --toon

Raises:
    ADBError: When device is offline or ADB command fails
    TimeoutError: When app not detected within timeout

Notes:
    - Checks window manager every 1 second
    - Progress bar shows elapsed time
    - Activity check is optional (more specific)
    - Supports both package and activity detection
    - Ctrl+C interruption handled gracefully

Related:
    - adb_game_loop.py: Execute automation after app ready
    - adb_get_current_activity.py: Get current activity name
    - adb_start_app.py: Launch app before waiting

Context:
    Part of automation/ category in moai-domain-adb skill. Provides
    synchronization primitive for automation workflows.

Implementation:
    1. Initialize device connection
    2. Poll window manager for package/activity
    3. Update progress bar
    4. Return success if detected before timeout
    5. Output results (human or TOON)
"""

import sys
import time
from typing import Optional

import click
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
    toon_output_option,
    verbose_option,
)
from common.error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_DEVICE_OFFLINE,
    EXIT_SUCCESS,
    ADBError,
    handle_adb_errors,
)
from common.path_utils import setup_adbautoplayer_path

# Setup path to adbautoplayer
setup_adbautoplayer_path()

from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError

console = Console()


def check_app_running(
    device: AdbDeviceWrapper, package: str, activity: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Purpose:
        Check if app is currently running in foreground. Optionally checks
        for specific activity if provided.

    Parameters:
        device: ADB device wrapper instance. Type: AdbDeviceWrapper
        package: Package name to check. Type: str
        activity: Optional activity name to check. Type: Optional[str]

    Returns:
        Tuple of (is_running, detected_activity). Type: tuple[bool, Optional[str]]

    Examples:
        >>> device = AdbDeviceWrapper.create_from_settings()
        >>> check_app_running(device, "com.afk.journey")
        (True, "com.afk.journey/.MainActivity")

    Raises:
        No exceptions. Returns False on errors.

    Notes:
        - Method 1: Check window manager mCurrentFocus
        - Method 2: Check pidof for package (fallback)
        - Activity check is substring match (supports partial activity names)
        - Returns detected activity name if found

    Related:
        - main(): Calls this in polling loop
        - verify_device_connected(): Verifies device before check

    Context:
        Core detection logic for app waiting.

    Implementation:
        1. Query dumpsys window windows for mCurrentFocus
        2. Check if package name in output
        3. If activity specified, check for activity match
        4. Return result tuple
    """
    try:
        # Check window manager for current focus
        output = device.shell("dumpsys window windows | grep 'mCurrentFocus'")

        # Check if package in output
        if package in output:
            # Extract activity if possible
            detected_activity = None
            if "/" in output:
                parts = output.split()
                for part in parts:
                    if package in part and "/" in part:
                        detected_activity = part.strip("}")
                        break

            # If activity specified, check for match
            if activity:
                if activity in output:
                    return True, detected_activity
                else:
                    return False, None

            return True, detected_activity

        return False, None

    except Exception:
        # Fallback: check pidof
        try:
            output = device.shell(f"pidof {package}")
            if output.strip():
                return True, None
        except Exception:
            pass

        return False, None


@click.command()
@click.option(
    "--package",
    "-p",
    required=True,
    type=str,
    help="Package name to wait for (e.g., com.afk.journey)",
)
@click.option(
    "--timeout",
    "-t",
    default=30,
    type=int,
    help="Timeout in seconds (default: 30)",
)
@click.option(
    "--activity",
    "-a",
    default=None,
    type=str,
    help="Specific activity to wait for (optional)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    package: str,
    timeout: int,
    activity: Optional[str],
    device: Optional[str],
    toon: bool,
    verbose: bool,
):
    """
    Purpose:
        Wait for app to launch and become active. Main entry point for
        app synchronization in automation workflows.

    Parameters:
        package: Package name to wait for. Type: str
        timeout: Timeout in seconds. Type: int
        activity: Optional activity name. Type: Optional[str]
        device: Device ID (optional). Type: Optional[str]
        toon: TOON output flag. Type: bool
        verbose: Verbose output flag. Type: bool

    Returns:
        Exit code via sys.exit(). Type: int

    Examples:
        See module-level docstring for usage examples.

    Raises:
        ADBError: Converted from GenericAdbError exceptions
        KeyboardInterrupt: Handled gracefully

    Notes:
        - Polls every 1 second
        - Progress bar shows elapsed time
        - Activity check is optional but more specific
        - TOON output includes detection timing

    Related:
        - check_app_running(): Core detection logic
        - adb_game_loop.py: Uses this for synchronization

    Context:
        Main entry point called via Click CLI.

    Implementation:
        1. Initialize device connection
        2. Start polling loop with progress tracking
        3. Check app every 1 second
        4. Return on detection or timeout
        5. Output results (human or TOON)
    """
    start_time = time.time()
    detected_activity = None

    try:
        # Display wait message
        if not toon:
            if activity:
                print_info(
                    f"Waiting for {package}/{activity} (timeout: {timeout}s)"
                )
            else:
                print_info(f"Waiting for {package} (timeout: {timeout}s)")

        # Initialize device
        device_id = device or get_default_device()
        if not verify_device_connected(device_id):
            raise ADBError(f"Device {device_id} is offline", EXIT_DEVICE_OFFLINE)

        device_wrapper = AdbDeviceWrapper.create_from_settings()

        found = False
        elapsed = 0

        with Progress() as progress:
            task = progress.add_task("[cyan]Waiting...", total=timeout)

            while elapsed < timeout:
                # Check if app is running
                found, detected_activity = check_app_running(
                    device_wrapper, package, activity
                )

                if found:
                    break

                time.sleep(1)
                elapsed = int(time.time() - start_time)
                progress.update(task, completed=elapsed)

                if verbose and elapsed % 5 == 0:
                    print_info(f"Still waiting... ({elapsed}s elapsed)")

        if found:
            detection_time = time.time() - start_time

            if toon:
                output_data = {
                    "status": "detected",
                    "package": package,
                    "detected_at_seconds": round(detection_time, 2),
                    "activity_name": detected_activity,
                }
                print(format_toon_output(output_data))
            else:
                print_success(f"App {package} is now active")
                if detected_activity:
                    print_info(f"Activity: {detected_activity}")
                print_info(f"Detected after {detection_time:.1f}s")

            sys.exit(EXIT_SUCCESS)

        else:
            if toon:
                output_data = {
                    "status": "timeout",
                    "package": package,
                    "timeout_seconds": timeout,
                    "activity_name": None,
                }
                print(format_toon_output(output_data))
            else:
                print_error(f"App {package} not detected within {timeout}s")

            sys.exit(EXIT_ADB_COMMAND_FAILED)

    except GenericAdbUnrecoverableError as e:
        raise ADBError(f"Fatal ADB error: {e}", EXIT_ADB_COMMAND_FAILED)
    except GenericAdbError as e:
        raise ADBError(f"ADB error: {e}", EXIT_ADB_COMMAND_FAILED)
    except KeyboardInterrupt:
        if toon:
            output_data = {
                "status": "interrupted",
                "package": package,
                "elapsed_seconds": int(time.time() - start_time),
                "activity_name": None,
            }
            print(format_toon_output(output_data))
        else:
            print_warning("Interrupted by user")

        sys.exit(EXIT_ADB_COMMAND_FAILED)


if __name__ == "__main__":
    main()
