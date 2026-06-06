# Common Utils Quick Reference

**Location**: `.claude/skills/moai-domain-adb/scripts/common/`
**Version**: 1.0.0 (Phase 5)
**Status**: Production Ready

---

## Quick Start

### Installation
```bash
# Add to your script
from common import (
    detect_project_root,
    setup_adbautoplayer_path,
    device_option,
    print_success,
    ADBError,
)

# Call at script start
setup_adbautoplayer_path()
```

### Minimal Script Template
```python
#!/usr/bin/env python3
import click
from common import setup_adbautoplayer_path, device_option, get_default_device

setup_adbautoplayer_path()

@click.command()
@device_option
def main(device):
    device = get_default_device(device)
    click.echo(f"Device: {device}")

if __name__ == "__main__":
    main()
```

---

## Modules Overview

### 1. `path_utils.py` - Path Detection
```python
from common import detect_project_root, setup_adbautoplayer_path

# Get project root from any directory
root = detect_project_root()  # Returns Path object

# Add adbautoplayer to sys.path (call once at script start)
setup_adbautoplayer_path()

# Now imports work from any directory
from adb_auto_player import ...
```

**Key Use**: Enable scripts to run from any directory (scripts/, .claude/, etc.)

---

### 2. `adb_utils.py` - Device Operations
```python
from common import (
    get_default_device,
    list_connected_devices,
    verify_device_connected,
    parse_package_list,
)

# Auto-select device (or use provided)
device = get_default_device()  # Auto-selects first device
device = get_default_device("emulator-5554")  # Use specified

# List all connected devices
devices = list_connected_devices()  # Returns ["device1", "device2"]

# Check if device is online
if verify_device_connected(device):
    print("Device online")

# Parse package output
packages = parse_package_list(pm_output)  # Returns ["com.app1", "com.app2"]
```

**Key Use**: Common device operations in 26/29 scripts

---

### 3. `cli_utils.py` - CLI & Output
```python
from common import (
    device_option,
    toon_output_option,
    verbose_option,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_info_table,
    create_list_table,
    format_toon_output,
)
from rich.console import console

# Add to command
@click.command()
@device_option  # Adds --device/-d
@toon_output_option  # Adds --toon
@verbose_option  # Adds --verbose/-v
def my_command(device, toon, verbose):
    pass

# Output messages
print_success("Operation complete")  # Green ✓
print_error("Device offline")  # Red ✗
print_warning("Low battery")  # Yellow ⚠
print_info("Processing...")  # Blue ℹ

# Output tables
info = {"Name": "Device", "Status": "Online"}
table = create_info_table(info, title="Info")
console.print(table)

items = ["item1", "item2"]
table = create_list_table(items, title="List")
console.print(table)

# Output YAML
data = {"devices": ["dev1", "dev2"]}
yaml_str = format_toon_output(data)
print(yaml_str)
```

**Key Use**: Consistent CLI options and output formatting

---

### 4. `error_handlers.py` - Error Handling
```python
from common import (
    ADBError,
    ADBDeviceNotFound,
    ADBCommandFailed,
    EXIT_SUCCESS,
    EXIT_GENERIC_ERROR,
    EXIT_DEVICE_OFFLINE,
    EXIT_ADB_COMMAND_FAILED,
    EXIT_INVALID_ARGUMENT,
)

# Exit codes for sys.exit()
sys.exit(EXIT_SUCCESS)  # 0
sys.exit(EXIT_DEVICE_OFFLINE)  # 2
sys.exit(EXIT_ADB_COMMAND_FAILED)  # 3

# Handle errors
try:
    devices = list_connected_devices()
except ADBCommandFailed as e:
    print(e.message)
    sys.exit(e.exit_code)
except ADBDeviceNotFound as e:
    print(e.message)
    sys.exit(e.exit_code)

# Optional: Use decorator for automatic handling
@handle_adb_errors
def my_command():
    raise ADBDeviceNotFound("emulator")  # Caught and handled
```

**Key Use**: Consistent error handling with proper exit codes

---

## Common Patterns

### Pattern 1: Auto-Select Device
```python
from common import get_default_device, verify_device_connected

device = get_default_device(device_arg)  # None → auto-select
if not verify_device_connected(device):
    print("Device offline")
    sys.exit(2)
```

