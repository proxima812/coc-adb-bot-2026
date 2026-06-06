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
Disconnect from ADB device.

Purpose:
    Terminate ADB connection to Android device. Safe to disconnect even if device
    is already disconnected or offline.

Parameters:
    --device/-d TEXT - Device ID or serial (default: 127.0.0.1:5555)
    --toon - Output in YAML format
    --verbose/-v - Show detailed disconnection info

Returns:
    Text: Disconnection status message
    TOON: YAML dict with {status, device_id, details}

Examples:
    # Disconnect from default device
    uv run adb_disconnect.py

    # Disconnect from specific device
    uv run adb_disconnect.py --device 127.0.0.1:5557

    # Output as YAML
    uv run adb_disconnect.py --toon

    # Verbose mode
    uv run adb_disconnect.py --verbose

Raises:
    ADBError - If ADB command failed (non-fatal)
    EXIT_SUCCESS (0) - Disconnection successful or device already disconnected
    EXIT_ADB_COMMAND_FAILED (3) - ADB command execution failed

Notes:
    - Safe to run even if device already disconnected
    - Does not stop the device or emulator, only closes ADB connection
    - Default device: 127.0.0.1:5555 (BlueStacks Instance 1)
    - BlueStacks ports: 5555 (Instance 1), 5557 (Instance 2), 5559 (Instance 3)

Related:
    adb_connect.py, adb_device_status.py, adb_restart_server.py

Context:
    Run this to clean up connections when finished using ADB. Also useful for
    troubleshooting connection issues. Device can be reconnected later with adb_connect.py.

Implementation:
    1. Resolve device ID from --device option or use default
    2. Execute: adb disconnect {device_id} via AdbClientHelper
    3. Verify disconnection by checking device list
    4. Format output as text or TOON based on flag
    5. Always returns success (0) even if already disconnected
"""

import sys
from pathlib import Path
import click
from rich.console import Console

# Add adbautoplayer to path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src-tauri" / "src-python"))

from adb_auto_player.device.adb.adb_client import AdbClientHelper
from adb_auto_player.exceptions import GenericAdbError, GenericAdbUnrecoverableError

# Import common utilities
COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))

from cli_utils import device_option, toon_output_option, verbose_option, print_success, print_error, print_info, format_toon_output
from error_handlers import handle_adb_errors, ADBError, EXIT_SUCCESS, EXIT_ADB_COMMAND_FAILED

console = Console()


@click.command()
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, toon: bool, verbose: bool):
    """Disconnect from ADB device"""

    # Use default device if not specified
    device_id = device if device else "127.0.0.1:5555"

    try:
        if verbose:
            print_info(f"Disconnecting from {device_id}...")

        # Get ADB client
        client = AdbClientHelper.get_adb_client()

        # Disconnect from device
        client.disconnect(device_id)

        # Verify disconnection
        devices = client.list_devices()
        device_serials = [d.serial for d in devices]
        still_connected = device_id in device_serials

        result = {
            "status": "disconnected",
            "device_id": device_id,
            "verified": not still_connected,
            "remaining_devices": device_serials
        }

        if toon:
            click.echo(format_toon_output(result))
        else:
            print_success(f"Successfully disconnected from {device_id}")
            if verbose:
                if still_connected:
                    console.print(f"[yellow]⚠ Device still appears in device list[/yellow]")
                else:
                    print_info("Device no longer in device list")
                if device_serials:
                    print_info(f"Remaining devices: {', '.join(device_serials)}")

        sys.exit(EXIT_SUCCESS)

    except GenericAdbUnrecoverableError as e:
        error_msg = f"Fatal ADB error: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "fatal_adb_error",
                "message": str(e),
                "device_id": device_id
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
        sys.exit(EXIT_ADB_COMMAND_FAILED)

    except GenericAdbError as e:
        # Disconnection errors are often non-fatal (device already disconnected)
        if verbose:
            print_info(f"ADB disconnect note: {e}")

        result = {
            "status": "disconnected",
            "device_id": device_id,
            "note": str(e)
        }

        if toon:
            click.echo(format_toon_output(result))
        else:
            print_success(f"Device {device_id} disconnected (already offline)")

        sys.exit(EXIT_SUCCESS)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "unexpected",
                "message": str(e),
                "device_id": device_id
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
        sys.exit(EXIT_ADB_COMMAND_FAILED)


if __name__ == "__main__":
    main()
