"""
Click CLI decorators and Rich output formatting utilities.

This module provides standardized CLI decorators and Rich-based output
formatters used across all 29 migrated scripts for consistent UX.
"""

from typing import Any, Dict, List, Optional

import click
import yaml
from rich.console import Console
from rich.table import Table


# Rich console instance for output
console = Console()


# ============================================================================
# Click Decorators
# ============================================================================


def device_option(func):
    """
    Purpose:
        Click decorator providing standardized --device/-d option for all
        scripts. Enables consistent device specification across CLI.

    Parameters:
        func: Function to decorate (Click command function). Type: callable

    Returns:
        Decorated function with device option. Type: callable

    Examples:
        >>> @click.command()
        >>> @device_option
        >>> def my_command(device):
        ...     click.echo(f"Using device: {device}")

    Raises:
        No exceptions during decoration. Click may raise during runtime.

    Notes:
        - Flag: -d, --device
        - Default: None (triggers auto-select in get_default_device)
        - Help: "Device ID (e.g., 127.0.0.1:5555 or emulator-5554)"
        - Type: string
        - Optional: user can omit for auto-select behavior

    Related:
        - toon_output_option: Similar formatting decorator
        - verbose_option: Similar verbose flag decorator
        - get_default_device(): Called to resolve None device_id

    Context:
        Used by 20+ scripts that support device specification. Provides
        standard --device option across all tools for consistency.

    Implementation:
        Uses click.option() to add --device/-d flag with callback.
    """
    return click.option(
        "-d",
        "--device",
        default=None,
        help="Device ID (e.g., 127.0.0.1:5555 or emulator-5554)",
    )(func)


def toon_output_option(func):
    """
    Purpose:
        Click decorator for TOON/YAML output format option. Enables
        structured output in YAML format for script integration and parsing.

    Parameters:
        func: Function to decorate (Click command function). Type: callable

    Returns:
        Decorated function with --toon flag. Type: callable

    Examples:
        >>> @click.command()
        >>> @toon_output_option
        >>> def my_command(toon):
        ...     if toon:
        ...         print_toon_output({"status": "success"})

    Raises:
        No exceptions during decoration. Click may raise during runtime.

    Notes:
        - Flag: --toon
        - Type: boolean (is_flag=True)
        - Default: False (human-readable output)
        - Help: "Output in TOON/YAML format"
        - When True: format output as YAML for parsing

    Related:
        - verbose_option: Similar boolean flag decorator
        - device_option: Similar standardized decorator
        - format_toon_output(): Converts dict to TOON format

    Context:
        Used by 15+ scripts for structured output. Enables script-to-script
        integration and parsing in automation scenarios.

    Implementation:
        Uses click.option() with is_flag=True for boolean toggle.
    """
    return click.option(
        "--toon",
        is_flag=True,
        default=False,
        help="Output in TOON/YAML format",
    )(func)


def verbose_option(func):
    """
    Purpose:
        Click decorator for verbose output flag. Enables detailed logging
        and debug information when requested by user.

    Parameters:
        func: Function to decorate (Click command function). Type: callable

    Returns:
        Decorated function with --verbose flag. Type: callable

    Examples:
        >>> @click.command()
        >>> @verbose_option
        >>> def my_command(verbose):
        ...     if verbose:
        ...         console.print("Debug info...", style="dim")

    Raises:
        No exceptions during decoration. Click may raise during runtime.

    Notes:
        - Flag: -v, --verbose
        - Type: boolean (is_flag=True)
        - Default: False (normal output)
        - Help: "Verbose output"
        - When True: print debug/trace information

    Related:
        - toon_output_option: Similar boolean flag decorator
        - device_option: Similar standardized decorator
        - print_info(): Used for verbose messages

    Context:
        Used by 12+ scripts for optional debugging. Helps developers
        understand script execution flow and troubleshoot issues.

    Implementation:
        Uses click.option() with is_flag=True for boolean toggle.
    """
    return click.option(
        "-v",
        "--verbose",
        is_flag=True,
        default=False,
        help="Verbose output",
    )(func)


