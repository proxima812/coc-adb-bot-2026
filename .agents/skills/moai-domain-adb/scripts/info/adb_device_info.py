#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0.0",
#     "pydantic>=2.12.4,<3",
#     "anyio>=4.11.0,<5",
#     "adbutils>=2.12.0,<3",
#     "opencv-python>=4.12.0.88,<5",
#     "av>=16.0.1,<17",
#     "pillow>=12.0.0,<13",
#     "pytesseract>=0.3.13,<0.4",
#     "psutil>=7.1.3,<8",
#     "numpy>=2.2.6,<2.3",
# ]
# ///
"""
ADB Device Info - Get comprehensive device specifications

Purpose:
    Retrieve detailed device information including model, manufacturer, Android version,
    API level, build ID, CPU cores, memory, and storage information.
    Essential for device identification and hardware capability assessment.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/info/adb_device_info.py [OPTIONS]

    Options:
        --device/-d TEXT     Target device serial (default: first available)
        --toon               Output in TOON/YAML format
        --verbose/-v         Show detailed execution logs
        --help               Show this help message

Examples:
    # Get device info for default device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_device_info.py

    # Get device info for specific device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_device_info.py -d emulator-5554

    # Get device info in TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_device_info.py --toon

Exit Codes:
    0 - Success: Device info retrieved
    2 - Device offline or not found
    3 - ADB command failed

Dependencies:
    - click>=8.1.0: CLI framework
    - rich>=13.0.0: Terminal formatting
    - pyyaml>=6.0.0: TOON output
    - adbautoplayer: ADB device wrapper

Integration:
    Part of moai-domain-adb skill info scripts collection.
    Uses common utilities for device handling and output formatting.

Author: MoAI-ADK
Version: 1.0.0
Last Updated: 2025-12-01
"""

import sys
from pathlib import Path
from typing import Dict, Any

import click
from rich.console import Console
from rich.table import Table

# Setup ADB Auto Player path
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]  # scripts/
sys.path.insert(0, str(SCRIPTS_ROOT / "common"))

from path_utils import setup_adbautoplayer_path
from adb_utils import get_default_device, verify_device_connected
from cli_utils import (
    device_option,
    toon_output_option,
    verbose_option,
    print_success,
    print_error,
    print_info,
    create_info_table,
    output_toon,
)
from error_handlers import (
    handle_adb_errors,
    ADBError,
    EXIT_SUCCESS,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
)

# Initialize path
setup_adbautoplayer_path()

from adb_auto_player.device.adb.adb_device import AdbDeviceWrapper

console = Console()


