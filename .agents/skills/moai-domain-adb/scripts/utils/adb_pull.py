#!/usr/bin/env python3
"""
ADB File Pull Utility

Pull files from connected Android devices to local system with progress tracking
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


def validate_remote_file_exists(device: str, remote_path: str) -> bool:
    """
    Check if remote file exists on device.

    Section 1: Overview
    --------------------
    Verifies that the specified file exists on the Android device before attempting
    to pull it.

    Section 2: Requirements
    -----------------------
    - Device must be connected and online
    - Valid remote path format
    - Shell access to device

    Section 3: Parameters
    ---------------------
    device : str
        Device serial number or identifier
    remote_path : str
        Path to file on device

    Section 4: Returns
    ------------------
    bool
        True if file exists, False otherwise

    Section 5: Raises
    -----------------
    ADBError
        If unable to check file existence (device offline, shell error)

    Section 6: Examples
    -------------------
    >>> exists = validate_remote_file_exists("emulator-5554", "/sdcard/test.txt")
    >>> if exists:
    ...     print("File found on device")

    Section 7: Notes
    ----------------
    - Uses 'test -f' shell command for validation
    - Works for regular files only (not directories)
    - Returns False for non-existent files (not error)

    Section 8: Edge Cases
    ---------------------
    - Directory path: Returns False (not a file)
    - Symlink: Follows link and checks target
    - Permission denied: May return False even if file exists
    - Device disconnects: Raises ADBError

    Section 9: Implementation Details
    ----------------------------------
    Uses adb shell to execute test command:
    - Exit code 0: File exists
    - Exit code 1: File doesn't exist
    - Other codes: Command error
    """
    import subprocess

    adb_cmd = ["adb", "-s", device, "shell", f"test -f {remote_path}"]

    try:
        result = subprocess.run(
            adb_cmd, capture_output=True, timeout=10, check=False
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        raise ADBError("File existence check timed out", EXIT_ADB_COMMAND_FAILED)
    except Exception as e:
        raise ADBError(f"Failed to check file existence: {e}", EXIT_ADB_COMMAND_FAILED)


def validate_local_destination(file_path: str) -> Path:
    """
    Validate local destination path is writable.

    Section 1: Overview
    --------------------
    Ensures the local destination path is valid and the parent directory is writable
    before attempting file transfer.

    Section 2: Requirements
    -----------------------
    - Parent directory must exist or be creatable
    - Parent directory must be writable
    - Path must not be a directory

    Section 3: Parameters
    ---------------------
    file_path : str
        Local destination file path

    Section 4: Returns
    ------------------
    Path
        Validated Path object for destination

    Section 5: Raises
    -----------------
    ADBError
        If path is invalid, directory not writable, or path is a directory

    Section 6: Examples
    -------------------
    >>> path = validate_local_destination("/tmp/output.txt")
    >>> print(f"Will write to: {path}")

    Section 7: Notes
    ----------------
    - Creates parent directories automatically if needed
    - Converts to absolute path
    - Checks write permissions before proceeding

    Section 8: Edge Cases
    ---------------------
    - Parent directory doesn't exist: Creates it
    - Path is existing directory: Raises error
    - Permission denied: Raises clear error
    - Disk full: May not detect until actual write

    Section 9: Implementation Details
    ----------------------------------
    Validation steps:
    1. Convert to absolute Path object
    2. Check if path is existing directory (error)
    3. Get parent directory
    4. Create parent if it doesn't exist
    5. Verify parent is writable
    """
    path = Path(file_path).resolve()

    # Check if path is existing directory
    if path.exists() and path.is_dir():
        raise ADBError(
            f"Path is a directory, not a file: {file_path}", EXIT_INVALID_ARGUMENT
        )

    # Get parent directory
    parent = path.parent

    # Create parent directory if it doesn't exist
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ADBError(
                f"Failed to create directory {parent}: {e}", EXIT_INVALID_ARGUMENT
            )

    # Verify parent is writable
    if not os.access(parent, os.W_OK):
        raise ADBError(
            f"Directory not writable: {parent}", EXIT_INVALID_ARGUMENT
        )

    return path


def pull_file(
    device: str, remote_path: str, local_path: Path, verbose: bool
) -> tuple[int, float, float]:
    """
    Pull file from Android device to local system.

    Section 1: Overview
    --------------------
    Transfers file from Android device to local filesystem via ADB pull command,
    measuring transfer time and calculating speed.

    Section 2: Requirements
    -----------------------
    - Device must be connected and online
    - Remote file must exist on device
    - Local destination must be writable
    - Device must have read permissions for source file
    - Sufficient local disk space

    Section 3: Parameters
    ---------------------
    device : str
        Device serial number or identifier
    remote_path : str
        Source file path on device
    local_path : Path
        Destination path on local system (validated)
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
        If pull command fails, file not found, or permission denied

    Section 6: Examples
    -------------------
    >>> size, duration, speed = pull_file(
    ...     "emulator-5554",
    ...     "/sdcard/Download/log.txt",
    ...     Path("/tmp/log.txt"),
    ...     False
    ... )
    >>> print(f"Downloaded {size} bytes at {speed:.1f} KB/s")

    Section 7: Notes
    ----------------
    - Uses adb pull command for efficient transfer
    - Shows progress indicator during transfer
    - Calculates transfer speed for performance monitoring
    - Handles large files (>100MB) efficiently
    - File size determined after transfer (device doesn't report before)

    Section 8: Edge Cases
    ---------------------
    - File not found: Clear error before transfer
    - Permission denied: Error with source path info
    - Device disconnects: Connection error during transfer
    - Empty file: Transfers successfully with 0 bytes
    - Very large file: Progress indicator helps user wait
    - Disk full locally: Error during or after transfer

    Section 9: Implementation Details
    ----------------------------------
    Transfer process:
    1. Validate remote file exists
    2. Start timing measurement
    3. Execute adb pull with device serial and paths
    4. Show progress spinner during transfer
    5. Get file size from local file after transfer
    6. Calculate duration and speed
    7. Verify transfer success via exit code
    """
    import subprocess

    # Verify remote file exists
    if not validate_remote_file_exists(device, remote_path):
        raise ADBError(
            f"File not found on device: {remote_path}", EXIT_INVALID_ARGUMENT
        )

    if verbose:
        print_info(f"Pulling {remote_path} to {local_path}")

    # Build ADB pull command
    adb_cmd = ["adb", "-s", device, "pull", remote_path, str(local_path)]

    # Execute with progress indicator
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Pulling {Path(remote_path).name}...", total=None)

        try:
            result = subprocess.run(
                adb_cmd, capture_output=True, text=True, timeout=300, check=False
            )
        except subprocess.TimeoutExpired:
            raise ADBError("Pull timed out after 5 minutes", EXIT_ADB_COMMAND_FAILED)
        finally:
            progress.update(task, completed=True)

    duration = time.time() - start_time

    # Check for errors
    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"

        if "does not exist" in error_msg or "No such file" in error_msg:
            raise ADBError(
                f"File not found on device: {remote_path}", EXIT_ADB_COMMAND_FAILED
            )
        elif "Permission denied" in error_msg:
            raise ADBError(
                f"Permission denied for path: {remote_path}", EXIT_ADB_COMMAND_FAILED
            )
        else:
            raise ADBError(f"Pull failed: {error_msg}", EXIT_ADB_COMMAND_FAILED)

    # Get file size from local file
    if not local_path.exists():
        raise ADBError("File not created locally after pull", EXIT_ADB_COMMAND_FAILED)

    file_size = local_path.stat().st_size

    # Calculate transfer speed
    speed_kbs = (file_size / 1024) / duration if duration > 0 else 0

    if verbose:
        print_info(
            f"Transfer complete: {file_size:,} bytes in {duration:.2f}s at {speed_kbs:.1f} KB/s"
        )

    return file_size, duration, speed_kbs


@click.command()
@click.option(
    "--remote",
    "-r",
    "remote_path",
    required=True,
    help="Remote source file path on device (e.g., /sdcard/Download/file.txt)",
)
@click.option(
    "--local",
    "-l",
    "local_path",
    required=True,
    help="Local destination file path",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def adb_pull(
    device: Optional[str],
    remote_path: str,
    local_path: str,
    toon: bool,
    verbose: bool,
) -> None:
    """
    Pull file from Android device to local system.

    Section 1: Overview
    --------------------
    CLI tool for transferring files from Android device to local system via ADB
    with progress tracking, speed calculation, and validation.

    Section 2: Requirements
    -----------------------
    - ADB installed and in PATH
    - Device connected via USB or network
    - Remote file exists on device
    - Local destination is writable
    - Sufficient local disk space

    Section 3: Parameters
    ---------------------
    device : Optional[str]
        Device serial (default: auto-detect)
    remote_path : str
        Remote source file path on device (required)
    local_path : str
        Local destination file path (required)
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
        If file not found, device offline, permission denied, or disk full

    Section 6: Examples
    -------------------
    # Pull log file from device
    $ uv run adb_pull.py -r /sdcard/Download/log.txt -l ./log.txt

    # Pull with verbose output
    $ uv run adb_pull.py -r /data/local/tmp/output.json -l output.json --verbose

    # Pull from specific device
    $ uv run adb_pull.py -d emulator-5554 -r /sdcard/photo.jpg -l photo.jpg

    # TOON output for scripting
    $ uv run adb_pull.py -r /sdcard/data.db -l backup.db --toon

    Section 7: Notes
    ----------------
    - Validates remote file exists before starting transfer
    - Creates local parent directories automatically
    - Shows progress indicator during large transfers
    - Calculates and reports transfer speed
    - Common remote paths:
      - /sdcard/Download/: User downloads folder
      - /sdcard/DCIM/: Camera/photos folder
      - /data/local/tmp/: Temporary files (may require root)
      - /data/data/<package>/: App data (requires root)

    Section 8: Edge Cases
    ---------------------
    - Remote file doesn't exist: Validation error before transfer
    - Permission denied: Error with source path info
    - Device disconnects: Connection error during transfer
    - Empty file: Transfers successfully (0 bytes)
    - Very large file (>1GB): Progress indicator shows activity
    - Local disk full: Error during write

    Section 9: Implementation Details
    ----------------------------------
    Exit codes:
    - 0: File pulled successfully
    - 2: Device offline or not found
    - 3: Pull failed (not found, permission denied, etc.)
    - 4: Invalid arguments (bad path, not writable)

    Transfer speed calculation:
    - Measured in KB/s (kilobytes per second)
    - Includes only transfer time (not validation)
    - Typical speeds: USB 2.0 ~10-20 MB/s, USB 3.0 ~30-50 MB/s

    Output formats:
    - Human: Colored output with progress and speed
    - TOON: Structured YAML with file size, duration, speed

    File size determination:
    - Size measured from local file after transfer
    - Device doesn't provide size before pull
    """
    # Validate local destination
    local_file = validate_local_destination(local_path)

    # Get device
    if not device:
        device = get_default_device()

    # Verify device is connected
    verify_device_connected(device)

    # Pull file
    file_size, duration, speed_kbs = pull_file(device, remote_path, local_file, verbose)

    # Output results
    if toon:
        import yaml

        output = {
            "status": "success",
            "device": device,
            "remote_file": remote_path,
            "local_path": str(local_file),
            "file_size_bytes": file_size,
            "transfer_time_seconds": round(duration, 3),
            "transfer_speed_kbs": round(speed_kbs, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(yaml.dump(output, default_flow_style=False, allow_unicode=True))
    else:
        print_success(f"Pulled {Path(remote_path).name} to {local_file}")
        print_info(
            f"Size: {file_size:,} bytes | "
            f"Time: {duration:.2f}s | "
            f"Speed: {speed_kbs:.1f} KB/s"
        )


if __name__ == "__main__":
    adb_pull()
