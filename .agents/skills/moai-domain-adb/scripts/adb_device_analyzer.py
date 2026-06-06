#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
# ]
# ///
"""
ADB Device Analyzer - Comprehensive device capability analysis tool.

This script analyzes connected ADB devices and provides detailed information about
their capabilities including API level, screen resolution, RAM, CPU threads, and
hardware specifications.

Purpose:
    - Analyze ADB device hardware and software capabilities
    - Detect device specifications for automation compatibility
    - Output human-readable tables or machine-parseable JSON
    - Support multiple device selection and filtering

Features:
    - API level detection (Android version mapping)
    - Screen resolution and density analysis
    - RAM and storage capacity detection
    - CPU architecture and thread count
    - Battery status and temperature
    - Device manufacturer and model information
    - JSON export for integration pipelines

Usage:
    # Analyze default device
    python adb_device_analyzer.py

    # Analyze specific device
    python adb_device_analyzer.py --device emulator-5554

    # Output JSON format
    python adb_device_analyzer.py --json

    # Verbose output with debug info
    python adb_device_analyzer.py --verbose

Exit Codes:
    0: Success
    1: No devices found
    2: Device offline or unauthorized
    3: ADB command failed
    4: Invalid device specified

Author: MoAI-ADK Domain ADB Expert
Version: 1.0.0
License: MIT
"""

# ============================================================================
# SECTION 2: IMPORTS
# ============================================================================

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# ============================================================================
# SECTION 3: CONFIGURATION
# ============================================================================

# API Level to Android Version mapping
ANDROID_VERSIONS = {
    34: "Android 14",
    33: "Android 13",
    32: "Android 12L",
    31: "Android 12",
    30: "Android 11",
    29: "Android 10",
    28: "Android 9 (Pie)",
    27: "Android 8.1 (Oreo)",
    26: "Android 8.0 (Oreo)",
    25: "Android 7.1 (Nougat)",
    24: "Android 7.0 (Nougat)",
    23: "Android 6.0 (Marshmallow)",
    22: "Android 5.1 (Lollipop)",
    21: "Android 5.0 (Lollipop)",
}

# ADB command timeout in seconds
ADB_TIMEOUT = 10

# Console for rich output
console = Console()

# ============================================================================
# SECTION 4: ROOT DETECTION
# ============================================================================

def detect_project_root() -> Path:
    """
    Detect project root directory.

    Returns:
        Path: Absolute path to project root directory.

    Note:
        For zero-context design, this script assumes execution from
        within the project structure. Falls back to current directory.
    """
    current = Path.cwd()

    # Look for common project markers
    markers = [".git", "pyproject.toml", "package.json", ".moai"]

    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent

    return Path.cwd()


PROJECT_ROOT = detect_project_root()

# ============================================================================
# SECTION 5: DATA MODELS
# ============================================================================

