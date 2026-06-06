#!/usr/bin/env python3
"""
ADB Shell Command Executor

Execute arbitrary shell commands on connected Android devices with timeout protection
and exit code preservation.

Dependencies:
    - click: CLI framework
    - rich: Terminal output formatting
    - common.adb_utils: Device management and verification
    - common.cli_utils: Shared CLI options and output utilities
    - common.error_handlers: Error handling and exit codes

Author: MoAI-ADK
Date: 2025-12-01
"""

import sys
import time
from typing import Optional

import click
from rich.console import Console

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


def execute_shell_command(
    device: str, command: str, timeout: int, verbose: bool
) -> tuple[str, str, int, float]:
    """
    Execute shell command on device with timeout protection.

    Section 1: Overview
    --------------------
    Executes arbitrary shell command on Android device via ADB, capturing stdout,
    stderr, exit code, and execution time.

    Section 2: Requirements
    -----------------------
    - Device must be connected and online
    - ADB daemon must be running
    - Command must be valid shell syntax
    - Timeout must be positive integer

    Section 3: Parameters
    ---------------------
    device : str
        Device serial number or identifier
    command : str
        Shell command to execute (can include pipes, redirects)
    timeout : int
        Maximum execution time in seconds
    verbose : bool
        Enable detailed output logging

    Section 4: Returns
    ------------------
    tuple[str, str, int, float]
        - stdout: Command standard output
        - stderr: Command standard error
        - exit_code: Command exit code (0 = success)
        - duration: Execution time in seconds

    Section 5: Raises
    -----------------
    ADBError
        If command execution fails or timeout exceeded

    Section 6: Examples
    -------------------
    >>> stdout, stderr, code, duration = execute_shell_command(
    ...     "emulator-5554", "ls -la /sdcard", 30, False
    ... )
    >>> print(f"Exit code: {code}, Duration: {duration:.2f}s")

    Section 7: Notes
    ----------------
    - Uses subprocess with timeout for safety
    - Preserves command exit codes
    - Supports complex shell syntax (pipes, redirects, &&, ||)
    - Times out gracefully with proper error messages
    - Separates stdout and stderr for clear diagnostics

    Section 8: Edge Cases
    ---------------------
    - Empty command: Raises validation error
    - Command not found: Returns non-zero exit code with stderr
    - Permission denied: Returns exit code 1 with error message
    - Timeout exceeded: Raises ADBError with timeout details
    - Device disconnects: Raises ADBError with connection error

    Section 9: Implementation Details
    ----------------------------------
    Execution flow:
    1. Validate command is non-empty
    2. Construct adb shell command with device serial
    3. Execute with subprocess.run() and timeout
    4. Measure execution time
    5. Capture and separate stdout/stderr
    6. Extract exit code from command result
    7. Handle timeout exceptions gracefully
    """
    import subprocess

    if not command.strip():
        raise ADBError("Command cannot be empty", EXIT_INVALID_ARGUMENT)

    if verbose:
        print_info(f"Executing on {device}: {command}")

    # Build ADB shell command
    adb_cmd = ["adb", "-s", device, "shell", command]

    start_time = time.time()
    try:
        result = subprocess.run(
            adb_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )
        duration = time.time() - start_time

        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode

        if verbose:
            print_info(f"Exit code: {exit_code}, Duration: {duration:.2f}s")
            if stdout:
                print_info(f"stdout: {stdout[:200]}...")
            if stderr:
                print_warning(f"stderr: {stderr[:200]}...")

        return stdout, stderr, exit_code, duration

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        raise ADBError(
            f"Command timed out after {timeout} seconds", EXIT_ADB_COMMAND_FAILED
        )
    except Exception as e:
        raise ADBError(f"Failed to execute command: {e}", EXIT_ADB_COMMAND_FAILED)


@click.command()
@click.option(
    "--command",
    "-c",
    required=True,
    help="Shell command to execute on device (can include pipes, redirects)",
)
@click.option(
    "--timeout",
    "-t",
    type=int,
    default=30,
    help="Command timeout in seconds (default: 30)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def adb_shell(
    device: Optional[str], command: str, timeout: int, toon: bool, verbose: bool
) -> None:
    """
    Execute arbitrary shell command on Android device.

    Section 1: Overview
    --------------------
    CLI tool for executing shell commands on Android devices via ADB with timeout
    protection, exit code preservation, and detailed output capture.

    Section 2: Requirements
    -----------------------
    - ADB installed and in PATH
    - Device connected via USB or network
    - Valid shell command syntax
    - Timeout between 1 and 3600 seconds

    Section 3: Parameters
    ---------------------
    device : Optional[str]
        Device serial (default: auto-detect)
    command : str
        Shell command to execute (required)
    timeout : int
        Maximum execution time in seconds (default: 30)
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
        If device offline, command fails, or timeout exceeded

    Section 6: Examples
    -------------------
    # Simple command
    $ uv run adb_shell.py -c "pm list packages"

    # Complex command with pipes
    $ uv run adb_shell.py -c "ps | grep com.android"

    # With timeout and verbose
    $ uv run adb_shell.py -c "find /sdcard -name '*.jpg'" -t 60 --verbose

    # TOON output
    $ uv run adb_shell.py -c "getprop ro.build.version.release" --toon

    Section 7: Notes
    ----------------
    - Supports complex shell syntax (pipes, redirects, &&, ||)
    - Preserves command exit codes for scripting
    - Separate stdout/stderr for clear diagnostics
    - Timeout protection prevents hanging commands
    - TOON format includes timing and exit code data

    Section 8: Edge Cases
    ---------------------
    - Empty command: Validation error before execution
    - Invalid timeout: Clamped to 1-3600 seconds
    - Command not found: Returns exit code 127 with stderr
    - Permission denied: Returns exit code 1 with error message
    - Device disconnects during execution: Raises connection error

    Section 9: Implementation Details
    ----------------------------------
    Exit codes:
    - 0: Command executed successfully (exit code 0)
    - 2: Device offline or not found
    - 3: ADB command failed or timeout
    - 4: Invalid arguments (empty command, bad timeout)

    Output formats:
    - Human: Colored output with clear sections
    - TOON: Structured YAML with all execution details
    """
    # Validate timeout
    if timeout < 1 or timeout > 3600:
        print_error("Timeout must be between 1 and 3600 seconds")
        sys.exit(EXIT_INVALID_ARGUMENT)

    # Get device
    if not device:
        device = get_default_device()

    # Verify device is connected
    verify_device_connected(device)

    # Execute command
    stdout, stderr, exit_code, duration = execute_shell_command(
        device, command, timeout, verbose
    )

    # Output results
    if toon:
        import yaml

        output = {
            "status": "success" if exit_code == 0 else "failed",
            "device": device,
            "command": command,
            "exit_code": exit_code,
            "duration_seconds": round(duration, 3),
            "timeout_seconds": timeout,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(yaml.dump(output, default_flow_style=False, allow_unicode=True))
    else:
        if exit_code == 0:
            print_success(f"Command executed successfully (exit code: 0)")
        else:
            print_warning(f"Command exited with code: {exit_code}")

        print_info(f"Duration: {duration:.3f}s")

        if stdout:
            console.print("\n[bold cyan]stdout:[/bold cyan]")
            console.print(stdout)

        if stderr:
            console.print("\n[bold yellow]stderr:[/bold yellow]")
            console.print(stderr)

    # Exit with command's exit code if not in TOON mode
    if not toon and exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    adb_shell()