### Pattern 2: Structured Output
```python
from common import toon_output_option, format_toon_output, create_info_table
from rich.console import console

@click.command()
@toon_output_option
def my_cmd(toon):
    data = {"status": "ok", "count": 5}

    if toon:
        print(format_toon_output(data))
    else:
        table = create_info_table(data)
        console.print(table)
```

### Pattern 3: Error Handling
```python
from common import ADBError, print_error, EXIT_ADB_COMMAND_FAILED

try:
    result = some_adb_operation()
except ADBError as e:
    print_error(e.message)
    sys.exit(e.exit_code)
```

### Pattern 4: Verbose Logging
```python
from common import verbose_option, print_info

@click.command()
@verbose_option
def my_cmd(verbose):
    if verbose:
        print_info("Starting operation...")

    do_work()

    if verbose:
        print_info("Operation complete")
```

---

## API Reference

### `path_utils`
- `detect_project_root(start_path=None) -> Path` - Find project root
- `setup_adbautoplayer_path() -> None` - Add adbautoplayer to sys.path

### `adb_utils`
- `get_default_device(device_id=None) -> str` - Get/select device
- `list_connected_devices() -> List[str]` - List all devices
- `verify_device_connected(device_id) -> bool` - Check if online
- `parse_package_list(output) -> List[str]` - Parse pm output

### `cli_utils`
- `@device_option` - Add --device/-d flag
- `@toon_output_option` - Add --toon flag
- `@verbose_option` - Add --verbose/-v flag
- `print_success(msg)` - Green success message
- `print_error(msg)` - Red error message
- `print_warning(msg)` - Yellow warning message
- `print_info(msg)` - Blue info message
- `create_info_table(data, title=None) -> Table` - Dict → table
- `create_list_table(items, title=None) -> Table` - List → table
- `format_toon_output(data) -> str` - Dict → YAML

### `error_handlers`
- `ADBError(message, exit_code=1)` - Base error
- `ADBDeviceNotFound(device_id)` - Device error (exit 2)
- `ADBCommandFailed(command, error)` - Command error (exit 3)
- `@handle_adb_errors` - Catch ADBError decorator
- Exit codes: `EXIT_SUCCESS`, `EXIT_GENERIC_ERROR`, `EXIT_DEVICE_OFFLINE`, `EXIT_ADB_COMMAND_FAILED`, `EXIT_INVALID_ARGUMENT`

---

## Testing

### Verify Installation
```bash
# Test imports
python3 -c "from common import detect_project_root; print(detect_project_root())"

# Test path setup
python3 -c "from common import setup_adbautoplayer_path; setup_adbautoplayer_path()"
```

### Test Device Operations
```bash
# List devices
python3 -c "from common import list_connected_devices; print(list_connected_devices())"

# Check device
python3 -c "from common import verify_device_connected; print(verify_device_connected('emulator-5554'))"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'common'` | Add `sys.path.insert(0, '.claude/skills/moai-domain-adb/scripts')` or run `setup_adbautoplayer_path()` |
| `ModuleNotFoundError: No module named 'click'` | Install: `pip install click` |
| `ModuleNotFoundError: No module named 'rich'` | Install: `pip install rich` |
| `ModuleNotFoundError: No module named 'yaml'` | Install: `pip install PyYAML` |
| Device error but device visible in `adb devices` | Use `verify_device_connected()` to debug |
| Script runs from one dir but not another | Ensure `setup_adbautoplayer_path()` called at script start |

---

## Best Practices

1. **Always call `setup_adbautoplayer_path()` early** in script execution
2. **Use `get_default_device()` instead of manual parsing** for device handling
3. **Always use decorators** for consistent CLI interface
4. **Always catch `ADBError` exceptions** with proper error messages
5. **Use structured output** (tables/YAML) for parsing integration
6. **Use verbose flag** for debugging without log files

---

## Phase 5 Status

- [x] All 4 modules created
- [x] All functions documented
- [x] All type hints present
- [x] All error handling complete
- [x] Syntax verified
- [x] Quick reference provided
- [x] Ready for Phase 6.1 (Script Migration)

---

**Last Updated**: 2025-12-01
**Next Phase**: Phase 6.1 (Script Migration)
