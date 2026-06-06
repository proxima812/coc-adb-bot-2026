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
ADB App Uninstall - Uninstall application from Android device

Purpose:
    Uninstall application by package name from Android device with support
    for keeping app data, TOON format output, and comprehensive validation.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/app/adb_app_uninstall.py [OPTIONS]

Examples:
    # Uninstall app (keep data)
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_uninstall.py --package com.example.app

    # Uninstall and remove all data
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_uninstall.py --package com.example.app --keep-data

    # Uninstall from specific device with TOON output
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_uninstall.py --device emulator-5554 --package com.example.app --toon

    # Verbose output for debugging
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_uninstall.py --package com.example.app --verbose

Exit Codes:
    0 - App uninstalled successfully
    2 - Device offline or not found
    3 - ADB command failed (package not found, permission denied, etc.)
    4 - Invalid input (invalid package name format)

Requirements:
    - Python 3.12+
    - click>=8.1.0
    - rich>=13.0.0
    - pyyaml>=6.0.0
    - ADB server running
    - Device connected and authorized

TOON Output Format:
    status: "success" | "error"
    package_name: str (package that was uninstalled)
    freed_space_mb: float (estimated space freed, 0 if keep-data)
    uninstall_time_seconds: float (time taken)
    device: str (device serial)
    data_kept: bool (whether app data was preserved)
    timestamp: str (ISO 8601 format)
    message: str (optional, error messages)

Architecture:
    - Uses common/path_utils for adbautoplayer path setup
    - Uses common/adb_utils for device management
    - Uses common/cli_utils for CLI options and output formatting
    - Uses common/error_handlers for error handling and exit codes
    - Validates package name format before uninstallation
    - Measures uninstallation time
    - Attempts to calculate freed space before uninstall