# ============================================================================
# Rich Output Formatters
# ============================================================================


def print_success(message: str) -> None:
    """
    Purpose:
        Print success message with green color and checkmark prefix.
        Provides visual feedback for successful operations.

    Parameters:
        message: Message text to display. Type: str

    Returns:
        None. Prints to console.

    Examples:
        >>> print_success("Device connected successfully")
        ✓ Device connected successfully

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Prefix: ✓ (checkmark)
        - Color: Green (success style)
        - Used for operation completions, confirmations

    Related:
        - print_error: Failure messages (red)
        - print_warning: Warning messages (yellow)
        - print_info: Info messages (blue)

    Context:
        Used throughout scripts for user feedback on successful operations.

    Implementation:
        Uses Rich console.print() with green style and checkmark prefix.
    """
    console.print(f"✓ {message}", style="green")


def print_error(message: str) -> None:
    """
    Purpose:
        Print error message with red color and X prefix. Provides visual
        feedback for failures and errors.

    Parameters:
        message: Error message text to display. Type: str

    Returns:
        None. Prints to console.

    Examples:
        >>> print_error("Device offline")
        ✗ Device offline

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Prefix: ✗ (X mark)
        - Color: Red (error style)
        - Used for failures, exceptions, invalid operations

    Related:
        - print_success: Success messages (green)
        - print_warning: Warning messages (yellow)
        - print_info: Info messages (blue)

    Context:
        Used for error reporting and failure notifications throughout scripts.

    Implementation:
        Uses Rich console.print() with red style and X prefix.
    """
    console.print(f"✗ {message}", style="red")


def print_warning(message: str) -> None:
    """
    Purpose:
        Print warning message with yellow color and warning prefix.
        Provides visual feedback for cautions and non-fatal issues.

    Parameters:
        message: Warning message text to display. Type: str

    Returns:
        None. Prints to console.

    Examples:
        >>> print_warning("Device connection unstable")
        ⚠ Device connection unstable

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Prefix: ⚠ (warning sign)
        - Color: Yellow (warning style)
        - Used for potential issues, deprecations, cautions

    Related:
        - print_success: Success messages (green)
        - print_error: Error messages (red)
        - print_info: Info messages (blue)

    Context:
        Used for warnings about device state, deprecated features, etc.

    Implementation:
        Uses Rich console.print() with yellow style and warning prefix.
    """
    console.print(f"⚠ {message}", style="yellow")


def print_info(message: str) -> None:
    """
    Purpose:
        Print info message with blue color and info prefix. Provides
        neutral informational feedback about operations.

    Parameters:
        message: Info message text to display. Type: str

    Returns:
        None. Prints to console.

    Examples:
        >>> print_info("Processing device list")
        ℹ Processing device list

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Prefix: ℹ (info symbol)
        - Color: Blue (info style)
        - Used for status updates, progress, informational messages

    Related:
        - print_success: Success messages (green)
        - print_error: Error messages (red)
        - print_warning: Warning messages (yellow)

    Context:
        Used for status updates and informational messages throughout scripts.

    Implementation:
        Uses Rich console.print() with blue style and info prefix.
    """
    console.print(f"ℹ {message}", style="blue")


def create_info_table(data: Dict[str, str], title: Optional[str] = None) -> Table:
    """
    Purpose:
        Create a Rich table from dictionary data for key-value display.
        Provides formatted output for structured information.

    Parameters:
        data: Dictionary with string keys and values to display in table.
              Type: Dict[str, str]
        title: Optional table title. If None, no title displayed.
               Type: Optional[str]

    Returns:
        Rich Table object configured with data. Type: Table

    Examples:
        >>> data = {"Name": "Device1", "Status": "Online"}
        >>> table = create_info_table(data, title="Device Info")
        >>> console.print(table)

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Two columns: "Key" and "Value"
        - Rows populated from dict items
        - Title optional (centered if provided)
        - Single-row tables supported

    Related:
        - create_list_table: Similar for list display
        - console.print(): Prints table to output

    Context:
        Used for displaying structured information (device details, stats).

    Implementation:
        1. Create Rich Table with title
        2. Add columns: "Key", "Value"
        3. For each dict item, add row
        4. Return configured table
    """
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    for key, value in data.items():
        table.add_row(key, str(value))

    return table


