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
ADB App List - List installed applications on Android device.

Purpose:
    Enumerate installed Android packages on device with filtering options.
    Supports user apps (3rd party), system apps, or all packages. Provides
    case-insensitive filtering and both Rich table output and TOON/YAML
    format for integration scenarios.

Parameters:
    --filter/-f (str, optional): Case-insensitive substring filter for
                                  package names. Matches anywhere in name
    --system/-s (flag, optional): Show only system apps (exclude user apps)
    --device/-d (str, optional): Device ID (e.g., "127.0.0.1:5555"). If not
                                  provided, auto-selects first connected device
    --toon (flag, optional): Output in TOON/YAML format for parsing
    --verbose/-v (flag, optional): Print detailed execution information

Returns:
    Exit code 0 on success with package list in table or TOON format.
    Exit codes:
        0 - List retrieved successfully
        2 - Device offline or not found
        3 - ADB command failed (pm command unavailable)

Examples:
    # List all user apps (default)
    $ uv run adb_app_list.py

    # List all apps including system
    $ uv run adb_app_list.py --system

    # Filter by package name substring
    $ uv run adb_app_list.py --filter afk
    User Apps (127.0.0.1:5555) - Total: 1
    ┌─────────────────┐
    │ Package Name    │
    ├─────────────────┤
    │ com.afk.journey │
    └─────────────────┘

    # TOON output for automation
    $ uv run adb_app_list.py --filter chrome --toon
    status: success
    total_count: 2
    apps:
    - package: com.android.chrome
    - package: com.chrome.beta

    # Verbose output with debug info
    $ uv run adb_app_list.py -v

Raises:
    ADBError: Base exception for all ADB-related failures
        - ADBDeviceOffline: Device not responding to commands
        - ADBCommandFailed: pm list command failed

Notes:
    - Default behavior: Show only user (3rd party) apps
    - Use --system to show system apps instead of user apps
    - Filter is case-insensitive and matches anywhere in package name
    - Package names sorted alphabetically in output
    - Table output uses Rich library for formatting
    - TOON output includes total count and package list
    - Empty results not an error (exit 0 with empty list)

Related:
    - adb_app_start.py: Launch application
    - adb_app_stop.py: Force stop application
    - common/adb_utils.py: parse_package_list() for parsing
    - common/cli_utils.py: Rich table formatting utilities

Context:
    Use this script to discover installed packages for testing, analysis,
    or inventory purposes. Commonly used to verify app installation, find
    package names for automation, or audit device contents.

Implementation:
    1. Resolve device ID (explicit or auto-select)
    2. Verify device is online and responsive
    3. Execute pm list command:
       - User apps: pm list packages -3
       - System apps: pm list packages -s
    4. Parse output using parse_package_list() utility
    5. Apply case-insensitive filter if provided
    6. Sort packages alphabetically
    7. Format as Rich table or TOON based on flag
    8. Return appropriate exit code
