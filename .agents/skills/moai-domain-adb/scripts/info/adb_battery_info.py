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
ADB Battery Info - Get battery status and health information

Purpose:
    Retrieve comprehensive battery information including level, temperature, health status,
    charging state, voltage, and technology. Essential for device health monitoring during
    automation and long-running operations.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/info/adb_battery_info.py [OPTIONS]

    Options:
        --device/-d TEXT     Target device serial (default: first available)
        --toon               Output in TOON/YAML format
        --verbose/-v         Show detailed execution logs
        --help               Show this help message

Examples:
    # Get battery info for default device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_battery_info.py

    # Get battery info for specific device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_battery_info.py -d emulator-5554

    # Get battery info in TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_battery_info.py --toon

Exit Codes:
    0 - Success: Battery info retrieved
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
    print_warning,
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


def parse_battery_info(dumpsys_output: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Parse dumpsys battery output.

    Args:
        dumpsys_output: Raw dumpsys battery output
        verbose: Show detailed logs

    Returns:
        Dictionary containing parsed battery information
    """
    battery_info = {}

    for line in dumpsys_output.split("\n"):
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            battery_info[key] = value

    if verbose:
        print_info(f"Parsed {len(battery_info)} battery properties")

    return battery_info


def format_battery_properties(raw_info: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """
    Format battery properties for display.

    Args:
        raw_info: Raw battery info from dumpsys
        verbose: Show detailed logs

    Returns:
        Formatted battery properties
    """
    properties = {}

    # Battery level (0-100)
    level = raw_info.get("level", "Unknown")
    properties["level_percent"] = level

    # Temperature (divide by 10 to get Celsius)
    temperature_raw = raw_info.get("temperature", "0")
    try:
        temp_celsius = float(temperature_raw) / 10.0
        properties["temperature_celsius"] = f"{temp_celsius:.1f}"
        properties["temperature_raw"] = temperature_raw
    except (ValueError, TypeError):
        properties["temperature_celsius"] = "Unknown"
        properties["temperature_raw"] = temperature_raw

    # Health status
    health_code = raw_info.get("health", "Unknown")
    health_map = {
        "1": "Unknown",
        "2": "Good",
        "3": "Overheat",
        "4": "Dead",
        "5": "Over voltage",
        "6": "Unspecified failure",
        "7": "Cold",
    }
    properties["health_status"] = health_map.get(health_code, f"Code {health_code}")
    properties["health_code"] = health_code

    # Charging status
    status_code = raw_info.get("status", "Unknown")
    status_map = {
        "1": "Unknown",
        "2": "Charging",
        "3": "Discharging",
        "4": "Not charging",
        "5": "Full",
    }
    properties["charging_status"] = status_map.get(status_code, f"Code {status_code}")
    properties["charging_code"] = status_code

    # Voltage (millivolts)
    voltage = raw_info.get("voltage", "Unknown")
    properties["voltage_mv"] = voltage
    try:
        voltage_v = float(voltage) / 1000.0
        properties["voltage_v"] = f"{voltage_v:.2f}"
    except (ValueError, TypeError):
        properties["voltage_v"] = "Unknown"

    # Power sources
    properties["ac_powered"] = raw_info.get("ac powered", "false")
    properties["usb_powered"] = raw_info.get("usb powered", "false")
    properties["wireless_powered"] = raw_info.get("wireless powered", "false")

    # Technology
    properties["technology"] = raw_info.get("technology", "Unknown")

    # Current (microamps)
    current = raw_info.get("current now", "Unknown")
    properties["current_ua"] = current
    try:
        current_ma = float(current) / 1000.0
        properties["current_ma"] = f"{current_ma:.1f}"
    except (ValueError, TypeError):
        properties["current_ma"] = "Unknown"

    # Charge counter (microamp-hours)
    charge_counter = raw_info.get("charge counter", "Unknown")
    properties["charge_counter_uah"] = charge_counter

    # Cycle count (if available)
    cycle_count = raw_info.get("cycle count", "Unknown")
    properties["cycle_count"] = cycle_count

    return properties


def get_health_indicator(health_status: str, temperature: str, level: str) -> str:
    """
    Get health indicator symbol and color.

    Args:
        health_status: Health status string
        temperature: Temperature in Celsius
        level: Battery level percent

    Returns:
        Colored indicator string
    """
    # Check critical conditions
    try:
        temp = float(temperature)
        if temp > 45.0:
            return "[red]⚠ CRITICAL[/red]"
        elif temp > 40.0:
            return "[yellow]⚠ WARNING[/yellow]"
    except (ValueError, TypeError):
        pass

    # Check health status
    if health_status in ["Good"]:
        return "[green]✓ HEALTHY[/green]"
    elif health_status in ["Overheat", "Dead", "Over voltage", "Cold"]:
        return "[red]⚠ CRITICAL[/red]"
    else:
        return "[yellow]? UNKNOWN[/yellow]"


@click.command()
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, toon: bool, verbose: bool):
    """Get battery status and health information"""

    if verbose:
        print_info("Starting battery info retrieval...")

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

    # Get battery info
    if verbose:
        print_info("Retrieving battery info from dumpsys...")

    try:
        dumpsys_output = device_wrapper.shell("dumpsys battery").strip()
    except Exception as e:
        raise ADBError(f"Failed to get battery info: {e}", EXIT_ADB_COMMAND_FAILED)

    # Parse battery info
    raw_info = parse_battery_info(dumpsys_output, verbose)
    properties = format_battery_properties(raw_info, verbose)

    # Output results
    if toon:
        output_data = {
            "status": "success",
            "device": device_serial,
            "battery": properties,
        }
        output_toon(output_data)
    else:
        # Create rich table
        table = create_info_table("Battery Information")

        # Add rows
        table.add_row("Battery Level", f"{properties['level_percent']}%")
        table.add_row("Temperature", f"{properties['temperature_celsius']}°C ({properties['temperature_raw']} raw)")
        table.add_row("Health Status", properties["health_status"])
        table.add_row("Charging Status", properties["charging_status"])
        table.add_row("", "")  # Separator
        table.add_row("Voltage", f"{properties['voltage_v']}V ({properties['voltage_mv']} mV)")
        table.add_row("Current", f"{properties['current_ma']} mA ({properties['current_ua']} µA)")
        table.add_row("Technology", properties["technology"])
        table.add_row("", "")  # Separator
        table.add_row("AC Powered", properties["ac_powered"])
        table.add_row("USB Powered", properties["usb_powered"])
        table.add_row("Wireless Powered", properties["wireless_powered"])

        if properties["cycle_count"] != "Unknown":
            table.add_row("", "")  # Separator
            table.add_row("Cycle Count", properties["cycle_count"])

        console.print(table)

        # Health indicator
        health_indicator = get_health_indicator(
            properties["health_status"],
            properties["temperature_celsius"],
            properties["level_percent"],
        )

        console.print(f"\n[cyan]Overall Health:[/cyan] {health_indicator}")

        # Warnings
        try:
            temp = float(properties["temperature_celsius"])
            if temp > 45.0:
                print_warning(f"⚠ High temperature detected: {temp}°C")

            level = int(properties["level_percent"])
            if level < 15:
                print_warning(f"⚠ Low battery: {level}%")
        except (ValueError, TypeError):
            pass

        print_success("Battery info retrieved successfully")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
