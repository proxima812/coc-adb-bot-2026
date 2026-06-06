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
ADB Memory Monitor - Real-time memory usage monitoring

Purpose:
    Monitor and report memory usage statistics on connected Android devices.
    Shows total, used, available, cached, and buffered memory with trends.
    Supports continuous monitoring with configurable sampling intervals.

Core Features:
    - Real-time memory usage monitoring
    - System-wide and per-package memory tracking
    - Time-series data collection
    - Statistical analysis (min, max, avg, peak)
    - Live updating rich table display
    - Human-readable size formatting
    - TOON/YAML output format support

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/performance/adb_memory_monitor.py [OPTIONS]

Examples:
    # Single memory snapshot
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_memory_monitor.py

    # Monitor for 60 seconds with 2-second intervals
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_memory_monitor.py --duration 60 --interval 2

    # Monitor specific package
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_memory_monitor.py --package com.example.app --duration 30

    # Export to TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_memory_monitor.py --duration 30 --toon

Exit Codes:
    0 - Memory monitoring successful
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
    Monitor memory usage on Android device with real-time statistics.

    Tracks system memory and optionally per-package memory over time.
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
        print_info(f"Monitoring memory on device: {device}")
        if package:
            print_info(f"Filtering to package: {package}")

    # Single sample or monitoring
    if duration == 0:
        result = get_memory_snapshot(adb_device, package, verbose)
    else:
        result = monitor_memory(adb_device, duration, interval, package, toon, verbose)

    # Output results
    if toon:
        output_toon(result)
    else:
        display_results(result)

    print_success("Memory monitoring completed")
    return EXIT_SUCCESS


def format_size(kb: int) -> str:
    """
    Format kilobytes to human-readable size.

    Parameters
    ----------
    kb : int
        Size in kilobytes

    Returns
    -------
    str
        Formatted size string (KB, MB, GB)
    """
    try:
        kb = int(kb)
        if kb < 1024:
            return f"{kb} KB"
        elif kb < 1024 * 1024:
            return f"{kb / 1024:.1f} MB"
        else:
            return f"{kb / (1024 * 1024):.2f} GB"
    except (ValueError, TypeError):
        return "N/A"


def parse_meminfo(meminfo_output: str) -> Dict[str, int]:
    """
    Parse /proc/meminfo output.

    Parameters
    ----------
    meminfo_output : str
        Raw meminfo output

    Returns
    -------
    Dict[str, int]
        Parsed memory values in KB
    """
    memory = {}
    for line in meminfo_output.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            try:
                memory[key.strip()] = int(value.strip().split()[0])
            except (ValueError, IndexError):
                pass
    return memory


def get_memory_snapshot(
    device, package: Optional[str], verbose: bool
) -> Dict[str, any]:
    """
    Get single memory usage snapshot.

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
        Memory snapshot data
    """
    if verbose:
        print_info("Capturing memory snapshot...")

    result = {
        "timestamp": datetime.now().isoformat(),
        "samples": [],
        "stats": {},
    }

    try:
        meminfo = device.shell("cat /proc/meminfo").strip()
        memory = parse_meminfo(meminfo)

        total = memory.get("MemTotal", 0)
        available = memory.get("MemAvailable", 0)
        used = total - available
        cached = memory.get("Cached", 0)
        buffers = memory.get("Buffers", 0)

        sample = {
            "timestamp": datetime.now().isoformat(),
            "total_kb": total,
            "used_kb": used,
            "available_kb": available,
            "cached_kb": cached,
            "buffers_kb": buffers,
            "used_percent": round(100 * used / total, 2) if total else 0,
        }

        # Package-specific memory
        if package:
            pkg_mem = get_package_memory(device, package, verbose)
            if pkg_mem:
                sample["package_memory_kb"] = pkg_mem

        result["samples"].append(sample)

        if verbose:
            print_info(
                f"Memory: {format_size(used)} / {format_size(total)} "
                f"({sample['used_percent']:.1f}%)"
            )

    except Exception as e:
        if verbose:
            print_error(f"Failed to get memory snapshot: {e}")
        raise ADBError(f"Failed to get memory data: {e}")

    return result