"""

import subprocess
from typing import List, Optional

import click
from rich.table import Table

from common.adb_utils import get_default_device, parse_package_list, verify_device_connected
from common.cli_utils import (
    console,
    device_option,
    format_toon_output,
    print_error,
    print_info,
    print_warning,
    toon_output_option,
    verbose_option,
)
from common.error_handlers import (
    EXIT_ADB_COMMAND_FAILED,
    EXIT_DEVICE_OFFLINE,
    EXIT_SUCCESS,
    ADBCommandFailed,
    handle_adb_errors,
)
from common.path_utils import setup_adbautoplayer_path

# Setup path to adbautoplayer package
setup_adbautoplayer_path()


def get_package_list(
    device: str,
    system_apps: bool,
    verbose: bool,
) -> str:
    """
    Execute ADB command to list packages.

    Args:
        device: Device ID to target
        system_apps: If True, list system apps; if False, list user apps
        verbose: Whether to print verbose output

    Returns:
        Raw pm list packages output string

    Raises:
        ADBCommandFailed: If pm command fails
    """
    # Build command
    if system_apps:
        cmd = ["adb", "-s", device, "shell", "pm", "list", "packages", "-s"]
        if verbose:
            print_info("Listing system apps")
    else:
        cmd = ["adb", "-s", device, "shell", "pm", "list", "packages", "-3"]
        if verbose:
            print_info("Listing user (3rd party) apps")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise ADBCommandFailed(" ".join(cmd), error_msg)
    except subprocess.TimeoutExpired:
        raise ADBCommandFailed(
            " ".join(cmd),
            "Command timed out after 30 seconds",
        )


def filter_packages(
    packages: List[str],
    filter_pattern: Optional[str],
    verbose: bool,
) -> List[str]:
    """
    Filter package list by pattern (case-insensitive).

    Args:
        packages: List of package names
        filter_pattern: Optional substring to match (case-insensitive)
        verbose: Whether to print verbose output

    Returns:
        Filtered and sorted list of package names
    """
    if not filter_pattern:
        return sorted(packages)

    # Case-insensitive substring match
    filter_lower = filter_pattern.lower()
    filtered = [pkg for pkg in packages if filter_lower in pkg.lower()]

    if verbose:
        print_info(f"Filter pattern: {filter_pattern}")
        print_info(f"Matched {len(filtered)} of {len(packages)} packages")

    return sorted(filtered)


def create_package_table(
    packages: List[str],
    device_id: str,
    system_apps: bool,
) -> Table:
    """
    Create Rich table for package display.

    Args:
        packages: List of package names to display
        device_id: Device ID for table title
        system_apps: Whether showing system apps

    Returns:
        Rich Table object
    """
    app_type = "System Apps" if system_apps else "User Apps"
    title = f"{app_type} ({device_id}) - Total: {len(packages)}"

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Package Name", style="green")

    for package in packages:
        table.add_row(package)

    return table


@click.command()
@click.option(
    "-f",
    "--filter",
    default=None,
    help="Filter package names (case-insensitive substring)",
    type=str,
)
@click.option(
    "-s",
    "--system",
    is_flag=True,
    default=False,
    help="Show system apps instead of user apps",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    filter: Optional[str],
    system: bool,
    device: Optional[str],
    toon: bool,
    verbose: bool,
) -> int:
    """List installed applications on Android device via ADB."""

    # Resolve device
    try:
        device_id = get_default_device(device)
        if verbose:
            print_info(f"Using device: {device_id}")
    except Exception as e:
        print_error(f"Device discovery failed: {e}")
        return EXIT_DEVICE_OFFLINE

    # Verify device connectivity
    if not verify_device_connected(device_id):
        print_error(f"Device offline: {device_id}")
        return EXIT_DEVICE_OFFLINE

    # Get package list
    try:
        if verbose:
            print_info("Retrieving package list...")

        output = get_package_list(device_id, system, verbose)
        packages = parse_package_list(output)

        if verbose:
            print_info(f"Retrieved {len(packages)} packages")

    except ADBCommandFailed as e:
        print_error(str(e))
        return EXIT_ADB_COMMAND_FAILED

    # Apply filter
    filtered_packages = filter_packages(packages, filter, verbose)

    # Handle empty results
    if not filtered_packages:
        if filter:
            print_warning(f"No packages matching filter: {filter}")
        else:
            print_warning("No packages found")

        # TOON output for empty result
        if toon:
            toon_data = {
                "status": "success",
                "total_count": 0,
                "apps": [],
            }
            print(format_toon_output(toon_data))

        return EXIT_SUCCESS

    # Format output
    if toon:
        toon_data = {
            "status": "success",
            "total_count": len(filtered_packages),
            "apps": [{"package": pkg} for pkg in filtered_packages],
        }
        print(format_toon_output(toon_data))
    else:
        table = create_package_table(filtered_packages, device_id, system)
        console.print(table)

        # Print summary
        if filter:
            console.print(f"\n[dim]Filtered by: {filter}[/dim]")

    return EXIT_SUCCESS


if __name__ == "__main__":
    exit(main())
