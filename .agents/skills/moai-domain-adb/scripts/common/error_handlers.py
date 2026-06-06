"""
Standardized error handling and exit codes.

This module provides custom exception classes and standardized exit codes
for consistent error handling across all 29 migrated scripts.
"""

from typing import Optional

# ============================================================================
# Exit Codes (POSIX Standard)
# ============================================================================

EXIT_SUCCESS = 0
"""Success exit code: All operations completed successfully."""

EXIT_GENERIC_ERROR = 1
"""Generic error exit code: Unhandled or unexpected error."""

EXIT_DEVICE_OFFLINE = 2
"""Device error exit code: Device not connected or offline."""

EXIT_ADB_COMMAND_FAILED = 3
"""ADB error exit code: ADB command execution failed."""

EXIT_INVALID_ARGUMENT = 4
"""Argument error exit code: Invalid user input or arguments."""


# ============================================================================
# Custom Exceptions
# ============================================================================


class ADBError(Exception):
    """
    Purpose:
        Base exception class for all ADB-related errors. Provides consistent
        error handling with exit codes across all scripts.

    Parameters:
        message: Error message describing what went wrong. Type: str
        exit_code: Exit code to use when script terminates. Default: 1.
                   Type: int (see exit code constants above)

    Returns:
        Exception instance with message and exit_code attributes. Type: ADBError

    Examples:
        >>> try:
        ...     raise ADBError("Device not found", EXIT_DEVICE_OFFLINE)
        ... except ADBError as e:
        ...     print(f"Error: {e.message}")
        ...     sys.exit(e.exit_code)

    Raises:
        No exceptions from constructor.

    Notes:
        - Base class for all ADB exceptions
        - Always has message and exit_code attributes
        - exit_code suitable for sys.exit()
        - Can be caught as generic Exception or specific ADBError

    Related:
        - ADBDeviceNotFound: Device-specific error
        - ADBCommandFailed: Command execution error
        - handle_adb_errors: Decorator for automatic handling

    Context:
        Used by all utility modules for consistent error reporting.
        Enables scripts to distinguish ADB errors from other exceptions.

    Implementation:
        1. Store message and exit_code as attributes
        2. Call parent Exception.__init__() with message
        3. Enables catching specific exit codes
    """

    def __init__(
        self, message: str, exit_code: int = EXIT_GENERIC_ERROR
    ) -> None:
        """Initialize ADBError with message and exit code."""
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


class ADBDeviceNotFound(ADBError):
    """
    Purpose:
        Exception raised when a requested device is not found or not
        connected. Indicates device connectivity issue.

    Parameters:
        device_id: The device ID that was not found (e.g., "emulator-5554").
                   Type: str

    Returns:
        Exception instance with device_id context and EXIT_DEVICE_OFFLINE
        exit code. Type: ADBDeviceNotFound

    Examples:
        >>> try:
        ...     if device_id not in connected_devices:
        ...         raise ADBDeviceNotFound("emulator-5555")
        ... except ADBDeviceNotFound as e:
        ...     print(f"Error: {e.message}")
        ...     print(f"Exit code: {e.exit_code}")
        ...     sys.exit(e.exit_code)

    Raises:
        No exceptions from constructor.

    Notes:
        - exit_code: EXIT_DEVICE_OFFLINE (2)
        - Used for device not found scenarios
        - Provides device_id context for debugging
        - Message format: "Device {device_id} not found"

    Related:
        - ADBError: Parent exception class
        - get_default_device(): Raises this exception
        - list_connected_devices(): Called to find devices

    Context:
        Raised when user specifies device that is not connected, or when
        auto-select fails due to no connected devices.

    Implementation:
        1. Build message with device_id context
        2. Call parent with message and EXIT_DEVICE_OFFLINE code
    """

    def __init__(self, device_id: str) -> None:
        """Initialize ADBDeviceNotFound with device_id context."""
        message = f"Device {device_id} not found"
        super().__init__(message, EXIT_DEVICE_OFFLINE)


class ADBCommandFailed(ADBError):
    """
    Purpose:
        Exception raised when an ADB shell command fails. Indicates command
        execution error on device or ADB-level failure.

    Parameters:
        command: The ADB command that failed (e.g., "adb shell pm list packages").
                 Type: str
        error: The error message from command execution (stderr output or
               exception message). Type: str

    Returns:
        Exception instance with command context and EXIT_ADB_COMMAND_FAILED
        exit code. Type: ADBCommandFailed

    Examples:
        >>> try:
        ...     result = subprocess.run(["adb", "shell", "..."], check=True)
        ... except subprocess.CalledProcessError as e:
        ...     raise ADBCommandFailed("adb shell pm list packages", e.stderr)

    Raises:
        No exceptions from constructor.

    Notes:
        - exit_code: EXIT_ADB_COMMAND_FAILED (3)
        - Used for ADB command execution failures
        - Includes command context for debugging
        - Message format: "ADB command failed: {command}\n{error}"

    Related:
        - ADBError: Parent exception class
        - ADBDeviceNotFound: Device connectivity error
        - list_connected_devices(): Raises this exception

    Context:
        Raised when subprocess.run() fails for ADB commands. Used by
        list_connected_devices() and other ADB operations.

    Implementation:
        1. Build message with command and error context
        2. Call parent with message and EXIT_ADB_COMMAND_FAILED code
    """

    def __init__(self, command: str, error: str) -> None:
        """Initialize ADBCommandFailed with command and error context."""
        message = f"ADB command failed: {command}\n{error}"
        super().__init__(message, EXIT_ADB_COMMAND_FAILED)


# ============================================================================
# Decorator for Error Handling (Optional)
# ============================================================================


def handle_adb_errors(func):
    """
    Purpose:
        Decorator for automatic ADB error handling. Catches ADBError
        exceptions, prints error message, and exits with appropriate code.

    Parameters:
        func: Function to decorate (should be click command). Type: callable

    Returns:
        Decorated function with error handling. Type: callable

    Examples:
        >>> @click.command()
        >>> @handle_adb_errors
        >>> def my_command():
        ...     raise ADBDeviceNotFound("emulator-5554")
        ... # Decorator catches exception, prints error, exits with code 2

    Raises:
        No exceptions raised (all caught and handled).

    Notes:
        - Only catches ADBError and subclasses
        - Uses cli_utils.print_error() for output
        - Exits with ADBError.exit_code
        - Allows other exceptions to propagate

    Related:
        - ADBError: Exceptions this decorator handles
        - cli_utils.print_error(): Used for output
        - click.command: Typically decorates click commands

    Context:
        Optional decorator for commands that want automatic error handling.
        Simplifies click command implementations.

    Implementation:
        1. Wrap function in try/except
        2. Catch ADBError exceptions
        3. Call print_error() with exception message
        4. Call sys.exit() with exception exit_code
        5. Let other exceptions propagate normally
    """
    import sys
    from functools import wraps

    from cli_utils import print_error

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ADBError as e:
            print_error(e.message)
            sys.exit(e.exit_code)

    return wrapper
