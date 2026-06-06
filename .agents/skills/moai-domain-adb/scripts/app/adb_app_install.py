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
ADB App Install - Install APK file on Android device

Purpose:
    Install APK file to Android device with support for reinstallation,
    TOON format output, and comprehensive validation.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/app/adb_app_install.py [OPTIONS]

Examples:
    # Install APK to default device
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_install.py --apk myapp.apk

    # Force reinstall existing app
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_install.py --apk myapp.apk --reinstall

    # Install to specific device with TOON output
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_install.py --device emulator-5554 --apk myapp.apk --toon

    # Verbose output for debugging
    $ uv run .claude/skills/moai-domain-adb/scripts/app/adb_app_install.py --apk myapp.apk --verbose

Exit Codes:
    0 - APK installed successfully
    2 - Device offline or not found
    3 - ADB command failed (invalid APK, insufficient space, etc.)
    4 - Invalid input (file not found, not readable, etc.)

Requirements:
    - Python 3.12+
    - click>=8.1.0
    - rich>=13.0.0
    - pyyaml>=6.0.0
    - ADB server running
    - Device connected and authorized

TOON Output Format:
    status: "success" | "error"
    package_name: str (extracted from APK)
    install_size_mb: float (APK file size)
    install_time_seconds: float (time taken)
    device: str (device serial)
    timestamp: str (ISO 8601 format)
    message: str (optional, error messages)

Architecture:
    - Uses common/path_utils for adbautoplayer path setup
    - Uses common/adb_utils for device management
    - Uses common/cli_utils for CLI options and output formatting
    - Uses common/error_handlers for error handling and exit codes
    - Validates APK file before installation
    - Measures installation time and file size
    - Extracts package name from APK for verification
"""

import sys
import time
from pathlib import Path
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


def validate_apk_file(apk_path: Path) -> None:
    """
    Validate APK file exists and is readable.

    Args:
        apk_path: Path to APK file

    Raises:
        ADBError: If file validation fails
    """
    if not apk_path.exists():
        raise ADBError(
            f"APK file not found: {apk_path}",
            exit_code=EXIT_INVALID_ARGUMENT,
        )

    if not apk_path.is_file():
        raise ADBError(
            f"Path is not a file: {apk_path}",
            exit_code=EXIT_INVALID_ARGUMENT,
        )

    if apk_path.stat().st_size == 0:
        raise ADBError(
            f"APK file is empty: {apk_path}",
            exit_code=EXIT_INVALID_ARGUMENT,
        )

    # Check file extension
    if apk_path.suffix.lower() != ".apk":
        print_warning(f"File does not have .apk extension: {apk_path}")


def get_package_name(device: AdbDeviceWrapper, apk_path: Path) -> Optional[str]:
    """
    Extract package name from APK file.

    Args:
        device: ADB device wrapper
        apk_path: Path to APK file

    Returns:
        Package name if extraction successful, None otherwise
    """
    try:
        # Use aapt or aapt2 to extract package name
        # First try with aapt2, fallback to aapt
        for cmd in ["aapt2", "aapt"]:
            try:
                result = device.shell(f'{cmd} dump badging "{apk_path}" | grep package')
                if result and "package:" in result:
                    # Parse: package: name='com.example.app' versionCode='1' ...
                    parts = result.split("'")
                    if len(parts) >= 2:
                        return parts[1]
            except Exception:
                continue

        # Fallback: try to parse from filename if format is com.example.app.apk
        name = apk_path.stem
        if "." in name and name.count(".") >= 2:
            return name

        return None
    except Exception as e:
        print_warning(f"Could not extract package name: {e}")
        return None


def install_apk(
    device: AdbDeviceWrapper,
    apk_path: Path,
    reinstall: bool = False,
    verbose: bool = False,
) -> tuple[bool, str, float]:
    """
    Install APK file on device.

    Args:
        device: ADB device wrapper
        apk_path: Path to APK file
        reinstall: Whether to reinstall if already installed
        verbose: Enable verbose output

    Returns:
        Tuple of (success: bool, output: str, elapsed_time: float)
    """
    start_time = time.time()

    try:
        # Build install command
        cmd_parts = ["install"]
        if reinstall:
            cmd_parts.append("-r")  # Replace existing app
        cmd_parts.append(str(apk_path))

        cmd = " ".join(cmd_parts)

        if verbose:
            print_info(f"Executing: adb {cmd}")

        # Execute install command
        result = device.shell(f"adb {cmd}")

        elapsed = time.time() - start_time

        # Check for success
        success = "Success" in result or "installed" in result.lower()

        return success, result, elapsed

    except (GenericAdbError, GenericAdbUnrecoverableError) as e:
        elapsed = time.time() - start_time
        return False, str(e), elapsed


@click.command()
@click.option(
    "--apk",
    "-a",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to APK file to install",
)
@click.option(
    "--reinstall",
    "-r",
    is_flag=True,
    help="Reinstall app if already installed (replace existing)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    apk: Path,
    reinstall: bool,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> None:
    """
    Install APK file on Android device.

    Installs the specified APK file to the target Android device. Supports
    reinstallation of existing apps and provides detailed output including
    installation time and package information.

    Examples:
        Install APK to default device:
        $ adb_app_install.py --apk myapp.apk

        Force reinstall:
        $ adb_app_install.py --apk myapp.apk --reinstall

        Install to specific device:
        $ adb_app_install.py --device emulator-5554 --apk myapp.apk
    """
    # Resolve APK path
    apk_path = apk.resolve()

    if verbose:
        print_info(f"APK file: {apk_path}")
        print_info(f"File size: {apk_path.stat().st_size / (1024 * 1024):.2f} MB")

    # Validate APK file
    validate_apk_file(apk_path)

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

    # Extract package name (best effort)
    package_name = get_package_name(adb_device, apk_path)
    if verbose and package_name:
        print_info(f"Package name: {package_name}")

    # Install APK with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Installing {apk_path.name}...",
            total=None,
        )

        success, output, elapsed = install_apk(
            adb_device,
            apk_path,
            reinstall=reinstall,
            verbose=verbose,
        )

        progress.remove_task(task)

    # Calculate file size
    install_size_mb = apk_path.stat().st_size / (1024 * 1024)

    # Prepare output
    if toon:
        toon_data = {
            "status": "success" if success else "error",
            "device": device_serial,
            "install_size_mb": round(install_size_mb, 2),
            "install_time_seconds": round(elapsed, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if package_name:
            toon_data["package_name"] = package_name

        if not success:
            toon_data["message"] = output.strip()

        console.print(format_toon_output(toon_data))
    else:
        if success:
            print_success(f"APK installed successfully in {elapsed:.2f}s")
            if package_name:
                print_info(f"Package: {package_name}")
            print_info(f"Size: {install_size_mb:.2f} MB")
        else:
            print_error("APK installation failed")
            if verbose or "INSTALL_FAILED" in output:
                console.print(f"[yellow]{output.strip()}[/yellow]")

            # Provide helpful error messages
            if "INSTALL_FAILED_INSUFFICIENT_STORAGE" in output:
                print_warning("Device has insufficient storage space")
            elif "INSTALL_FAILED_ALREADY_EXISTS" in output:
                print_warning("App already installed. Use --reinstall to replace")
            elif "INSTALL_PARSE_FAILED" in output:
                print_warning("Invalid or corrupted APK file")

    # Exit with appropriate code
    sys.exit(EXIT_SUCCESS if success else EXIT_ADB_COMMAND_FAILED)


if __name__ == "__main__":
    main()
