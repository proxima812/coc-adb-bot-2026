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
ADB App Start - Launch application on Android device.

Purpose:
    Start an Android application by package name using ADB commands. Supports
    optional activity specification and wait-for-launch functionality with
    process monitoring. Provides both human-readable and TOON/YAML output
    formats for integration scenarios.

Parameters:
    --package/-p (str, required): App package name to launch
                                   (e.g., "com.afk.journey")
    --activity/-a (str, optional): Specific activity to start. If not provided,
                                    uses monkey command for auto-detection
    --wait/-w (flag, optional): Wait for app to launch and verify process
                                 started (30-second timeout)
    --device/-d (str, optional): Device ID (e.g., "127.0.0.1:5555"). If not
                                  provided, auto-selects first connected device
    --toon (flag, optional): Output in TOON/YAML format for parsing
    --verbose/-v (flag, optional): Print detailed execution information

Returns:
    Exit code 0 on success with launch confirmation message or TOON output.
    Exit codes:
        0 - App launched successfully
        2 - Device offline or not found
        3 - ADB command failed (package not installed, permission denied)
        4 - Invalid package name or activity format

Examples:
    # Basic app start
    $ uv run adb_app_start.py --package com.afk.journey

    # Start with specific activity
    $ uv run adb_app_start.py -p com.example.app -a .MainActivity

    # Start and wait for launch verification
    $ uv run adb_app_start.py -p com.afk.journey --wait

    # TOON output for automation
    $ uv run adb_app_start.py -p com.afk.journey --toon
    status: success
    package: com.afk.journey
    launched_at: "2025-12-01T10:30:45"
    wait_timeout: false

    # Verbose output with debug info
    $ uv run adb_app_start.py -p com.afk.journey --wait -v

Raises:
    ADBError: Base exception for all ADB-related failures
        - ADBDeviceOffline: Device not responding to commands
        - ADBCommandFailed: Launch command failed (package not found, etc.)
        - InvalidArgument: Package name format invalid

Notes:
    - Package names must follow format: com.example.app
    - Activity names can be relative (.MainActivity) or absolute
    - If --activity not provided, uses monkey command for auto-launch
    - --wait flag monitors process with 30-second timeout
    - Process verification checks for PID presence using pidof command
    - TOON output includes timestamp and timeout status

Related:
    - adb_app_stop.py: Force stop application
    - adb_app_list.py: List installed applications
    - common/adb_utils.py: Device discovery and verification functions
    - common/error_handlers.py: Error handling decorators

Context:
    Use this script to launch apps for testing, automation, or initial setup.
    Commonly used in test suites and deployment workflows to ensure apps
    start correctly. --wait flag useful for CI/CD pipelines to verify
    successful launch before proceeding with tests.

Implementation:
    1. Validate package name format (com.example.app pattern)
    2. Resolve device ID (explicit or auto-select)
    3. Verify device is online and responsive
    4. Execute launch command:
       - With activity: am start -n {package}/{activity}
       - Without activity: monkey -p {package} 1 (auto-detect)
    5. If --wait flag:
       - Loop for 30 seconds checking pidof {package}
       - Break on first successful PID detection
       - Timeout if 30 seconds elapse without PID
    6. Format output (text or TOON based on flag)
    7. Return appropriate exit code