def create_list_table(
    items: List[str], title: Optional[str] = None
) -> Table:
    """
    Purpose:
        Create a Rich table from list data for item display. Provides
        formatted output for lists (devices, packages, etc.).

    Parameters:
        items: List of string items to display in table.
               Type: List[str]
        title: Optional table title. If None, no title displayed.
               Type: Optional[str]

    Returns:
        Rich Table object configured with items. Type: Table

    Examples:
        >>> devices = ["emulator-5554", "127.0.0.1:5555"]
        >>> table = create_list_table(devices, title="Connected Devices")
        >>> console.print(table)

    Raises:
        No exceptions. Errors in Rich are handled internally.

    Notes:
        - Single column: "Item"
        - Each list item becomes one row
        - Title optional (centered if provided)
        - Suitable for device lists, package lists, etc.

    Related:
        - create_info_table: Similar for key-value display
        - console.print(): Prints table to output

    Context:
        Used for displaying lists (devices, packages, running apps).

    Implementation:
        1. Create Rich Table with title
        2. Add single column: "Item"
        3. For each list item, add row
        4. Return configured table
    """
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Item", style="cyan")

    for item in items:
        table.add_row(item)

    return table


def format_toon_output(data: Dict[str, Any]) -> str:
    """
    Purpose:
        Convert dictionary to TOON/YAML format string for structured output.
        Enables script-to-script integration and configuration file generation.

    Parameters:
        data: Dictionary to convert to YAML format.
              Type: Dict[str, Any]

    Returns:
        String in YAML format suitable for file output or piping.
        Type: str

    Examples:
        >>> data = {"devices": ["dev1", "dev2"], "status": "online"}
        >>> output = format_toon_output(data)
        >>> print(output)
        devices:
        - dev1
        - dev2
        status: online

    Raises:
        yaml.YAMLError: If data cannot be serialized to YAML.

    Notes:
        - Uses PyYAML for serialization
        - Handles nested dictionaries and lists
        - Output suitable for config files and parsing
        - Compact representation for automation

    Related:
        - toon_output_option: CLI flag for TOON output
        - yaml module: Used for serialization
        - console.print(): Prints output to console

    Context:
        Used when --toon flag is provided to scripts for structured output.

    Implementation:
        1. Use yaml.dump() to serialize dict
        2. Set default_flow_style=False for readability
        3. Return formatted string
    """
    return yaml.dump(data, default_flow_style=False)


def output_toon(data: Dict[str, Any]) -> None:
    """
    Purpose:
        Print data in TOON/YAML format to stdout.
        Convenience wrapper around format_toon_output() that prints directly.

    Parameters:
        data: Dictionary to output in TOON format. Type: Dict[str, Any]

    Returns:
        None. Prints to stdout.

    Examples:
        >>> data = {"status": "success", "device": "emulator-5554"}
        >>> output_toon(data)
        device: emulator-5554
        status: success

    Raises:
        yaml.YAMLError: If data cannot be serialized to YAML.

    Notes:
        - Prints to stdout (not console.print) for parsing
        - Uses format_toon_output() internally
        - Suitable for pipe/redirect operations
        - No colors or formatting applied

    Related:
        - format_toon_output(): Returns formatted string
        - toon_output_option: CLI flag decorator

    Context:
        Used by all info scripts when --toon flag is provided.

    Implementation:
        1. Format data using format_toon_output()
        2. Print to stdout using print()
    """
    print(format_toon_output(data))
