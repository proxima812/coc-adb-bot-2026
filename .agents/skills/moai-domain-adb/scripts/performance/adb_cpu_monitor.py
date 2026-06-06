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
ADB CPU Monitor - Real-time CPU usage monitoring

Purpose:
    Monitor and report CPU usage statistics on connected Android devices.
    Shows per-core load average and overall system CPU usage with statistics.
    Supports continuous monitoring with configurable sampling intervals.

Core Features:
    - Real-time CPU load monitoring
    - Load average tracking (1, 5, 15 minutes)
    - Per-package process filtering
    - Time-series data collection
    - Statistical analysis (min, max, avg, peak)
    - Live updating rich table display
    - TOON/YAML output format support

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/performance/adb_cpu_monitor.py [OPTIONS]

Examples:
    # Single CPU snapshot
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_cpu_monitor.py

    # Monitor for 60 seconds with 2-second intervals
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_cpu_monitor.py --duration 60 --interval 2

    # Monitor specific package
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_cpu_monitor.py --package com.example.app --duration 30

    # Export to TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_cpu_monitor.py --duration 30 --toon

Exit Codes:
    0 - CPU monitoring successful
    2 - Device offline or disconnected
    3 - ADB command execution failed

Dependencies:
    - common.path_utils: Path resolution
    - common.adb_utils: Device management
    - common.cli_utils: CLI decorators and output
    - common.error_handlers: Error handling and exit codes

