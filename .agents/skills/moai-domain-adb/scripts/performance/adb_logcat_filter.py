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
ADB Logcat Filter - Filtered device log monitoring

Purpose:
    Display and filter Android device logs (logcat) by tag, priority, or package.
    Provides color-coded output with priority levels and continuous streaming.
    Essential for debugging, monitoring app behavior, and diagnosing issues.

Core Features:
    - Real-time logcat streaming
    - Filter by tag, priority level, or package
    - Color-coded output by priority (V/D/I/W/E)
    - Line limit and continuous follow modes
    - Log clearing before monitoring
    - Parsed timestamp, priority, tag, message
    - TOON/YAML output format support

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py [OPTIONS]

Examples:
    # Get recent logs (last 50 lines)
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py

    # Filter by specific tag
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py --tag MyApp

    # Filter by priority (show errors only)
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py --priority E

    # Clear logs and stream continuously
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py --clear --follow

    # Combination: tag + priority + lines
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py --tag ActivityManager --priority W --lines 100

    # Export to TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/performance/adb_logcat_filter.py --tag MyApp --toon

Exit Codes:
    0 - Logs retrieved successfully
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
import re
from datetime import datetime
from typing import Dict, List, Optional

import click
import yaml
from rich.console import Console

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

# Priority level mappings
PRIORITY_COLORS = {
    "V": "white",      # VERBOSE - white
    "D": "cyan",       # DEBUG - cyan
    "I": "green",      # INFO - green
    "W": "yellow",     # WARNING - yellow
    "E": "red",        # ERROR - red
    "F": "red bold",   # FATAL - red bold
}

PRIORITY_NAMES = {
    "V": "VERBOSE",
    "D": "DEBUG",
    "I": "INFO",
    "W": "WARNING",
    "E": "ERROR",
    "F": "FATAL",
}


