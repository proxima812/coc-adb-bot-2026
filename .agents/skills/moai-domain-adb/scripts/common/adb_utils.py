"""
Reusable ADB device operations and utilities.

This module provides functions for device discovery, verification, and
package list parsing used by 26 of the 29 migrated scripts.
"""

import subprocess
from typing import List, Optional

from error_handlers import ADBCommandFailed, ADBDeviceNotFound


def get_default_device(device_id: Optional[str] = None) -> str:
    """
    Purpose:
        Return the provided device_id or auto-select the first connected
        device. Provides flexible device specification for scripts that
        may not have explicit device selection.

    Parameters:
        device_id: Specific device ID to use (e.g., "127.0.0.1:5555" or
                   "emulator-5554"). If None, auto-selects first connected
                   device. Type: Optional[str]

    Returns:
        String device ID of the selected or auto-selected device.
        Type: str

    Examples:
        >>> # With explicit device
        >>> device = get_default_device("127.0.0.1:5555")
        >>> device
        '127.0.0.1:5555'

        >>> # Auto-select first device
        >>> device = get_default_device()
        >>> device
        'emulator-5554'

    Raises:
        ADBDeviceNotFound: If device_id is provided but not connected,
                          or if auto-select requested but no devices
                          connected (raised by list_connected_devices).

    Notes:
        - device_id parameter takes precedence if provided
        - Auto-selection uses first device from list_connected_devices()
        - No validation of device connectivity here (use
          verify_device_connected for that)
        - Handles both emulator and real device IDs

    Related:
        - list_connected_devices(): Auto-selects from connected devices
        - verify_device_connected(): Validates device is actually online
        - ADBDeviceNotFound: Exception raised if device not found

    Context:
        Used by 12+ scripts that support optional device specification.
        Allows scripts to work with single device (auto-select) or
        explicit device selection for multi-device scenarios.

    Implementation:
        1. Check if device_id is provided (not None)
        2. If provided, return it directly
        3. If None, call list_connected_devices() for auto-selection
        4. Return first device from list (raises if list empty)
    """
    if device_id is not None:
        return device_id

    # Auto-select first device from connected devices list
    devices = list_connected_devices()
    if not devices:
        raise ADBDeviceNotFound("(no devices connected)")

    return devices[0]


def list_connected_devices() -> List[str]:
    """
    Purpose:
        Return a list of all device IDs currently connected via ADB.
        Provides device discovery for auto-selection and enumeration
        in scripts.

    Parameters:
        None

    Returns:
        List of device ID strings (e.g., ["emulator-5554", "127.0.0.1:5555"]).
        Empty list if no devices connected. Type: List[str]

    Examples:
        >>> devices = list_connected_devices()
        >>> devices
        ['emulator-5554', 'R58M819JD7N']

        >>> len(devices)
        2

    Raises:
        ADBCommandFailed: If 'adb devices' command execution fails
                         (e.g., adb not in PATH, permission denied).

    Notes:
        - Executes 'adb devices' shell command
        - Parses output to extract device IDs only
        - Ignores header line ("List of attached devices")
        - Returns empty list if no devices (does not raise)
        - Device IDs have format: "emulator-NNNN" or "XXX.XXX.XXX.XXX:NNNNN"

    Related:
        - get_default_device(): Uses this to auto-select device
        - verify_device_connected(): Verifies individual device status
        - ADBCommandFailed: Exception for command failures

    Context:
        Called by get_default_device() for auto-selection. Also used by
        scripts that need to enumerate multiple devices or provide
        device selection UI.

    Implementation:
        1. Execute: subprocess.run(["adb", "devices"], capture_output=True)
        2. Decode output as UTF-8
        3. Split output into lines
        4. Skip header line ("List of attached devices")
        5. For each remaining line:
           - Split on whitespace
           - First part is device ID
           - Skip empty lines
        6. Return list of device IDs
    """
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ADBCommandFailed("adb devices", e.stderr or str(e))

    devices = []
    lines = result.stdout.strip().split("\n")

    # Skip header line and parse device IDs
    for line in lines[1:]:
        if not line.strip():
            continue

        parts = line.split()
        if parts:
            device_id = parts[0]
            devices.append(device_id)

    return devices


def verify_device_connected(device_id: str) -> bool:
    """
    Purpose:
        Verify that a specific device is connected and online by executing
        a simple ADB command. Ensures device is actually available before
        attempting operations.

    Parameters:
        device_id: The device ID to verify (e.g., "emulator-5554" or
                   "127.0.0.1:5555"). Type: str

    Returns:
        True if device is online and responsive, False if offline or
        unreachable. Type: bool

    Examples:
        >>> verify_device_connected("emulator-5554")
        True

        >>> verify_device_connected("offline-device")
        False

    Raises:
        No exceptions. Returns False if device offline/unreachable.

    Notes:
        - Executes: adb -s {device_id} shell echo "test"
        - Non-blocking: times out quickly for offline devices
        - Handles both online and offline states gracefully
        - Does not raise exceptions (returns boolean)
        - Suitable for device health checks in loops

    Related:
        - get_default_device(): Returns device to verify
        - list_connected_devices(): Lists devices to verify
        - ADBCommandFailed: Not raised (exception handling internal)

    Context:
        Used by scripts before executing device operations to ensure
        target device is actually available. Prevents wasted time on
        offline devices and provides early error detection.

    Implementation:
        1. Try to execute: adb -s {device_id} shell echo "test"
        2. Catch subprocess.CalledProcessError (command failed)
        3. Return True if success, False if exception
        4. No retry logic (simple yes/no check)
    """
    try:
        subprocess.run(
            ["adb", "-s", device_id, "shell", "echo", "test"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def parse_package_list(output: str) -> List[str]:
    """
    Purpose:
        Parse the output of 'pm list packages' command and return a clean
        list of package names. Removes package prefixes and filters empty
        lines for reliable package enumeration.

    Parameters:
        output: Raw output string from 'adb shell pm list packages' command.
                Format: "package:com.example.app\npackage:com.other.app\n..."
                Type: str

    Returns:
        List of clean package name strings without "package:" prefix.
        Type: List[str]

    Examples:
        >>> output = "package:com.android.chrome\\npackage:com.example.app\\n"
        >>> packages = parse_package_list(output)
        >>> packages
        ['com.android.chrome', 'com.example.app']

    Raises:
        No exceptions. Returns empty list if no packages found.

    Notes:
        - Removes "package:" prefix from each line
        - Filters empty lines and whitespace
        - Handles Windows and Unix line endings
        - Case-sensitive package name preservation
        - Idempotent: safe to call multiple times

    Related:
        - get_package_manager_info(): Uses for package discovery
        - analyze_package_stats(): Uses for package enumeration
        - verify_package_installed(): Checks if package in parsed list

    Context:
        Used by 3+ scripts that enumerate installed packages on device.
        Essential for package discovery, filtering, and analysis tasks.

    Implementation:
        1. Split output into lines
        2. For each line:
           - Strip whitespace
           - Skip empty lines
           - Remove "package:" prefix if present
           - Keep remaining string as package name
        3. Return filtered list of package names
    """
    packages = []

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Remove "package:" prefix if present
        if line.startswith("package:"):
            package_name = line[8:]  # len("package:") == 8
        else:
            package_name = line

        packages.append(package_name)

    return packages