def monitor_memory(
    device,
    duration: int,
    interval: int,
    package: Optional[str],
    toon: bool,
    verbose: bool,
) -> Dict[str, any]:
    """
    Monitor memory usage over time with live display.

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
        Memory monitoring data with samples and statistics
    """
    if verbose:
        print_info(f"Starting memory monitoring for {duration} seconds...")

    result = {
        "start_time": datetime.now().isoformat(),
        "duration_seconds": duration,
        "interval_seconds": interval,
        "samples": [],
        "stats": {},
    }

    memory_samples = []
    elapsed = 0

    try:
        # Live display mode (non-TOON)
        if not toon:
            with Live(generate_table([]), refresh_per_second=4, console=console) as live:
                while elapsed < duration:
                    sample = capture_memory_sample(device, package, verbose)
                    if sample:
                        result["samples"].append(sample)
                        memory_samples.append(sample["used_percent"])

                        # Update live table
                        live.update(generate_table(result["samples"]))

                    time.sleep(interval)
                    elapsed += interval

        else:
            # TOON mode (no live display)
            while elapsed < duration:
                sample = capture_memory_sample(device, package, verbose)
                if sample:
                    result["samples"].append(sample)
                    memory_samples.append(sample["used_percent"])

                time.sleep(interval)
                elapsed += interval

    except KeyboardInterrupt:
        print_info("Monitoring stopped by user")

    # Calculate statistics
    if memory_samples:
        result["stats"] = {
            "min_percent": round(min(memory_samples), 2),
            "max_percent": round(max(memory_samples), 2),
            "avg_percent": round(sum(memory_samples) / len(memory_samples), 2),
            "peak_percent": round(max(memory_samples), 2),
            "sample_count": len(memory_samples),
        }

        # MB stats
        if result["samples"]:
            used_mb_samples = [s["used_kb"] / 1024 for s in result["samples"]]
            result["stats"]["min_mb"] = round(min(used_mb_samples), 2)
            result["stats"]["max_mb"] = round(max(used_mb_samples), 2)
            result["stats"]["avg_mb"] = round(sum(used_mb_samples) / len(used_mb_samples), 2)
            result["stats"]["peak_mb"] = round(max(used_mb_samples), 2)

    result["end_time"] = datetime.now().isoformat()

    return result


def capture_memory_sample(
    device, package: Optional[str], verbose: bool
) -> Optional[Dict[str, any]]:
    """
    Capture single memory sample.

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
        Memory sample data or None if failed
    """
    try:
        meminfo = device.shell("cat /proc/meminfo").strip()
        memory = parse_meminfo(meminfo)

        total = memory.get("MemTotal", 1)
        available = memory.get("MemAvailable", 0)
        used = total - available
        cached = memory.get("Cached", 0)
        buffers = memory.get("Buffers", 0)

        sample = {
            "timestamp": datetime.now().isoformat(),
            "total_kb": total,
            "used_kb": used,
            "available_kb": available,
            "cached_kb": cached,
            "buffers_kb": buffers,
            "used_percent": round(100 * used / total, 2) if total else 0,
        }

        # Package-specific memory
        if package:
            pkg_mem = get_package_memory(device, package, verbose)
            if pkg_mem:
                sample["package_memory_kb"] = pkg_mem

        return sample

    except Exception as e:
        if verbose:
            print_error(f"Failed to capture memory sample: {e}")
        return None