"""

import re
import subprocess
import time
from datetime import datetime
from typing import Optional

import click

from common.adb_utils import get_default_device, verify_device_connected
from common.cli_utils import (
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
from common.error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_DEVICE_OFFLINE,
    EXIT_INVALID_ARGUMENT,
    EXIT_SUCCESS,
    ADBCommandFailed,
    ADBDeviceOffline,
    InvalidArgument,
    handle_adb_errors,
)
from common.path_utils import setup_adbautoplayer_path

# Setup path to adbautoplayer package
setup_adbautoplayer_path()


PACKAGE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")
WAIT_TIMEOUT_SECONDS = 30
WAIT_CHECK_INTERVAL_SECONDS = 1


def validate_package_name(package: str) -> None:
    """
    Validate package name format.

    Args:
        package: Package name to validate

    Raises:
        InvalidArgument: If package name format is invalid
    """
    if not PACKAGE_NAME_PATTERN.match(package):
        raise InvalidArgument(
            f"Invalid package name format: {package}. "
            "Expected format: com.example.app"
        )


def execute_start_command(
    device: str, package: str, activity: Optional[str], verbose: bool
) -> str:
    """
    Execute ADB command to start application.

    Args:
        device: Device ID to target
        package: Package name to start
        activity: Optional activity name
        verbose: Whether to print verbose output

    Returns:
        Command output string

    Raises:
        ADBCommandFailed: If start command fails
    """
    if activity:
        # Start with specific activity
        cmd = ["adb", "-s", device, "shell", "am", "start", "-n", f"{package}/{activity}"]
        if verbose:
            print_info(f"Launching with activity: {activity}")
    else:
        # Use monkey for auto-detect main activity
        cmd = ["adb", "-s", device, "shell", "monkey", "-p", package, "1"]
        if verbose:
            print_info("Using monkey command for auto-launch")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        if "Error: Activity class" in error_msg or "does not exist" in error_msg:
            raise ADBCommandFailed(
                " ".join(cmd),
                f"Activity not found. {error_msg}",
            )
        elif "Error: Could not access" in error_msg:
            raise ADBCommandFailed(
                " ".join(cmd),
                f"Permission denied or package not found. {error_msg}",
            )
        else:
            raise ADBCommandFailed(" ".join(cmd), error_msg)
    except subprocess.TimeoutExpired:
        raise ADBCommandFailed(
            " ".join(cmd),
            "Command timed out after 10 seconds",
        )


def wait_for_app_launch(device: str, package: str, verbose: bool) -> bool:
    """
    Wait for application to launch by checking process ID.

    Args:
        device: Device ID to check
        package: Package name to monitor
        verbose: Whether to print verbose output

    Returns:
        True if app launched within timeout, False if timeout
    """
    if verbose:
        print_info(f"Waiting for {package} to launch (timeout: {WAIT_TIMEOUT_SECONDS}s)...")

    start_time = time.time()
    elapsed = 0

    while elapsed < WAIT_TIMEOUT_SECONDS:
        try:
            # Check if process is running
            result = subprocess.run(
                ["adb", "-s", device, "shell", "pidof", package],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )

            pid = result.stdout.strip()
            if pid:
                if verbose:
                    print_info(f"Process detected with PID: {pid}")
                return True

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        time.sleep(WAIT_CHECK_INTERVAL_SECONDS)
        elapsed = time.time() - start_time

        if verbose and int(elapsed) % 5 == 0 and elapsed > 0:
            print_info(f"Still waiting... ({int(elapsed)}s elapsed)")

    return False


@click.command()
@click.option(
    "-p",
    "--package",
    required=True,
    help="App package name (e.g., com.afk.journey)",
    type=str,
)
@click.option(
    "-a",
    "--activity",
    default=None,
    help="Specific activity to start (e.g., .MainActivity)",
    type=str,
)
@click.option(
    "-w",
    "--wait",
    is_flag=True,
    default=False,
    help="Wait for app to launch (30-second timeout)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    package: str,
    activity: Optional[str],
    wait: bool,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """Launch application on Android device via ADB."""

    # Validate package name format
    try:
        validate_package_name(package)
    except InvalidArgument as e:
        print_error(str(e))
        return EXIT_INVALID_ARGUMENT

    # Resolve device
    try:
        device_id = get_default_device(device)
        if verbose:
            print_info(f"Using device: {device_id}")
    except Exception as e:
        print_error(f"Device discovery failed: {e}")
        return EXIT_DEVICE_OFFLINE

    # Verify device connectivity
    if not verify_device_connected(device_id):
        print_error(f"Device offline: {device_id}")
        return EXIT_DEVICE_OFFLINE

    # Launch app
    try:
        if verbose:
            print_info(f"Starting app: {package}")

        output = execute_start_command(device_id, package, activity, verbose)

        if verbose:
            print_info(f"Launch command output:\n{output.strip()}")

    except ADBCommandFailed as e:
        print_error(str(e))
        return EXIT_ADB_COMMAND_FAILED

    # Wait for launch if requested
    wait_timeout = False
    if wait:
        launched = wait_for_app_launch(device_id, package, verbose)
        if not launched:
            print_warning(f"App launch verification timed out after {WAIT_TIMEOUT_SECONDS}s")
            print_warning("App may still be loading")
            wait_timeout = True
        else:
            if verbose:
                print_success("App process detected")

    # Format output
    if toon:
        toon_data = {
            "status": "success",
            "package": package,
            "launched_at": datetime.now().isoformat(),
            "wait_timeout": wait_timeout,
        }
        if activity:
            toon_data["activity"] = activity
        print(format_toon_output(toon_data))
    else:
        print_success(f"Started: {package}")
        if activity:
            console.print(f"  Activity: [cyan]{activity}[/cyan]")
        if wait and not wait_timeout:
            console.print(f"  Process: [green]Running[/green]")

    return EXIT_SUCCESS


if __name__ == "__main__":
    exit(main())