"""

import re
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from common.path_utils import setup_adbautoplayer_path
from common.adb_utils import get_default_device, verify_device_connected
from common.cli_utils import (
    device_option,
    toon_output_option,
    verbose_option,
    print_success,
    print_error,
    print_info,
    print_warning,
    format_toon_output,
)
from common.error_handlers import (
    handle_adb_errors,
    ADBError,
    EXIT_SUCCESS,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
    EXIT_INVALID_ARGUMENT,
)

# Setup adbautoplayer path
setup_adbautoplayer_path()

from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError

console = Console()

# Package name pattern: com.example.app, com.example.app.name, etc.
PACKAGE_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$")


def validate_package_name(package: str) -> None:
    """
    Validate package name format.

    Args:
        package: Package name to validate

    Raises:
        ADBError: If package name format is invalid
    """
    if not package:
        raise ADBError(
            "Package name cannot be empty",
            exit_code=EXIT_INVALID_ARGUMENT,
        )

    if not PACKAGE_NAME_PATTERN.match(package):
        raise ADBError(
            f"Invalid package name format: {package}\n"
            "Expected format: com.example.app (at least 2 segments separated by dots)",
            exit_code=EXIT_INVALID_ARGUMENT,
        )


def check_package_exists(device: AdbDeviceWrapper, package: str) -> bool:
    """
    Check if package is installed on device.

    Args:
        device: ADB device wrapper
        package: Package name to check

    Returns:
        True if package is installed, False otherwise
    """
    try:
        result = device.shell(f"pm list packages | grep {package}")
        return package in result
    except Exception:
        return False


def get_package_size(device: AdbDeviceWrapper, package: str) -> float:
    """
    Get approximate package size in MB.

    Args:
        device: ADB device wrapper
        package: Package name

    Returns:
        Package size in MB, or 0 if unable to determine
    """
    try:
        # Get package path
        result = device.shell(f"pm path {package}")
        if not result or "package:" not in result:
            return 0.0

        # Extract APK path
        apk_path = result.split("package:")[1].strip()

        # Get file size
        size_result = device.shell(f"ls -l {apk_path}")
        if size_result:
            # Parse: -rw-r--r-- 1 root root 12345678 2024-01-01 12:00 file.apk
            parts = size_result.split()
            if len(parts) >= 5:
                try:
                    size_bytes = int(parts[4])
                    return size_bytes / (1024 * 1024)
                except (ValueError, IndexError):
                    pass

        return 0.0
    except Exception:
        return 0.0


def uninstall_app(
    device: AdbDeviceWrapper,
    package: str,
    keep_data: bool = False,
    verbose: bool = False,
) -> tuple[bool, str, float]:
    """
    Uninstall application from device.

    Args:
        device: ADB device wrapper
        package: Package name to uninstall
        keep_data: Whether to keep app data after uninstall
        verbose: Enable verbose output

    Returns:
        Tuple of (success: bool, output: str, elapsed_time: float)
    """
    start_time = time.time()

    try:
        # Build uninstall command
        if keep_data:
            cmd = f"pm uninstall -k {package}"
        else:
            cmd = f"pm uninstall {package}"

        if verbose:
            print_info(f"Executing: {cmd}")

        # Execute uninstall command
        result = device.shell(cmd)

        elapsed = time.time() - start_time

        # Check for success
        success = "Success" in result or "removed" in result.lower()

        return success, result, elapsed

    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        elapsed = time.time() - start_time
        return False, str(e), elapsed


@click.command()
@click.option(
    "--package",
    "-p",
    required=True,
    type=str,
    help="Package name to uninstall (e.g., com.example.app)",
)
@click.option(
    "--keep-data",
    "-k",
    is_flag=True,
    help="Keep app data and cache after uninstall",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    package: str,
    keep_data: bool,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> None:
    """
    Uninstall application from Android device.

    Uninstalls the specified application by package name from the target
    Android device. Supports keeping app data and provides detailed output
    including uninstallation time and freed space.

    Examples:
        Uninstall app (remove all data):
        $ adb_app_uninstall.py --package com.example.app

        Uninstall but keep data:
        $ adb_app_uninstall.py --package com.example.app --keep-data

        Uninstall from specific device:
        $ adb_app_uninstall.py --device emulator-5554 --package com.example.app
    """
    if verbose:
        print_info(f"Package: {package}")
        print_info(f"Keep data: {keep_data}")

    # Validate package name format
    validate_package_name(package)

    # Get device
    device_serial = device or get_default_device()
    if verbose:
        print_info(f"Target device: {device_serial}")

    # Verify device is connected
    verify_device_connected(device_serial)

    # Create device wrapper
    try:
        adb_device = AdbDeviceWrapper.create_from_settings()
    except Exception as e:
        raise ADBError(
            f"Failed to create device wrapper: {e}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Check if package exists
    if not check_package_exists(adb_device, package):
        raise ADBError(
            f"Package not found on device: {package}",
            exit_code=EXIT_ADB_COMMAND_FAILED,
        )

    # Get package size before uninstall (for freed space calculation)
    package_size = get_package_size(adb_device, package) if not keep_data else 0.0
    if verbose and package_size > 0:
        print_info(f"Package size: {package_size:.2f} MB")

    # Uninstall app with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Uninstalling {package}...",
            total=None,
        )

        success, output, elapsed = uninstall_app(
            adb_device,
            package,
            keep_data=keep_data,
            verbose=verbose,
        )

        progress.remove_task(task)

    # Prepare output
    if toon:
        toon_data = {
            "status": "success" if success else "error",
            "package_name": package,
            "device": device_serial,
            "freed_space_mb": round(package_size, 2),
            "uninstall_time_seconds": round(elapsed, 2),
            "data_kept": keep_data,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if not success:
            toon_data["message"] = output.strip()

        console.print(format_toon_output(toon_data))
    else:
        if success:
            print_success(f"App uninstalled successfully in {elapsed:.2f}s")
            print_info(f"Package: {package}")
            if package_size > 0:
                print_info(f"Freed space: {package_size:.2f} MB")
            if keep_data:
                print_info("App data preserved")
        else:
            print_error("App uninstall failed")
            if verbose:
                console.print(f"[yellow]{output.strip()}[/yellow]")

            # Provide helpful error messages
            if "DELETE_FAILED_INTERNAL_ERROR" in output:
                print_warning("Internal error during uninstall")
            elif "UNKNOWN_PACKAGE" in output:
                print_warning(f"Package not found: {package}")
            elif "DELETE_FAILED_DEVICE_POLICY_MANAGER" in output:
                print_warning("Cannot uninstall: app is a device administrator")

    # Exit with appropriate code
    sys.exit(EXIT_SUCCESS if success else EXIT_ADB_COMMAND_FAILED)


if __name__ == "__main__":
    main()
