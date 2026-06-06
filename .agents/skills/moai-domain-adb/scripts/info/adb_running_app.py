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
ADB Running App - Get currently active application

Purpose:
    Retrieve the currently focused/active application window including package name
    and activity name. Essential for app state verification and automation targeting.
    Supports multiple detection methods with automatic fallback.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/info/adb_running_app.py [OPTIONS]

    Options:
        --device/-d TEXT     Target device serial (default: first available)
        --toon               Output in TOON/YAML format
        --verbose/-v         Show detailed execution logs
        --help               Show this help message

Examples:
    # Get current foreground app for default device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_running_app.py

    # Get current foreground app for specific device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_running_app.py -d emulator-5554

    # Get current foreground app in TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_running_app.py --toon

Exit Codes:
    0 - Success: App info retrieved
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
import re
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


def get_foreground_app(device: AdbDeviceWrapper, verbose: bool = False) -> Dict[str, Any]:
    """
    Get currently active/foreground application.

    Args:
        device: ADB device wrapper
        verbose: Show detailed logs

    Returns:
        Dictionary containing package and activity info
    """
    app_info = {
        "package": "Unknown",
        "activity": "Unknown",
        "detection_method": "none",
    }

    if verbose:
        print_info("Detecting foreground app...")

    # Method 1: dumpsys window (most reliable)
    try:
        if verbose:
            print_info("Trying Method 1: dumpsys window...")

        output = device.shell("dumpsys window windows | grep 'mCurrentFocus'").strip()

        if verbose:
            print_info(f"dumpsys output: {output}")

        if output and "mCurrentFocus" in output:
            # Pattern: mCurrentFocus=Window{... u0 com.package.name/com.package.ActivityName}
            match = re.search(r"([a-zA-Z0-9._]+)/([a-zA-Z0-9._]+)", output)
            if match:
                app_info["package"] = match.group(1).strip()
                app_info["activity"] = match.group(2).strip()
                app_info["detection_method"] = "dumpsys_window"

                if verbose:
                    print_info(f"✓ Method 1 success: {app_info['package']}/{app_info['activity']}")

                return app_info
    except Exception as e:
        if verbose:
            print_error(f"Method 1 failed: {e}")

    # Method 2: dumpsys activity (alternative)
    try:
        if verbose:
            print_info("Trying Method 2: dumpsys activity...")

        output = device.shell("dumpsys activity activities | grep 'mResumedActivity'").strip()

        if verbose:
            print_info(f"activity output: {output}")

        if output and "mResumedActivity" in output:
            # Pattern: mResumedActivity: ActivityRecord{... u0 com.package.name/.ActivityName t123}
            match = re.search(r"([a-zA-Z0-9._]+)/([a-zA-Z0-9._]+)", output)
            if match:
                app_info["package"] = match.group(1).strip()
                activity = match.group(2).strip()

                # If activity starts with dot, prepend package
                if activity.startswith("."):
                    app_info["activity"] = app_info["package"] + activity
                else:
                    app_info["activity"] = activity

                app_info["detection_method"] = "dumpsys_activity"

                if verbose:
                    print_info(f"✓ Method 2 success: {app_info['package']}/{app_info['activity']}")

                return app_info
    except Exception as e:
        if verbose:
            print_error(f"Method 2 failed: {e}")

    # Method 3: Top activity (fallback)
    try:
        if verbose:
            print_info("Trying Method 3: dumpsys activity top...")

        output = device.shell("dumpsys activity top | grep ACTIVITY | head -1").strip()

        if verbose:
            print_info(f"top activity output: {output}")

        if output and "ACTIVITY" in output:
            # Pattern: ACTIVITY com.package.name/.ActivityName ...
            match = re.search(r"ACTIVITY\s+([a-zA-Z0-9._]+)/([a-zA-Z0-9._]+)", output)
            if match:
                app_info["package"] = match.group(1).strip()
                activity = match.group(2).strip()

                # If activity starts with dot, prepend package
                if activity.startswith("."):
                    app_info["activity"] = app_info["package"] + activity
                else:
                    app_info["activity"] = activity

                app_info["detection_method"] = "dumpsys_top"

                if verbose:
                    print_info(f"✓ Method 3 success: {app_info['package']}/{app_info['activity']}")

                return app_info
    except Exception as e:
        if verbose:
            print_error(f"Method 3 failed: {e}")

    if verbose:
        print_error("All detection methods failed")

    return app_info


@click.command()
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, toon: bool, verbose: bool):
    """Get currently active application"""

    if verbose:
        print_info("Starting foreground app detection...")

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

    # Get foreground app
    app_info = get_foreground_app(device_wrapper, verbose)

    # Output results
    if toon:
        output_data = {
            "status": "success" if app_info["package"] != "Unknown" else "unknown",
            "device": device_serial,
            "foreground_app": {
                "package": app_info["package"],
                "activity": app_info["activity"],
                "detection_method": app_info["detection_method"],
            },
        }
        output_toon(output_data)
    else:
        # Create rich table
        table = create_info_table("Currently Active Application")

        # Add rows
        table.add_row("Package", app_info["package"])
        table.add_row("Activity", app_info["activity"])

        if verbose:
            table.add_row("Detection Method", app_info["detection_method"])

        console.print(table)

        if app_info["package"] != "Unknown":
            print_success(f"Foreground app detected: {app_info['package']}")
        else:
            print_error("Could not detect foreground app")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