@dataclass
class DeviceInfo:
    """
    Comprehensive device information container.

    Attributes:
        serial: Device serial number (e.g., 'emulator-5554')
        model: Device model name (e.g., 'Pixel 6')
        manufacturer: Device manufacturer (e.g., 'Google')
        android_version: Human-readable Android version (e.g., 'Android 13')
        api_level: Android API level (e.g., 33)
        resolution: Screen resolution (e.g., '1080x2400')
        density: Screen density in dpi (e.g., 420)
        ram_total_mb: Total RAM in megabytes
        ram_available_mb: Available RAM in megabytes
        cpu_architecture: CPU architecture (e.g., 'arm64-v8a')
        cpu_threads: Number of CPU threads
        storage_total_gb: Total storage in gigabytes
        storage_available_gb: Available storage in gigabytes
        battery_level: Battery level percentage (0-100)
        battery_temperature: Battery temperature in Celsius
        is_emulator: Whether device is an emulator
        state: Device state (device, offline, unauthorized)
        errors: List of errors encountered during analysis
    """

    serial: str
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    android_version: str = "Unknown"
    api_level: int = 0
    resolution: str = "Unknown"
    density: int = 0
    ram_total_mb: int = 0
    ram_available_mb: int = 0
    cpu_architecture: str = "Unknown"
    cpu_threads: int = 0
    storage_total_gb: float = 0.0
    storage_available_gb: float = 0.0
    battery_level: int = 0
    battery_temperature: float = 0.0
    is_emulator: bool = False
    state: str = "device"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert device info to dictionary format."""
        return {
            "serial": self.serial,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "android_version": self.android_version,
            "api_level": self.api_level,
            "resolution": self.resolution,
            "density": self.density,
            "ram": {
                "total_mb": self.ram_total_mb,
                "available_mb": self.ram_available_mb,
            },
            "cpu": {
                "architecture": self.cpu_architecture,
                "threads": self.cpu_threads,
            },
            "storage": {
                "total_gb": self.storage_total_gb,
                "available_gb": self.storage_available_gb,
            },
            "battery": {
                "level_percent": self.battery_level,
                "temperature_celsius": self.battery_temperature,
            },
            "is_emulator": self.is_emulator,
            "state": self.state,
            "errors": self.errors,
        }


# ============================================================================
# SECTION 6: CUSTOM EXCEPTIONS
# ============================================================================

class DeviceAnalyzerError(Exception):
    """Base exception for device analyzer errors."""
    pass


class DeviceOfflineError(DeviceAnalyzerError):
    """Raised when device is offline or unauthorized."""
    pass


class TimeoutError(DeviceAnalyzerError):
    """Raised when ADB command times out."""
    pass


class NoDevicesFoundError(DeviceAnalyzerError):
    """Raised when no ADB devices are found."""
    pass


# ============================================================================
# SECTION 7: CORE LOGIC
# ============================================================================

def run_adb_command(
    command: list[str],
    device: Optional[str] = None,
    timeout: int = ADB_TIMEOUT,
) -> str:
    """
    Execute ADB command and return output.

    Args:
        command: ADB command arguments (e.g., ['shell', 'getprop'])
        device: Optional device serial number
        timeout: Command timeout in seconds

    Returns:
        str: Command output (stdout)

    Raises:
        TimeoutError: If command exceeds timeout
        subprocess.CalledProcessError: If command fails
    """
    cmd = ["adb"]
    if device:
        cmd.extend(["-s", device])
    cmd.extend(command)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"ADB command timed out after {timeout}s: {' '.join(cmd)}") from e


def get_connected_devices() -> list[str]:
    """
    Get list of connected ADB devices.

    Returns:
        list[str]: List of device serial numbers

    Raises:
        NoDevicesFoundError: If no devices are connected
    """
    output = run_adb_command(["devices"])
    lines = output.split("\n")[1:]  # Skip header line

    devices = []
    for line in lines:
        if line.strip():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

    if not devices:
        raise NoDevicesFoundError("No ADB devices found. Connect a device or start an emulator.")

    return devices


def analyze_device(device_serial: str, verbose: bool = False) -> DeviceInfo:
    """
    Analyze comprehensive device information.

    Args:
        device_serial: Device serial number
        verbose: Enable verbose logging

    Returns:
        DeviceInfo: Complete device information

    Raises:
        DeviceOfflineError: If device is offline or unauthorized
    """
    info = DeviceInfo(serial=device_serial)

    if verbose:
        console.print(f"[cyan]Analyzing device: {device_serial}[/cyan]")

    # Check device state
    try:
        devices_output = run_adb_command(["devices"])
        for line in devices_output.split("\n"):
            if device_serial in line:
                state = line.split()[1] if len(line.split()) > 1 else "unknown"
                info.state = state
                if state != "device":
                    raise DeviceOfflineError(f"Device {device_serial} is {state}")
                break
    except Exception as e:
        info.errors.append(f"State check failed: {str(e)}")
        raise

    # Detect if emulator
    info.is_emulator = "emulator" in device_serial

    # Get Android version and API level
    try:
        api_level_str = run_adb_command(["shell", "getprop", "ro.build.version.sdk"], device=device_serial)
        info.api_level = int(api_level_str)
        info.android_version = ANDROID_VERSIONS.get(info.api_level, f"API {info.api_level}")
    except Exception as e:
        info.errors.append(f"API level detection failed: {str(e)}")

    # Get device model and manufacturer
    try:
        info.model = run_adb_command(["shell", "getprop", "ro.product.model"], device=device_serial)
        info.manufacturer = run_adb_command(["shell", "getprop", "ro.product.manufacturer"], device=device_serial)
    except Exception as e:
        info.errors.append(f"Model detection failed: {str(e)}")

    # Get screen resolution and density
    try:
        wm_output = run_adb_command(["shell", "wm", "size"], device=device_serial)
        if match := re.search(r"(\d+x\d+)", wm_output):
            info.resolution = match.group(1)

        density_output = run_adb_command(["shell", "wm", "density"], device=device_serial)
        if match := re.search(r"(\d+)", density_output):
            info.density = int(match.group(1))
    except Exception as e:
        info.errors.append(f"Screen info detection failed: {str(e)}")

    # Get RAM information
    try:
        meminfo = run_adb_command(["shell", "cat", "/proc/meminfo"], device=device_serial)
        if match := re.search(r"MemTotal:\s+(\d+)\s+kB", meminfo):
            info.ram_total_mb = int(match.group(1)) // 1024
        if match := re.search(r"MemAvailable:\s+(\d+)\s+kB", meminfo):
            info.ram_available_mb = int(match.group(1)) // 1024
    except Exception as e:
        info.errors.append(f"RAM detection failed: {str(e)}")

    # Get CPU information
    try:
        info.cpu_architecture = run_adb_command(["shell", "getprop", "ro.product.cpu.abi"], device=device_serial)
        cpuinfo = run_adb_command(["shell", "cat", "/proc/cpuinfo"], device=device_serial)
        info.cpu_threads = len(re.findall(r"^processor", cpuinfo, re.MULTILINE))
    except Exception as e:
        info.errors.append(f"CPU detection failed: {str(e)}")

    # Get storage information
    try:
        df_output = run_adb_command(["shell", "df", "/data"], device=device_serial)
        lines = df_output.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 4:
                # Convert KB to GB
                info.storage_total_gb = round(int(parts[1]) / (1024 * 1024), 2)
                info.storage_available_gb = round(int(parts[3]) / (1024 * 1024), 2)
    except Exception as e:
        info.errors.append(f"Storage detection failed: {str(e)}")

    # Get battery information
    try:
        battery_output = run_adb_command(["shell", "dumpsys", "battery"], device=device_serial)
        if match := re.search(r"level:\s+(\d+)", battery_output):
            info.battery_level = int(match.group(1))
        if match := re.search(r"temperature:\s+(\d+)", battery_output):
            info.battery_temperature = round(int(match.group(1)) / 10, 1)
    except Exception as e:
        info.errors.append(f"Battery detection failed: {str(e)}")

    if verbose and info.errors:
        console.print(f"[yellow]Warnings: {len(info.errors)} errors encountered[/yellow]")

    return info


# ============================================================================
# SECTION 8: OUTPUT FORMATTERS
# ============================================================================

def format_table_output(device_info: DeviceInfo) -> None:
    """
    Format device information as rich table.

    Args:
        device_info: Device information to display
    """
    table = Table(title=f"Device Analysis: {device_info.serial}", box=box.ROUNDED)
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Device identity
    table.add_row("Serial", device_info.serial)
    table.add_row("State", device_info.state)
    table.add_row("Type", "Emulator" if device_info.is_emulator else "Physical Device")
    table.add_row("Manufacturer", device_info.manufacturer)
    table.add_row("Model", device_info.model)

    # Software
    table.add_section()
    table.add_row("Android Version", device_info.android_version)
    table.add_row("API Level", str(device_info.api_level))

    # Display
    table.add_section()
    table.add_row("Resolution", device_info.resolution)
    table.add_row("Density", f"{device_info.density} dpi")

    # Hardware
    table.add_section()
    table.add_row("CPU Architecture", device_info.cpu_architecture)
    table.add_row("CPU Threads", str(device_info.cpu_threads))
    table.add_row("RAM Total", f"{device_info.ram_total_mb} MB")
    table.add_row("RAM Available", f"{device_info.ram_available_mb} MB")
    table.add_row("Storage Total", f"{device_info.storage_total_gb} GB")
    table.add_row("Storage Available", f"{device_info.storage_available_gb} GB")

    # Battery
    table.add_section()
    table.add_row("Battery Level", f"{device_info.battery_level}%")
    table.add_row("Battery Temperature", f"{device_info.battery_temperature}°C")

    console.print(table)

    if device_info.errors:
        error_panel = Panel(
            "\n".join(f"• {error}" for error in device_info.errors),
            title="[yellow]Warnings[/yellow]",
            border_style="yellow",
        )
        console.print(error_panel)


# ============================================================================
# SECTION 9: CLI INTERFACE
# ============================================================================

@click.command()
@click.option(
    "--device",
    "-d",
    default=None,
    help="Specific device serial number to analyze (e.g., emulator-5554)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results in JSON format",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output with debug information",
)
def main(device: Optional[str], output_json: bool, verbose: bool) -> None:
    """
    ADB Device Analyzer - Analyze connected device capabilities.

    Analyzes ADB devices and provides comprehensive hardware and software
    information including API level, resolution, RAM, CPU, storage, and battery.

    Examples:
        adb_device_analyzer.py
        adb_device_analyzer.py --device emulator-5554
        adb_device_analyzer.py --json
        adb_device_analyzer.py --verbose
    """
    try:
        # Get target device
        if device:
            target_device = device
        else:
            devices = get_connected_devices()
            target_device = devices[0]
            if verbose:
                console.print(f"[cyan]Auto-selected device: {target_device}[/cyan]")

        # Analyze device
        device_info = analyze_device(target_device, verbose=verbose)

        # Output results
        if output_json:
            print(json.dumps(device_info.to_dict(), indent=2))
        else:
            format_table_output(device_info)

        sys.exit(0)

    except NoDevicesFoundError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)

    except DeviceOfflineError as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(2)

    except Exception as e:
        console.print(f"[red]Unexpected error: {str(e)}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(3)


if __name__ == "__main__":
    main()
