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
ADB App Stop - Force stop application on Android device.

Purpose:
    Force stop an Android application by package name using ADB commands.
    Terminates all app processes immediately without waiting for graceful
    shutdown. Provides both human-readable and TOON/YAML output formats
    for integration scenarios.

Parameters:
    --package/-p (str, required): App package name to stop
                                   (e.g., "com.afk.journey")
    --device/-d (str, optional): Device ID (e.g., "127.0.0.1:5555"). If not
                                  provided, auto-selects first connected device
    --toon (flag, optional): Output in TOON/YAML format for parsing
    --verbose/-v (flag, optional): Print detailed execution information

Returns:
    Exit code 0 on success with stop confirmation message or TOON output.
    Exit codes:
        0 - App stopped successfully
        2 - Device offline or not found
        3 - ADB command failed (package not found, permission denied)
        4 - Invalid package name format

Examples:
    # Basic app stop
    $ uv run adb_app_stop.py --package com.afk.journey

    # Stop with specific device
    $ uv run adb_app_stop.py -p com.example.app -d 127.0.0.1:5555

    # TOON output for automation
    $ uv run adb_app_stop.py -p com.afk.journey --toon
    status: success
    package: com.afk.journey
    stopped_at: "2025-12-01T10:30:45"

    # Verbose output with debug info
    $ uv run adb_app_stop.py -p com.afk.journey -v

Raises:
    ADBError: Base exception for all ADB-related failures
        - ADBDeviceOffline: Device not responding to commands
        - ADBCommandFailed: Stop command failed (package not found, etc.)
        - InvalidArgument: Package name format invalid

Notes:
    - Package names must follow format: com.example.app
    - Uses 'am force-stop' command for immediate termination
    - Does NOT clear app data or cache (use pm clear for that)
    - Stops all processes associated with package
    - Silent operation if package not running (not an error)
    - TOON output includes timestamp for logging

Related:
    - adb_app_start.py: Launch application
    - adb_app_list.py: List installed applications
    - common/adb_utils.py: Device discovery and verification functions
    - common/error_handlers.py: Error handling decorators

Context:
    Use this script to terminate apps for testing, cleanup, or reset
    scenarios. Commonly used in test teardown, debugging sessions, or
    when app becomes unresponsive. Unlike killing via PID, force-stop
    ensures all app components (services, receivers) are terminated.

Implementation:
    1. Validate package name format (com.example.app pattern)
    2. Resolve device ID (explicit or auto-select)
    3. Verify device is online and responsive
    4. Execute: adb shell am force-stop {package}
    5. Command succeeds silently even if app not running
    6. Format output (text or TOON based on flag)
    7. Return appropriate exit code
"""

import re
import subprocess
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
    toon_output_option,
    verbose_option,
)
from common.error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_DEVICE_OFFLINE,
    EXIT_INVALID_ARGUMENT,
    EXIT_SUCCESS,
    ADBCommandFailed,
    InvalidArgument,
    handle_adb_errors,
)
from common.path_utils import setup_adbautoplayer_path

# Setup path to adbautoplayer package
setup_adbautoplayer_path()


PACKAGE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")


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


def execute_stop_command(device: str, package: str, verbose: bool) -> str:
    """
    Execute ADB command to force stop application.

    Args:
        device: Device ID to target
        package: Package name to stop
        verbose: Whether to print verbose output

    Returns:
        Command output string (usually empty for force-stop)

    Raises:
        ADBCommandFailed: If stop command fails
    """
    cmd = ["adb", "-s", device, "shell", "am", "force-stop", package]

    if verbose:
        print_info(f"Executing: {' '.join(cmd)}")

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
        raise ADBCommandFailed(" ".join(cmd), error_msg)
    except subprocess.TimeoutExpired:
        raise ADBCommandFailed(
            " ".join(cmd),
            "Command timed out after 10 seconds",
        )


@click.command()
@click.option(
    "-p",
    "--package",
    required=True,
    help="App package name (e.g., com.afk.journey)",
    type=str,
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    package: str,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """Force stop application on Android device via ADB."""

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

    # Stop app
    try:
        if verbose:
            print_info(f"Stopping app: {package}")

        output = execute_stop_command(device_id, package, verbose)

        if verbose and output.strip():
            print_info(f"Command output:\n{output.strip()}")

    except ADBCommandFailed as e:
        print_error(str(e))
        return EXIT_ADB_COMMAND_FAILED

    # Format output
    if toon:
        toon_data = {
            "status": "success",
            "package": package,
            "stopped_at": datetime.now().isoformat(),
        }
        print(format_toon_output(toon_data))
    else:
        print_success(f"Stopped: {package}")

    return EXIT_SUCCESS


if __name__ == "__main__":
    exit(main())
