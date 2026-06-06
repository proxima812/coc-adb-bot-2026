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
Restart ADB server daemon.

Purpose:
    Kill and restart the ADB server daemon. Useful for fixing connection issues,
    clearing ADB state, and recovering from stuck connections.

Parameters:
    --toon - Output in YAML format
    --verbose/-v - Show detailed restart process

Returns:
    Text: Server restart status with device count
    TOON: YAML dict with {status, devices_found, device_list}

Examples:
    # Restart ADB server
    uv run adb_restart_server.py

    # Output as YAML
    uv run adb_restart_server.py --toon

    # Verbose mode with detailed steps
    uv run adb_restart_server.py --verbose

    # Chain with device status check
    uv run adb_restart_server.py && uv run adb_device_status.py

Raises:
    ADBError - If server restart failed
    EXIT_SUCCESS (0) - Server restarted successfully
    EXIT_ADB_COMMAND_FAILED (3) - ADB command execution failed

Notes:
    - Kills all existing ADB connections
    - Server automatically restarts on next ADB command
    - Wait time: 2 seconds after kill, 1 second after start
    - All connected devices must reconnect after restart
    - Safe to run even if no devices connected

Related:
    adb_connect.py, adb_device_status.py, adb_disconnect.py

Context:
    Run this when experiencing connection issues, devices not appearing, or ADB
    commands hanging. After restart, reconnect devices with adb_connect.py.

Implementation:
    1. Get ADB client via AdbClientHelper
    2. Execute: adb kill-server
    3. Wait 2 seconds for server to fully stop
    4. Execute: adb devices (implicitly starts server)
    5. Wait 1 second for server to initialize
    6. List devices to verify server running
    7. Format output as text or TOON based on flag
"""

import sys
import time
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
from error_handlers import handle_adb_errors, ADBError, EXIT_SUCCESS, EXIT_ADB_COMMAND_FAILED

console = Console()


@click.command()
@toon_output_option
@verbose_option
@handle_adb_errors
def main(toon: bool, verbose: bool):
    """Restart ADB server daemon"""

    try:
        if verbose:
            print_info("Restarting ADB server...")

        # Get ADB client
        client = AdbClientHelper.get_adb_client()

        # Kill server
        if verbose:
            print_info("Killing ADB server...")

        try:
            client.shell("adb kill-server")
        except:
            # kill-server may fail if no server running, that's OK
            if verbose:
                print_info("Server was not running")

        # Wait for server to stop
        time.sleep(2)

        # Start server by listing devices (this starts server automatically)
        if verbose:
            print_info("Starting ADB server...")

        devices = client.list_devices()

        # Wait for server to initialize
        time.sleep(1)

        # Verify server is running by listing devices again
        devices = client.list_devices()
        device_serials = [d.serial for d in devices]

        result = {
            "status": "restarted",
            "devices_found": len(devices),
            "device_list": device_serials
        }

        if toon:
            click.echo(format_toon_output(result))
        else:
            print_success("ADB server restarted successfully")
            print_info(f"Devices found: {len(devices)}")

            if verbose and devices:
                console.print("\n[cyan]Connected devices:[/cyan]")
                for device in devices:
                    state = "online" if device.is_alive() else "offline"
                    state_color = "green" if device.is_alive() else "red"
                    console.print(f"  [{state_color}]•[/{state_color}] {device.serial} ({state})")
            elif devices:
                for device in devices:
                    console.print(f"  • {device.serial}")

        sys.exit(EXIT_SUCCESS)

    except GenericAdbUnrecoverableError as e:
        error_msg = f"Fatal ADB error: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "fatal_adb_error",
                "message": str(e)
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
        sys.exit(EXIT_ADB_COMMAND_FAILED)

    except GenericAdbError as e:
        error_msg = f"ADB restart failed: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "restart_failed",
                "message": str(e)
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
        sys.exit(EXIT_ADB_COMMAND_FAILED)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "unexpected",
                "message": str(e)
            }
            click.echo(format_toon_output(result))
        else:
            print_error(error_msg)
        sys.exit(EXIT_ADB_COMMAND_FAILED)


if __name__ == "__main__":
    main()
