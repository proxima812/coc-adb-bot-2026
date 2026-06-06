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
Check ADB device connection status.

Purpose:
    List all connected ADB devices and their connection status. Shows device serial,
    state (online/offline), and optional device details (model, Android version).

Parameters:
    --device/-d TEXT - Filter to specific device serial (optional)
    --toon - Output in YAML format
    --verbose/-v - Show detailed device information (model, Android version)

Returns:
    Text: Rich table with device list and summary
    TOON: YAML dict with {devices: [{serial, state, model, android_version}], summary}

Examples:
    # List all devices
    uv run adb_device_status.py

    # Check specific device
    uv run adb_device_status.py --device 127.0.0.1:5555

    # Verbose output with model and Android version
    uv run adb_device_status.py --verbose

    # Output as YAML
    uv run adb_device_status.py --toon

    # Combine verbose and TOON
    uv run adb_device_status.py --verbose --toon

Raises:
    ADBError - If ADB client failed to initialize
    EXIT_SUCCESS (0) - Status check successful (even if no devices found)
    EXIT_ADB_COMMAND_FAILED (3) - ADB command execution failed

Notes:
    - Shows "online" for active devices, "offline" for disconnected
    - BlueStacks ports: 5555 (Instance 1), 5557 (Instance 2), 5559 (Instance 3)
    - Verbose mode queries device properties (requires device to be online)
    - Returns EXIT_SUCCESS even if no devices found
    - Device filtering is case-sensitive

Related:
    adb_connect.py, adb_disconnect.py, adb_restart_server.py

Context:
    Run this to verify device connections before operations, troubleshoot connection
    issues, or list available devices. Use --verbose to verify device details.

Implementation:
    1. Get ADB client via AdbClientHelper
    2. Execute: adb devices via client.list_devices()
    3. Filter by --device if specified
    4. For each device, check state via device.is_alive()
    5. If --verbose, query device properties:
       - Model: getprop ro.product.model
       - Android version: getprop ro.build.version.release
    6. Format as Rich table or YAML based on --toon flag
    7. Show summary with device counts and BlueStacks port info
"""

import sys
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table

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
    """Check ADB device connection status"""

    try:
        # Get ADB client
        client = AdbClientHelper.get_adb_client()

        # List devices
        devices = client.list_devices()

        if not devices:
            result = {
                "status": "no_devices",
                "devices": [],
                "summary": {
                    "total": 0,
                    "online": 0,
                    "offline": 0
                }
            }

            if toon:
                click.echo(format_toon_output(result))
            else:
                console.print("[yellow]⚠ No ADB devices found[/yellow]")
                print_info("Make sure devices are running and ADB is enabled")
                print_info("Try: adb_connect.py or adb_restart_server.py")

            sys.exit(EXIT_SUCCESS)

        # Filter to specific device if requested
        if device:
            devices = [d for d in devices if d.serial == device]
            if not devices:
                result = {
                    "status": "device_not_found",
                    "device": device,
                    "devices": [],
                    "summary": {
                        "total": 0,
                        "online": 0,
                        "offline": 0
                    }
                }

                if toon:
                    click.echo(format_toon_output(result))
                else:
                    console.print(f"[yellow]⚠ Device {device} not found[/yellow]")
                    print_info("Run without --device to see all devices")

                sys.exit(EXIT_SUCCESS)

        # Collect device information
        device_info_list = []
        online_count = 0

        for dev in devices:
            is_online = dev.is_alive()
            if is_online:
                online_count += 1

            device_data = {
                "serial": dev.serial,
                "state": "online" if is_online else "offline",
                "is_online": is_online
            }

            # Get verbose info if requested and device is online
            if verbose and is_online:
                try:
                    # Get device model
                    model = dev.shell("getprop ro.product.model").strip()
                    device_data["model"] = model if model else "Unknown"

                    # Get Android version
                    android_version = dev.shell("getprop ro.build.version.release").strip()
                    device_data["android_version"] = android_version if android_version else "Unknown"
                except Exception as e:
                    device_data["model"] = "N/A"
                    device_data["android_version"] = "N/A"
                    if verbose:
                        device_data["query_error"] = str(e)

            device_info_list.append(device_data)

        # Prepare result
        result = {
            "status": "success",
            "devices": device_info_list,
            "summary": {
                "total": len(devices),
                "online": online_count,
                "offline": len(devices) - online_count
            }
        }

        # Check for BlueStacks instances
        bluestacks_detected = any("127.0.0.1:555" in d.serial for d in devices)
        if bluestacks_detected:
            result["bluestacks_info"] = {
                "detected": True,
                "ports": {
                    "5555": "Instance 1",
                    "5557": "Instance 2",
                    "5559": "Instance 3"
                }
            }

        # Output
        if toon:
            click.echo(format_toon_output(result))
        else:
            # Create Rich table
            table = Table(title="ADB Devices", show_header=True, header_style="bold cyan")
            table.add_column("Serial", style="green")
            table.add_column("State", style="blue")

            if verbose:
                table.add_column("Model", style="magenta")
                table.add_column("Android", style="magenta")

            # Add device rows
            for dev_data in device_info_list:
                state_color = "green" if dev_data["is_online"] else "red"
                state_text = f"[{state_color}]{dev_data['state']}[/{state_color}]"

                row = [dev_data["serial"], state_text]

                if verbose:
                    row.append(dev_data.get("model", "N/A"))
                    android = dev_data.get("android_version", "N/A")
                    row.append(f"Android {android}" if android != "N/A" else "N/A")

                table.add_row(*row)

            console.print(table)

            # Summary
            console.print(f"\n[cyan]Total: {result['summary']['total']} device(s), "
                         f"{result['summary']['online']} online, "
                         f"{result['summary']['offline']} offline[/cyan]")

            # BlueStacks info
            if bluestacks_detected:
                console.print("\n[cyan]BlueStacks instances detected:[/cyan]")
                console.print("[dim]  Port 5555: Instance 1[/dim]")
                console.print("[dim]  Port 5557: Instance 2[/dim]")
                console.print("[dim]  Port 5559: Instance 3[/dim]")

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
        error_msg = f"ADB command failed: {e}"
        if toon:
            result = {
                "status": "error",
                "error": "adb_error",
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
