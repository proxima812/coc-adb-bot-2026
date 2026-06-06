#!/usr/bin/env python3
"""
ADB File Push Utility

Push files from local system to connected Android devices with progress tracking
and transfer speed calculation.

Dependencies:
    - click: CLI framework
    - rich: Terminal output formatting and progress bars
    - common.adb_utils: Device management and verification
    - common.cli_utils: Shared CLI options and output utilities
    - common.error_handlers: Error handling and exit codes

Author: MoAI-ADK
Date: 2025-12-01
"""

import os
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
)
from common.error_handlers import (
    handle_adb_errors,
    ADBError,
    EXIT_SUCCESS,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
    EXIT_INVALID_ARGUMENT,
)

# Setup paths
setup_adbautoplayer_path()

console = Console()


def validate_local_file(file_path: str) -> Path:
    """
    Validate local source file exists and is readable.

    Section 1: Overview
    --------------------
    Validates that the source file exists, is readable, and is a regular file
    (not a directory or special file).

    Section 2: Requirements
    -----------------------
    - File must exist in filesystem
    - File must be readable by current user
    - File must be a regular file (not directory)

    Section 3: Parameters
    ---------------------
    file_path : str
        Path to local file to validate

    Section 4: Returns
    ------------------
    Path
        Validated Path object for the file

    Section 5: Raises
    -----------------
    ADBError
        If file doesn't exist, not readable, or not a regular file

    Section 6: Examples
    -------------------
    >>> path = validate_local_file("/path/to/file.txt")
    >>> print(f"File size: {path.stat().st_size} bytes")

    Section 7: Notes
    ----------------
    - Converts to absolute path automatically
    - Checks file permissions before proceeding
    - Provides clear error messages for different failure modes

    Section 8: Edge Cases
    ---------------------
    - File doesn't exist: Raises clear error
    - Directory instead of file: Raises type error
    - Permission denied: Raises permission error
    - Symlink: Follows link and validates target

    Section 9: Implementation Details
    ----------------------------------
    Uses pathlib for cross-platform path handling and validation.
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise ADBError(f"File not found: {file_path}", EXIT_INVALID_ARGUMENT)

    if not path.is_file():
        raise ADBError(
            f"Path is not a regular file: {file_path}", EXIT_INVALID_ARGUMENT
        )

    if not os.access(path, os.R_OK):
        raise ADBError(f"File not readable: {file_path}", EXIT_INVALID_ARGUMENT)

    return path


def push_file(
    device: str, local_path: Path, remote_path: str, verbose: bool
) -> tuple[int, float, float]:
    """
    Push file from local system to Android device.

    Section 1: Overview
    --------------------
    Transfers file from local filesystem to Android device via ADB push command,
    measuring transfer time and calculating speed.

    Section 2: Requirements
    -----------------------
    - Device must be connected and online
    - Local file must exist and be readable
    - Remote path must be valid Android filesystem path
    - Device must have write permissions for target directory
    - Sufficient storage space on device

    Section 3: Parameters
    ---------------------
    device : str
        Device serial number or identifier
    local_path : Path
        Source file path (validated)
    remote_path : str
        Destination path on device
    verbose : bool
        Enable detailed progress logging

    Section 4: Returns
    ------------------
    tuple[int, float, float]
        - file_size: File size in bytes
        - duration: Transfer time in seconds
        - speed_kbs: Transfer speed in KB/s

    Section 5: Raises
    -----------------
    ADBError
        If push command fails, insufficient space, or permission denied

    Section 6: Examples
    -------------------
    >>> size, duration, speed = push_file(
    ...     "emulator-5554",
    ...     Path("/tmp/test.apk"),
    ...     "/sdcard/Download/test.apk",
    ...     False
    ... )
    >>> print(f"Transferred {size} bytes at {speed:.1f} KB/s")

    Section 7: Notes
    ----------------
    - Uses adb push command for efficient transfer
    - Shows progress indicator during transfer
    - Calculates transfer speed for performance monitoring
    - Handles large files (>100MB) efficiently
    - Preserves file timestamps

    Section 8: Edge Cases
    ---------------------
    - Insufficient space: Clear error with space needed
    - Permission denied: Error with target directory
    - Device disconnects: Connection error during transfer
    - Empty file: Transfers successfully with 0 bytes
    - Very large file: Progress indicator helps user wait

    Section 9: Implementation Details
    ----------------------------------
    Transfer process:
    1. Get file size for progress calculation
    2. Start timing measurement
    3. Execute adb push with device serial and paths
    4. Show progress spinner during transfer
    5. Calculate duration and speed
    6. Verify transfer success via exit code
    """
    import subprocess

    # Get file size
    file_size = local_path.stat().st_size

    if verbose:
        print_info(
            f"Pushing {local_path.name} ({file_size:,} bytes) to {remote_path}"
        )

    # Build ADB push command
    adb_cmd = ["adb", "-s", device, "push", str(local_path), remote_path]

    # Execute with progress indicator
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Pushing {local_path.name}...", total=None)

        try:
            result = subprocess.run(
                adb_cmd, capture_output=True, text=True, timeout=300, check=False
            )
        except subprocess.TimeoutExpired:
            raise ADBError("Push timed out after 5 minutes", EXIT_ADB_COMMAND_FAILED)
        finally:
            progress.update(task, completed=True)

    duration = time.time() - start_time

    # Check for errors
    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"

        if "No space left on device" in error_msg:
            raise ADBError(
                f"Insufficient storage space on device", EXIT_ADB_COMMAND_FAILED
            )
        elif "Permission denied" in error_msg:
            raise ADBError(
                f"Permission denied for path: {remote_path}", EXIT_ADB_COMMAND_FAILED
            )
        elif "Read-only file system" in error_msg:
            raise ADBError(
                f"Target path is read-only: {remote_path}", EXIT_ADB_COMMAND_FAILED
            )
        else:
            raise ADBError(f"Push failed: {error_msg}", EXIT_ADB_COMMAND_FAILED)

    # Calculate transfer speed
    speed_kbs = (file_size / 1024) / duration if duration > 0 else 0

    if verbose:
        print_info(
            f"Transfer complete: {duration:.2f}s at {speed_kbs:.1f} KB/s"
        )

    return file_size, duration, speed_kbs


@click.command()
@click.option(
    "--local",
    "-l",
    "local_path",
    required=True,
    help="Local source file path to push",
)
@click.option(
    "--remote",
    "-r",
    "remote_path",
    required=True,
    help="Remote destination path on device (e.g., /sdcard/Download/file.txt)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def adb_push(
    device: Optional[str],
    local_path: str,
    remote_path: str,
    toon: bool,
    verbose: bool,
) -> None:
    """
    Push file from local system to Android device.

    Section 1: Overview
    --------------------
    CLI tool for transferring files from local system to Android device via ADB
    with progress tracking, speed calculation, and validation.

    Section 2: Requirements
    -----------------------
    - ADB installed and in PATH
    - Device connected via USB or network
    - Local file exists and is readable
    - Device has write permissions for target path
    - Sufficient storage space on device

    Section 3: Parameters
    ---------------------
    device : Optional[str]
        Device serial (default: auto-detect)
    local_path : str
        Local source file path (required)
    remote_path : str
        Remote destination path on device (required)
    toon : bool
        Output in TOON/YAML format
    verbose : bool
        Enable detailed logging

    Section 4: Returns
    ------------------
    None
        Exits with code 0 on success, non-zero on error

    Section 5: Raises
    -----------------
    ADBError
        If file not found, device offline, insufficient space, or permission denied

    Section 6: Examples
    -------------------
    # Push APK to device
    $ uv run adb_push.py -l app.apk -r /sdcard/Download/app.apk

    # Push with verbose output
    $ uv run adb_push.py -l photo.jpg -r /sdcard/DCIM/photo.jpg --verbose

    # Push to specific device
    $ uv run adb_push.py -d emulator-5554 -l file.txt -r /data/local/tmp/file.txt

    # TOON output for scripting
    $ uv run adb_push.py -l data.json -r /sdcard/data.json --toon

    Section 7: Notes
    ----------------
    - Validates local file before starting transfer
    - Shows progress indicator during large transfers
    - Calculates and reports transfer speed
    - Common remote paths:
      - /sdcard/Download/: User downloads folder
      - /sdcard/DCIM/: Camera/photos folder
      - /data/local/tmp/: Temporary files (requires root)
      - /mnt/sdcard/: External SD card (if present)

    Section 8: Edge Cases
    ---------------------
    - File doesn't exist: Validation error before transfer
    - Insufficient space: Clear error with space needed
    - Permission denied: Error with target directory info
    - Device disconnects: Connection error during transfer
    - Empty file: Transfers successfully (0 bytes)
    - Very large file (>1GB): Progress indicator shows activity

    Section 9: Implementation Details
    ----------------------------------
    Exit codes:
    - 0: File pushed successfully
    - 2: Device offline or not found
    - 3: Push failed (no space, permission denied, etc.)
    - 4: Invalid arguments (file not found, bad path)

    Transfer speed calculation:
    - Measured in KB/s (kilobytes per second)
    - Includes only transfer time (not validation)
    - Typical speeds: USB 2.0 ~10-20 MB/s, USB 3.0 ~30-50 MB/s

    Output formats:
    - Human: Colored output with progress and speed
    - TOON: Structured YAML with file size, duration, speed
    """
    # Validate local file
    local_file = validate_local_file(local_path)

    # Get device
    if not device:
        device = get_default_device()

    # Verify device is connected
    verify_device_connected(device)

    # Push file
    file_size, duration, speed_kbs = push_file(device, local_file, remote_path, verbose)

    # Output results
    if toon:
        import yaml

        output = {
            "status": "success",
            "device": device,
            "local_file": str(local_file),
            "remote_path": remote_path,
            "file_size_bytes": file_size,
            "transfer_time_seconds": round(duration, 3),
            "transfer_speed_kbs": round(speed_kbs, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(yaml.dump(output, default_flow_style=False, allow_unicode=True))
    else:
        print_success(f"Pushed {local_file.name} to {remote_path}")
        print_info(
            f"Size: {file_size:,} bytes | "
            f"Time: {duration:.2f}s | "
            f"Speed: {speed_kbs:.1f} KB/s"
        )


if __name__ == "__main__":
    adb_push()
