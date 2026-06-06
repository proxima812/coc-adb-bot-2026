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
ADB Display Info - Get display resolution and orientation

Purpose:
    Retrieve display specifications including resolution, DPI, orientation, and aspect ratio.
    Critical for coordinate calibration, responsive design, and screen automation.
    Supports both physical and override display settings.

Usage:
    uv run "$CLAUDE_PROJECT_DIR"/.claude/skills/moai-domain-adb/scripts/info/adb_display_info.py [OPTIONS]

    Options:
        --device/-d TEXT     Target device serial (default: first available)
        --toon               Output in TOON/YAML format
        --verbose/-v         Show detailed execution logs
        --help               Show this help message

Examples:
    # Get display info for default device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_display_info.py

    # Get display info for specific device
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_display_info.py -d emulator-5554

    # Get display info in TOON format
    $ uv run .claude/skills/moai-domain-adb/scripts/info/adb_display_info.py --toon

Exit Codes:
    0 - Success: Display info retrieved
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


def get_display_properties(device: AdbDeviceWrapper, verbose: bool = False) -> Dict[str, Any]:
    """
    Get display properties including resolution, DPI, and orientation.

    Args:
        device: ADB device wrapper
        verbose: Show detailed logs

    Returns:
        Dictionary containing display properties
    """
    properties = {}

    if verbose:
        print_info("Collecting display properties...")

    # Get resolution from wm size
    try:
        size_output = device.shell("wm size").strip()
        if verbose:
            print_info(f"wm size output: {size_output}")

        # Parse: "Physical size: 1080x1920" or "Override size: 1080x1920"
        resolution_match = re.search(r"(\d+)x(\d+)", size_output)
        if resolution_match:
            width = int(resolution_match.group(1))
            height = int(resolution_match.group(2))
            properties["width"] = width
            properties["height"] = height
            properties["resolution"] = f"{width}x{height}"

            # Calculate aspect ratio
            if height > 0:
                aspect_ratio = width / height
                properties["aspect_ratio"] = f"{aspect_ratio:.2f}:1"
            else:
                properties["aspect_ratio"] = "N/A"

            # Determine orientation
            if width > height:
                properties["orientation"] = "landscape"
            elif height > width:
                properties["orientation"] = "portrait"
            else:
                properties["orientation"] = "square"

            if verbose:
                print_info(f"✓ Resolution: {width}x{height}")
        else:
            if verbose:
                print_error("Failed to parse resolution")
            properties["width"] = "Unknown"
            properties["height"] = "Unknown"
            properties["resolution"] = "Unknown"
            properties["aspect_ratio"] = "N/A"
            properties["orientation"] = "Unknown"
    except Exception as e:
        if verbose:
            print_error(f"Failed to get resolution: {e}")
        properties["width"] = "Unknown"
        properties["height"] = "Unknown"
        properties["resolution"] = "Unknown"
        properties["aspect_ratio"] = "N/A"
        properties["orientation"] = "Unknown"

    # Get DPI from wm density
    try:
        density_output = device.shell("wm density").strip()
        if verbose:
            print_info(f"wm density output: {density_output}")

        # Parse: "Physical density: 420" or "Override density: 420"
        density_match = re.search(r"(\d+)", density_output)
        if density_match:
            properties["dpi"] = density_match.group(1)
            if verbose:
                print_info(f"✓ DPI: {properties['dpi']}")
        else:
            properties["dpi"] = "Unknown"
    except Exception as e:
        if verbose:
            print_error(f"Failed to get DPI: {e}")
        properties["dpi"] = "Unknown"

    # Get refresh rate (optional, may not be available on all devices)
    try:
        refresh_output = device.shell("dumpsys display | grep 'RefreshRate'").strip()
        if refresh_output and verbose:
            print_info(f"Refresh rate info: {refresh_output}")

        # Extract numeric value if available
        refresh_match = re.search(r"(\d+\.?\d*)", refresh_output)
        if refresh_match:
            properties["refresh_rate"] = f"{refresh_match.group(1)} Hz"
        else:
            properties["refresh_rate"] = "Unknown"
    except Exception:
        properties["refresh_rate"] = "Unknown"

    return properties


@click.command()
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(device: str, toon: bool, verbose: bool):
    """Get display resolution and orientation"""

    if verbose:
        print_info("Starting display info retrieval...")

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

    # Get display properties
    properties = get_display_properties(device_wrapper, verbose)

    # Output results
    if toon:
        output_data = {
            "status": "success",
            "device": device_serial,
            "display": properties,
        }
        output_toon(output_data)
    else:
        # Create rich table
        table = create_info_table("Display Information")

        # Add rows
        table.add_row("Resolution", properties["resolution"])
        table.add_row("Width", str(properties["width"]))
        table.add_row("Height", str(properties["height"]))
        table.add_row("DPI", properties["dpi"])
        table.add_row("Aspect Ratio", properties["aspect_ratio"])
        table.add_row("Orientation", properties["orientation"])

        if properties["refresh_rate"] != "Unknown":
            table.add_row("Refresh Rate", properties["refresh_rate"])

        console.print(table)

        print_success("Display info retrieved successfully")

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