@click.command()
@click.option(
    "--tag",
    "-t",
    default=None,
    type=str,
    help="Filter by log tag (case-insensitive)",
)
@click.option(
    "--priority",
    "-p",
    default="I",
    type=click.Choice(["V", "D", "I", "W", "E", "F"], case_sensitive=False),
    help="Minimum priority level (V=verbose, D=debug, I=info, W=warning, E=error, F=fatal)",
)
@click.option(
    "--lines",
    "-l",
    default=50,
    type=int,
    help="Number of lines to display (if not following)",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Stream logs continuously (Ctrl+C to stop)",
)
@click.option(
    "--clear",
    "-c",
    is_flag=True,
    help="Clear logs before starting",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    device: str,
    tag: Optional[str],
    priority: str,
    lines: int,
    follow: bool,
    clear: bool,
    toon: bool,
    verbose: bool,
) -> int:
    """
    Monitor and filter Android device logs (logcat).

    Displays filtered logcat output with color-coded priorities.
    Supports continuous streaming and multiple filter criteria.

    Parameters
    ----------
    device : str
        Target device serial number
    tag : Optional[str]
        Filter by log tag (case-insensitive)
    priority : str
        Minimum priority level (V/D/I/W/E/F)
    lines : int
        Number of lines to display (if not following)
    follow : bool
        Stream logs continuously
    clear : bool
        Clear logs before starting
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
        print_info(f"Monitoring logcat on device: {device}")
        if tag:
            print_info(f"Filtering by tag: {tag}")
        print_info(f"Minimum priority: {PRIORITY_NAMES.get(priority, priority)}")

    # Clear logs if requested
    if clear:
        if verbose:
            print_info("Clearing device logs...")
        try:
            adb_device.shell("logcat -c")
            print_success("Logs cleared")
        except Exception as e:
            print_error(f"Failed to clear logs: {e}")

    # Capture logs
    try:
        if follow:
            stream_logs(adb_device, tag, priority, toon, verbose)
        else:
            capture_logs(adb_device, tag, priority, lines, toon, verbose)

    except KeyboardInterrupt:
        print_info("Log monitoring stopped by user")

    return EXIT_SUCCESS


def build_logcat_command(
    tag: Optional[str],
    priority: str,
    lines: int,
    follow: bool,
) -> str:
    """
    Build logcat command with filters.

    Parameters
    ----------
    tag : Optional[str]
        Filter by tag
    priority : str
        Minimum priority level
    lines : int
        Number of lines to display
    follow : bool
        Stream continuously

    Returns
    -------
    str
        Complete logcat command
    """
    cmd = "logcat"

    # Dump and exit or continuous
    if not follow:
        cmd += " -d"

    # Priority filter
    if tag:
        # Specific tag with priority
        cmd += f" -s {tag}:{priority}"
    else:
        # All tags with minimum priority
        cmd += f" *:{priority}"

    # Brief format (timestamp priority/tag: message)
    cmd += " -v brief"

    # Line limit (only for non-follow mode)
    if not follow and lines:
        cmd += f" | head -n {lines}"

    return cmd


def parse_log_line(line: str) -> Optional[Dict[str, str]]:
    """
    Parse logcat line into components.

    Expected format: timestamp PID TID PRIORITY/TAG: message
    Example: 12-01 10:30:45.123  1234  1234 I/MyApp: Some message

    Parameters
    ----------
    line : str
        Raw log line

    Returns
    -------
    Optional[Dict[str, str]]
        Parsed log components or None if parse failed
    """
    # Regex pattern for logcat brief format
    # timestamp PID TID PRIORITY/TAG: message
    pattern = r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])/(.*?):\s*(.*)$"

    match = re.match(pattern, line.strip())
    if match:
        timestamp, pid, tid, priority, tag, message = match.groups()
        return {
            "timestamp": timestamp,
            "pid": pid,
            "tid": tid,
            "priority": priority,
            "tag": tag,
            "message": message,
        }

    return None


def format_log_line(log: Dict[str, str], tag_filter: Optional[str]) -> str:
    """
    Format parsed log line with colors.

    Parameters
    ----------
    log : Dict[str, str]
        Parsed log components
    tag_filter : Optional[str]
        Tag filter (for highlighting)

    Returns
    -------
    str
        Formatted log line with rich markup
    """
    priority = log["priority"]
    color = PRIORITY_COLORS.get(priority, "white")

    # Highlight matching tag
    tag_display = log["tag"]
    if tag_filter and tag_filter.lower() in tag_display.lower():
        tag_display = f"[bold]{tag_display}[/bold]"

    return (
        f"[dim]{log['timestamp']}[/dim] "
        f"[{color}]{priority}/{tag_display}[/{color}]: "
        f"{log['message']}"
    )


def capture_logs(
    device,
    tag: Optional[str],
    priority: str,
    lines: int,
    toon: bool,
    verbose: bool,
) -> None:
    """
    Capture and display logs (non-streaming mode).

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    tag : Optional[str]
        Filter by tag
    priority : str
        Minimum priority level
    lines : int
        Number of lines to display
    toon : bool
        TOON output mode
    verbose : bool
        Enable verbose output
    """
    if verbose:
        print_info(f"Capturing last {lines} log lines...")

    cmd = build_logcat_command(tag, priority, lines, follow=False)

    try:
        output = device.shell(cmd)

        logs = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            parsed = parse_log_line(line)
            if parsed:
                # Apply tag filter (case-insensitive)
                if tag and tag.lower() not in parsed["tag"].lower():
                    continue

                logs.append(parsed)

                # Display formatted line (non-TOON)
                if not toon:
                    console.print(format_log_line(parsed, tag))
            elif not toon:
                # Unparseable line (display as-is)
                console.print(line)

        # TOON output
        if toon:
            output_toon(logs, tag, priority, lines)

        if verbose:
            print_info(f"Captured {len(logs)} log entries")

    except Exception as e:
        if verbose:
            print_error(f"Failed to capture logs: {e}")
        raise ADBError(f"Failed to get logcat: {e}")


def stream_logs(
    device,
    tag: Optional[str],
    priority: str,
    toon: bool,
    verbose: bool,
) -> None:
    """
    Stream logs continuously (follow mode).

    Parameters
    ----------
    device : AdbDeviceWrapper
        Connected device instance
    tag : Optional[str]
        Filter by tag
    priority : str
        Minimum priority level
    toon : bool
        TOON output mode
    verbose : bool
        Enable verbose output
    """
    if verbose:
        print_info("Streaming logs continuously (press Ctrl+C to stop)...")

    console.print("[cyan]Streaming logs...[/cyan]\n")

    cmd = build_logcat_command(tag, priority, lines=0, follow=True)

    logs = []

    try:
        # Note: This is simplified - real streaming would need popen
        output = device.shell(cmd)

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            parsed = parse_log_line(line)
            if parsed:
                # Apply tag filter
                if tag and tag.lower() not in parsed["tag"].lower():
                    continue

                logs.append(parsed)

                # Display formatted line (non-TOON)
                if not toon:
                    console.print(format_log_line(parsed, tag))
            elif not toon:
                console.print(line)

    except KeyboardInterrupt:
        # Output TOON on interrupt
        if toon:
            output_toon(logs, tag, priority, len(logs))
        raise

    except Exception as e:
        if verbose:
            print_error(f"Failed to stream logs: {e}")
        raise ADBError(f"Failed to stream logcat: {e}")


def output_toon(
    logs: List[Dict[str, str]],
    tag: Optional[str],
    priority: str,
    line_count: int,
) -> None:
    """
    Output logs in TOON/YAML format.

    Parameters
    ----------
    logs : List[Dict[str, str]]
        Parsed log entries
    tag : Optional[str]
        Tag filter
    priority : str
        Priority level
    line_count : int
        Requested line count
    """
    toon_data = {
        "status": "success",
        "filters": {
            "tag": tag or "all",
            "priority_level": PRIORITY_NAMES.get(priority, priority),
            "line_count": line_count,
        },
        "logs": logs,
        "total_entries": len(logs),
    }

    print(yaml.dump(toon_data, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    sys.exit(main())