Author: MoAI-ADK
Version: 1.0.0
"""

import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import click
import yaml
from rich.console import Console
from rich.live import Live
from rich.table import Table

# Common utilities
from common.path_utils import setup_adbautoplayer_path
from common.adb_utils import get_default_device, verify_device_connected
from common.cli_utils import (
    device_option,
    toon_output_option,
    verbose_option,
    print_success,
    print_error,
    print_info,
)
from common.error_handlers import (
    handle_adb_errors,
    ADBError,
    EXIT_SUCCESS,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
)

# Setup path
setup_adbautoplayer_path()

console = Console()


@click.command()
@click.option(
    "--duration",
    "-d",
    default=60,
    type=int,
    help="Monitor duration in seconds (0 = single sample)",
)
@click.option(
    "--interval",
    "-i",
    default=2,
    type=int,
    help="Sample interval in seconds",
)
@click.option(
    "--package",
    "-p",
    default=None,
    type=str,
    help="Filter to specific package (optional)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    device: str,
    duration: int,
    interval: int,
    package: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """
    Monitor CPU usage on Android device with real-time statistics.

    Tracks CPU load average over time with optional package filtering.
    Displays live updating table with color-coded severity levels.

    Parameters
    ----------
    device : str
        Target device serial number
    duration : int
        Monitoring duration in seconds (0 for single sample)
    interval : int
        Time between samples in seconds
    package : Optional[str]
        Filter to specific package name
    toon : bool
        Output in TOON/YAML format
    verbose : bool
        Enable verbose logging

    Returns
    -------
    int
        Exit code (0=success, 2=device offline, 3=adb failed)

    Raises
    ------
    ADBError
        When device communication fails
    """
    # Verify device
    verify_device_connected(device)
    adb_device = get_default_device(device)

    if verbose:
        print_info(f"Monitoring CPU on device: {device}")
        if package:
            print_info(f"Filtering to package: {package}")

    # Get CPU count
    try:
        cpu_count = adb_device.shell("nproc").strip()
        if verbose:
            print_info(f"CPU cores detected: {cpu_count}")
    except Exception as e:
        if verbose:
            print_error(f"Failed to get CPU count: {e}")
        cpu_count = "unknown"

    # Single sample or monitoring
    if duration == 0:
        result = get_cpu_snapshot(adb_device, package, verbose)
    else:
        result = monitor_cpu(adb_device, duration, interval, package, toon, verbose)

    # Output results
    if toon:
        output_toon(result, cpu_count)
    else:
        display_results(result, cpu_count)

    print_success("CPU monitoring completed")
    return EXIT_SUCCESS


def get_cpu_snapshot(
    device, package: Optional[str], verbose: bool
) -> Dict[str, any]:
    """
    Get single CPU usage snapshot.

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    package : Optional[str]
        Optional package filter
    verbose : bool
        Enable verbose output

    Returns
    -------
    Dict[str, any]
        CPU snapshot data with load averages and frequency
    """
    if verbose:
        print_info("Capturing CPU snapshot...")

    result = {
        "timestamp": datetime.now().isoformat(),
        "samples": [],
        "stats": {},
    }

    # Get load average
    try:
        load_output = device.shell("cat /proc/loadavg").strip()
        parts = load_output.split()
        load_1, load_5, load_15 = parts[0:3]

        sample = {
            "timestamp": datetime.now().isoformat(),
            "load_1min": float(load_1),
            "load_5min": float(load_5),
            "load_15min": float(load_15),
        }

        # Get CPU frequency
        try:
            freq = device.shell(
                "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
            ).strip()
            if freq:
                sample["max_freq_mhz"] = int(freq) // 1000
        except Exception:
            sample["max_freq_mhz"] = None

        result["samples"].append(sample)

        if verbose:
            print_info(f"Load: {load_1} (1m), {load_5} (5m), {load_15} (15m)")

    except Exception as e:
        if verbose:
            print_error(f"Failed to get CPU snapshot: {e}")
        raise ADBError(f"Failed to get CPU data: {e}")

    return result


def monitor_cpu(
    device,
    duration: int,
    interval: int,
    package: Optional[str],
    toon: bool,
    verbose: bool,
) -> Dict[str, any]:
    """
    Monitor CPU usage over time with live display.

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    duration : int
        Total monitoring duration in seconds
    interval : int
        Time between samples in seconds
    package : Optional[str]
        Optional package filter
    toon : bool
        TOON output mode (suppresses live display)
    verbose : bool
        Enable verbose output

    Returns
    -------
    Dict[str, any]
        CPU monitoring data with samples and statistics
    """
    if verbose:
        print_info(f"Starting CPU monitoring for {duration} seconds...")

    result = {
        "start_time": datetime.now().isoformat(),
        "duration_seconds": duration,
        "interval_seconds": interval,
        "samples": [],
        "stats": {},
    }

    load_samples = []
    elapsed = 0

    try:
        # Live display mode (non-TOON)
        if not toon:
            with Live(generate_table([]), refresh_per_second=4, console=console) as live:
                while elapsed < duration:
                    sample = capture_cpu_sample(device, package, verbose)
                    if sample:
                        result["samples"].append(sample)
                        load_samples.append(sample["load_1min"])

                        # Update live table
                        live.update(generate_table(result["samples"]))

                    time.sleep(interval)
                    elapsed += interval

        else:
            # TOON mode (no live display)
            while elapsed < duration:
                sample = capture_cpu_sample(device, package, verbose)
                if sample:
                    result["samples"].append(sample)
                    load_samples.append(sample["load_1min"])

                time.sleep(interval)
                elapsed += interval

    except KeyboardInterrupt:
        print_info("Monitoring stopped by user")

    # Calculate statistics
    if load_samples:
        result["stats"] = {
            "min_load": round(min(load_samples), 2),
            "max_load": round(max(load_samples), 2),
            "avg_load": round(sum(load_samples) / len(load_samples), 2),
            "peak_load": round(max(load_samples), 2),
            "sample_count": len(load_samples),
        }

    result["end_time"] = datetime.now().isoformat()

    return result


def capture_cpu_sample(
    device, package: Optional[str], verbose: bool
) -> Optional[Dict[str, any]]:
    """
    Capture single CPU sample.

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    package : Optional[str]
        Optional package filter
    verbose : bool
        Enable verbose output

    Returns
    -------
    Optional[Dict[str, any]]
        CPU sample data or None if failed
    """
    try:
        load_output = device.shell("cat /proc/loadavg").strip()
        parts = load_output.split()

        sample = {
            "timestamp": datetime.now().isoformat(),
            "load_1min": float(parts[0]),
            "load_5min": float(parts[1]),
            "load_15min": float(parts[2]),
        }

        # Package-specific CPU (if requested)
        if package:
            try:
                pid = device.shell(f"pidof {package}").strip()
                if pid:
                    cpu_cmd = f"top -n 1 -p {pid} | tail -1"
                    cpu_output = device.shell(cpu_cmd).strip()
                    if cpu_output:
                        parts = cpu_output.split()
                        if len(parts) >= 9:
                            sample["package_cpu_percent"] = float(parts[8].strip("%"))
            except Exception as e:
                if verbose:
                    print_error(f"Failed to get package CPU: {e}")

        return sample

    except Exception as e:
        if verbose:
            print_error(f"Failed to capture CPU sample: {e}")
        return None


def generate_table(samples: List[Dict[str, any]]) -> Table:
    """
    Generate rich table for live CPU display.

    Parameters
    ----------
    samples : List[Dict[str, any]]
        List of CPU samples

    Returns
    -------
    Table
        Formatted rich table
    """
    table = Table(title="CPU Load Monitoring", show_header=True)
    table.add_column("Time", style="cyan", width=12)
    table.add_column("1 min", style="white", justify="right")
    table.add_column("5 min", style="white", justify="right")
    table.add_column("15 min", style="white", justify="right")
    table.add_column("Status", style="white", justify="center")

    # Show last 10 samples
    for sample in samples[-10:]:
        timestamp = datetime.fromisoformat(sample["timestamp"]).strftime("%H:%M:%S")
        load_1 = sample["load_1min"]

        # Color coding based on load
        if load_1 < 1.0:
            color = "green"
            status = "Normal"
        elif load_1 < 2.0:
            color = "yellow"
            status = "Moderate"
        else:
            color = "red"
            status = "High"

        table.add_row(
            timestamp,
            f"[{color}]{load_1:.2f}[/{color}]",
            f"{sample['load_5min']:.2f}",
            f"{sample['load_15min']:.2f}",
            f"[{color}]{status}[/{color}]",
        )

    return table


def display_results(result: Dict[str, any], cpu_count: str) -> None:
    """
    Display CPU monitoring results in rich format.

    Parameters
    ----------
    result : Dict[str, any]
        CPU monitoring data
    cpu_count : str
        Number of CPU cores
    """
    console.print(f"\n[cyan]CPU Cores:[/cyan] {cpu_count}")

    if result.get("samples"):
        # Summary statistics
        stats = result.get("stats", {})
        if stats:
            console.print("\n[cyan]CPU Load Summary:[/cyan]")
            console.print(f"  Minimum:  {stats.get('min_load', 'N/A')}")
            console.print(f"  Maximum:  {stats.get('max_load', 'N/A')}")
            console.print(f"  Average:  {stats.get('avg_load', 'N/A')}")
            console.print(f"  Peak:     {stats.get('peak_load', 'N/A')}")
            console.print(f"  Samples:  {stats.get('sample_count', 0)}")

        # Latest sample details
        latest = result["samples"][-1]
        table = Table(title="Latest CPU Load", show_header=False)
        table.add_column("Period", style="cyan")
        table.add_column("Load", style="green")

        table.add_row("1 minute", f"{latest['load_1min']:.2f}")
        table.add_row("5 minutes", f"{latest['load_5min']:.2f}")
        table.add_row("15 minutes", f"{latest['load_15min']:.2f}")

        if "max_freq_mhz" in latest and latest["max_freq_mhz"]:
            table.add_row("Max Frequency", f"{latest['max_freq_mhz']} MHz")

        console.print(table)


def output_toon(result: Dict[str, any], cpu_count: str) -> None:
    """
    Output CPU data in TOON/YAML format.

    Parameters
    ----------
    result : Dict[str, any]
        CPU monitoring data
    cpu_count : str
        Number of CPU cores
    """
    toon_data = {
        "status": "success",
        "cpu_cores": cpu_count,
        "monitoring": {
            "start_time": result.get("start_time"),
            "end_time": result.get("end_time"),
            "duration_seconds": result.get("duration_seconds", 0),
            "interval_seconds": result.get("interval_seconds", 0),
        },
        "samples": result.get("samples", []),
        "statistics": result.get("stats", {}),
    }

    print(yaml.dump(toon_data, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    sys.exit(main())