def get_package_memory(device, package: str, verbose: bool) -> Optional[int]:
    """
    Get memory usage for specific package.

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    package : str
        Package name
    verbose : bool
        Enable verbose output

    Returns
    -------
    Optional[int]
        Memory usage in KB or None if failed
    """
    try:
        pid = device.shell(f"pidof {package}").strip()
        if pid:
            mem_cmd = f"cat /proc/{pid}/status | grep VmRSS"
            mem_output = device.shell(mem_cmd).strip()
            if mem_output and ":" in mem_output:
                value = mem_output.split(":")[1].strip().split()[0]
                return int(value)
    except Exception as e:
        if verbose:
            print_error(f"Failed to get package memory: {e}")
    return None


def generate_table(samples: List[Dict[str, any]]) -> Table:
    """
    Generate rich table for live memory display.

    Parameters
    ----------
    samples : List[Dict[str, any]]
        List of memory samples

    Returns
    -------
    Table
        Formatted rich table
    """
    table = Table(title="Memory Usage Monitoring", show_header=True)
    table.add_column("Time", style="cyan", width=12)
    table.add_column("Used", style="white", justify="right")
    table.add_column("Available", style="white", justify="right")
    table.add_column("Used %", style="white", justify="right")
    table.add_column("Status", style="white", justify="center")

    # Show last 10 samples
    for sample in samples[-10:]:
        timestamp = datetime.fromisoformat(sample["timestamp"]).strftime("%H:%M:%S")
        used_percent = sample["used_percent"]

        # Color coding based on usage
        if used_percent < 30:
            color = "green"
            status = "Normal"
        elif used_percent < 60:
            color = "yellow"
            status = "Moderate"
        else:
            color = "red"
            status = "High"

        table.add_row(
            timestamp,
            f"[{color}]{format_size(sample['used_kb'])}[/{color}]",
            format_size(sample["available_kb"]),
            f"[{color}]{used_percent:.1f}%[/{color}]",
            f"[{color}]{status}[/{color}]",
        )

    return table


def display_results(result: Dict[str, any]) -> None:
    """
    Display memory monitoring results in rich format.

    Parameters
    ----------
    result : Dict[str, any]
        Memory monitoring data
    """
    if result.get("samples"):
        latest = result["samples"][-1]

        # Current state table
        table = Table(title="System Memory", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Size", style="green")
        table.add_column("Percent", style="yellow")

        total = latest["total_kb"]
        used = latest["used_kb"]
        available = latest["available_kb"]
        used_percent = latest["used_percent"]

        table.add_row("Total", format_size(total), "100%")
        table.add_row("Used", format_size(used), f"{used_percent:.1f}%")
        table.add_row("Available", format_size(available), f"{100 - used_percent:.1f}%")
        table.add_row("Cached", format_size(latest.get("cached_kb", 0)), "")
        table.add_row("Buffers", format_size(latest.get("buffers_kb", 0)), "")

        console.print(table)

        # Package memory
        if "package_memory_kb" in latest:
            console.print(
                f"\n[cyan]Package Memory:[/cyan] {format_size(latest['package_memory_kb'])}"
            )

        # Summary statistics
        stats = result.get("stats", {})
        if stats:
            console.print("\n[cyan]Memory Usage Summary:[/cyan]")
            console.print(f"  Minimum:  {stats.get('min_percent', 'N/A'):.1f}% ({stats.get('min_mb', 'N/A'):.1f} MB)")
            console.print(f"  Maximum:  {stats.get('max_percent', 'N/A'):.1f}% ({stats.get('max_mb', 'N/A'):.1f} MB)")
            console.print(f"  Average:  {stats.get('avg_percent', 'N/A'):.1f}% ({stats.get('avg_mb', 'N/A'):.1f} MB)")
            console.print(f"  Peak:     {stats.get('peak_percent', 'N/A'):.1f}% ({stats.get('peak_mb', 'N/A'):.1f} MB)")
            console.print(f"  Samples:  {stats.get('sample_count', 0)}")


def output_toon(result: Dict[str, any]) -> None:
    """
    Output memory data in TOON/YAML format.

    Parameters
    ----------
    result : Dict[str, any]
        Memory monitoring data
    """
    toon_data = {
        "status": "success",
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
