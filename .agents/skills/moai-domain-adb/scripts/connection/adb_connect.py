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
Connect to ADB device (BlueStacks or physical).

Purpose:
    Establish ADB connection to Android device. Required before any device operations.
    Supports custom host/port for multiple BlueStacks instances or physical devices.

Parameters:
    --device/-d TEXT - Device ID or host:port (default: auto-select first device)
    --host TEXT - ADB host address (default: 127.0.0.1)
    --port INT - ADB port (default: 5555)
    --toon - Output in YAML format
    --verbose/-v - Show detailed connection info

Returns:
    Text: Connection status message with device verification
    TOON: YAML dict with {status, device_id, details, connected_devices}

Examples:
    # Connect to default device (127.0.0.1:5555)
    uv run adb_connect.py

    # Connect to specific device
    uv run adb_connect.py --device 127.0.0.1:5557

    # Connect using host and port
    uv run adb_connect.py --host 192.168.1.100 --port 5555

    # Output as YAML
    uv run adb_connect.py --toon

    # Verbose mode
    uv run adb_connect.py --verbose

Raises:
    ADBError - If device not found or connection failed
    EXIT_DEVICE_OFFLINE (2) - Device offline after connection attempt
    EXIT_ADB_COMMAND_FAILED (3) - ADB command execution failed

Notes:
    - Default device is 127.0.0.1:5555 (BlueStacks Instance 1)
    - Connection timeout: 5 seconds per attempt
    - Verifies connection by listing devices after connect
    - BlueStacks ports: 5555 (Instance 1), 5557 (Instance 2), 5559 (Instance 3)

Related:
    adb_disconnect.py, adb_device_status.py, adb_restart_server.py

Context:
    Run this first before using any other ADB commands. Verify connection with
    adb_device_status.py. If connection fails, try adb_restart_server.py.

Implementation:
    1. Resolve device ID from --device or construct from --host:--port
    2. Execute: adb connect {device_id} via AdbClientHelper
    3. Verify connection by listing devices
    4. Format output as text or TOON based on flag
    5. Set exit code based on connection status
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

from cli_utils import toon_output_option, verbose_option, print_success, print_error, print_info, format_toon_output
from error_handlers import handle_adb_errors, ADBError, EXIT_SUCCESS, EXIT_DEVICE_OFFLINE, EXIT_ADB_COMMAND_FAILED

console = Console()


@click.command()
@click.option(
    "--device",
    "-d",
    default=None,
    help="Device ID (e.g., 127.0.0.1:5555). If not specified, uses --host:--port",
    type=str,
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="ADB host address (default: 127.0.0.1)",
    type=str,
)
@click.option(
    "--port",
    default=5555,
    help="ADB port (default: 5555)",
    type=int,
)
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, host: str, port: int, toon: bool, verbose: bool):
    """Connect to ADB device (BlueStacks or physical)"""

    # Resolve device ID
    device_id = device if device else f"{host}:{port}"

    try:
        if verbose:
            print_info(f"Connecting to {device_id}...")

        # Get ADB client
        client = AdbClientHelper.get_adb_client()

        # Parse host and port from device_id if needed
        if ":" in device_id:
            connect_host, connect_port = device_id.rsplit(":", 1)
            connect_port = int(connect_port)
        else:
            connect_host = device_id
            connect_port = 5555

        # Connect to device
        client.connect(connect_host, connect_port)

        # Verify connection by listing devices
        devices = client.list_devices()
        device_serials = [d.serial for d in devices]
        connected = device_id in device_serials

        if connected:
            result = {
                "status": "connected",
                "device_id": device_id,
                "verified": True,
                "connected_devices": device_serials
            }

            if toon:
                click.echo(format_toon_output(result))
            else:
                print_success(f"Successfully connected to {device_id}")
                if verbose:
                    print_info("Device verified in device list")
                    print_info(f"Connected devices: {', '.join(device_serials)}")

            sys.exit(EXIT_SUCCESS)
        else:
            result = {
                "status": "connected_but_unverified",
                "device_id": device_id,
                "verified": False,
                "connected_devices": device_serials,
                "warning": "Connection established but device not in list"
            }

            if toon:
                click.echo(format_toon_output(result))
            else:
                print_success(f"Connection established to {device_id}")
                console.print(f"[yellow]⚠ Device not verified in device list[/yellow]")
                if verbose:
                    print_info(f"Available devices: {', '.join(device_serials)}")

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
        error_msg = f"ADB connection failed: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "connection_failed",
                "message": str(e),
                "device_id": device_id,
                "hint": "Make sure device is running and ADB is enabled"
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
            print_info("Make sure device is running and ADB is enabled")
        sys.exit(EXIT_DEVICE_OFFLINE)

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