def get_device_properties(device: AdbDeviceWrapper, verbose: bool = False) -> Dict[str, Any]:
    """
    Get comprehensive device properties.

    Args:
        device: ADB device wrapper
        verbose: Show detailed logs

    Returns:
        Dictionary containing device properties
    """
    properties = {}

    if verbose:
        print_info("Collecting device properties...")

    # Basic device info
    try:
        properties["model"] = device.shell("getprop ro.product.model").strip()
        properties["manufacturer"] = device.shell("getprop ro.product.manufacturer").strip()
        properties["android_version"] = device.shell("getprop ro.build.version.release").strip()
        properties["api_level"] = device.shell("getprop ro.build.version.sdk").strip()
        properties["build_id"] = device.shell("getprop ro.build.id").strip()
        properties["board"] = device.shell("getprop ro.product.board").strip()
        properties["device_type"] = device.shell("getprop ro.build.characteristics").strip()

        if verbose:
            print_info("✓ Basic properties collected")
    except Exception as e:
        if verbose:
            print_error(f"Failed to get basic properties: {e}")
        raise ADBError(f"Failed to get device properties: {e}", EXIT_ADB_COMMAND_FAILED)

    # CPU info
    try:
        properties["cpu_hardware"] = device.shell("getprop ro.hardware").strip()
        properties["cpu_cores"] = device.shell("nproc").strip()
        properties["cpu_abi"] = device.shell("getprop ro.product.cpu.abi").strip()

        if verbose:
            print_info("✓ CPU info collected")
    except Exception as e:
        if verbose:
            print_error(f"Failed to get CPU info: {e}")
        properties["cpu_hardware"] = "Unknown"
        properties["cpu_cores"] = "Unknown"
        properties["cpu_abi"] = "Unknown"

    # Memory info
    try:
        memory_info = device.shell("cat /proc/meminfo").strip()
        memory_total = "Unknown"
        memory_available = "Unknown"

        for line in memory_info.split("\n"):
            if "MemTotal" in line:
                memory_total = line.split()[1]
            elif "MemAvailable" in line:
                memory_available = line.split()[1]

        properties["memory_total_kb"] = memory_total
        properties["memory_total_mb"] = int(memory_total) // 1024 if memory_total != "Unknown" else "Unknown"
        properties["memory_available_kb"] = memory_available
        properties["memory_available_mb"] = int(memory_available) // 1024 if memory_available != "Unknown" else "Unknown"

        if verbose:
            print_info("✓ Memory info collected")
    except Exception as e:
        if verbose:
            print_error(f"Failed to get memory info: {e}")
        properties["memory_total_kb"] = "Unknown"
        properties["memory_total_mb"] = "Unknown"
        properties["memory_available_kb"] = "Unknown"
        properties["memory_available_mb"] = "Unknown"

    # Storage info
    try:
        storage_info = device.shell("df /data | tail -1").strip()
        storage_parts = storage_info.split()

        storage_total = storage_parts[1] if len(storage_parts) > 1 else "Unknown"
        storage_free = storage_parts[3] if len(storage_parts) > 3 else "Unknown"

        properties["storage_total_kb"] = storage_total
        properties["storage_total_mb"] = int(storage_total) // 1024 if storage_total != "Unknown" else "Unknown"
        properties["storage_free_kb"] = storage_free
        properties["storage_free_mb"] = int(storage_free) // 1024 if storage_free != "Unknown" else "Unknown"

        if verbose:
            print_info("✓ Storage info collected")
    except Exception as e:
        if verbose:
            print_error(f"Failed to get storage info: {e}")
        properties["storage_total_kb"] = "Unknown"
        properties["storage_total_mb"] = "Unknown"
        properties["storage_free_kb"] = "Unknown"
        properties["storage_free_mb"] = "Unknown"

    return properties


@click.command()
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, toon: bool, verbose: bool):
    """Get comprehensive device specifications"""

    if verbose:
        print_info("Starting device info retrieval...")

    # Get device serial
    device_serial = device or get_default_device()

    if verbose:
        print_info(f"Target device: {device_serial}")

    # Verify device connection
    verify_device_connected(device_serial, verbose)

    # Create device wrapper
    if verbose:
        print_info("Creating device wrapper...")

    device_wrapper = AdbDeviceWrapper(device_serial)

    # Get device properties
    properties = get_device_properties(device_wrapper, verbose)

    # Output results
    if toon:
        output_data = {
            "status": "success",
            "device": device_serial,
            "properties": properties,
        }
        output_toon(output_data)
    else:
        # Create rich table
        table = create_info_table("Device Information")

        # Add rows
        table.add_row("Model", properties["model"])
        table.add_row("Manufacturer", properties["manufacturer"])
        table.add_row("Android Version", f"{properties['android_version']} (API {properties['api_level']})")
        table.add_row("Build ID", properties["build_id"])
        table.add_row("Board", properties["board"])
        table.add_row("Device Type", properties["device_type"])
        table.add_row("", "")  # Separator
        table.add_row("CPU Hardware", properties["cpu_hardware"])
        table.add_row("CPU Cores", properties["cpu_cores"])
        table.add_row("CPU ABI", properties["cpu_abi"])
        table.add_row("", "")  # Separator
        table.add_row("Total Memory", f"{properties['memory_total_kb']} KB (~{properties['memory_total_mb']} MB)")
        table.add_row("Available Memory", f"{properties['memory_available_kb']} KB (~{properties['memory_available_mb']} MB)")
        table.add_row("", "")  # Separator
        table.add_row("Storage Total", f"{properties['storage_total_kb']} KB (~{properties['storage_total_mb']} MB)")
        table.add_row("Storage Free", f"{properties['storage_free_kb']} KB (~{properties['storage_free_mb']} MB)")

        console.print(table)

        print_success("Device info retrieved successfully")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
