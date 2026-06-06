"""
Common utilities shared across all ADB UV scripts.

This package provides reusable components for path detection, ADB operations,
CLI utilities, and error handling used by the 29 migrated scripts.
"""

from .path_utils import detect_project_root, setup_adbautoplayer_path
from .adb_utils import (
    get_default_device,
    list_connected_devices,
    verify_device_connected,
    parse_package_list,
)
from .cli_utils import device_option, toon_output_option, verbose_option
from .error_handlers import (
    ADBError,
    ADBDeviceNotFound,
    ADBCommandFailed,
    EXIT_SUCCESS,
    EXIT_GENERIC_ERROR,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
    EXIT_INVALID_ARGUMENT,
)

__all__ = [
    # path_utils
    "detect_project_root",
    "setup_adbautoplayer_path",
    # adb_utils
    "get_default_device",
    "list_connected_devices",
    "verify_device_connected",
    "parse_package_list",
    # cli_utils
    "device_option",
    "toon_output_option",
    "verbose_option",
    # error_handlers
    "ADBError",
    "ADBDeviceNotFound",
    "ADBCommandFailed",
    "EXIT_SUCCESS",
    "EXIT_GENERIC_ERROR",
    "EXIT_DEVICE_OFFLINE",
    "EXIT_ADB_COMMAND_FAILED",
    "EXIT_INVALID_ARGUMENT",
]
