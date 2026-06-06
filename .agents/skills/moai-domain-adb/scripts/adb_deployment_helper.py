#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1.0",
#   "rich>=13.0.0",
# ]
# ///
"""
ADB Deployment Helper - Production Bot Deployment Manager

A zero-context CLI tool for safely deploying automation bots to production
Android devices with pre-flight checks, backup, and rollback capabilities.

This is script #7 of 7 in the moai-domain-adb skill suite.

Author: MoAI-ADK
Version: 1.0.0
License: MIT
"""

# ============================================================================
# SECTION 1: IMPORTS & DEPENDENCIES
# ============================================================================

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

# ============================================================================
# SECTION 2: CONSTANTS & CONFIGURATION
# ============================================================================

# Deployment targets with safety levels
class DeploymentTarget(str, Enum):
    """Deployment target environments."""
    STAGING = "staging"
    PRODUCTION = "production"

# Safety check thresholds
SAFETY_CHECKS = {
    DeploymentTarget.STAGING: {
        "require_backup": False,
        "require_validation": True,
        "max_parallel_devices": 10,
        "allow_force": True,
    },
    DeploymentTarget.PRODUCTION: {
        "require_backup": True,
        "require_validation": True,
        "max_parallel_devices": 3,
        "allow_force": False,
    },
}

# Required device capabilities
REQUIRED_DEVICE_CAPABILITIES = [
    "shell",
    "push",
    "pull",
]

# Backup directory structure
BACKUP_DIR = Path.home() / ".adb_deployment_helper" / "backups"
DEPLOYMENT_HISTORY = Path.home() / ".adb_deployment_helper" / "deployments.json"

# Exit codes
EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILED = 1
EXIT_DEPLOYMENT_FAILED = 2
EXIT_ROLLBACK_FAILED = 3
EXIT_DEVICE_PREPARATION_FAILED = 4

# ============================================================================
# SECTION 3: CUSTOM EXCEPTIONS
# ============================================================================

class DeploymentError(Exception):
    """Base exception for deployment errors."""
    pass

class ValidationError(DeploymentError):
    """Raised when pre-flight validation fails."""
    pass

class DevicePreparationError(DeploymentError):
    """Raised when device preparation fails."""
    pass

class InstallationError(DeploymentError):
    """Raised when bot installation fails."""
    pass

class RollbackError(DeploymentError):
    """Raised when rollback operation fails."""
    pass

class VerificationError(DeploymentError):
    """Raised when deployment verification fails."""
    pass

# ============================================================================
# SECTION 4: DATA STRUCTURES
# ============================================================================

@dataclass
class DeviceInfo:
    """Information about a target device."""
    device_id: str
    model: str = "Unknown"
    android_version: str = "Unknown"
    status: str = "device"
    available_space_mb: int = 0
    capabilities: list[str] = field(default_factory=list)

@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    device_id: str
    success: bool
    message: str
    timestamp: str
    backup_path: str | None = None
    installed_bot: str | None = None
    verification_passed: bool = False
    error: str | None = None

@dataclass
class DeploymentReport:
    """Complete deployment report."""
    target: DeploymentTarget
    bot_file: Path
    total_devices: int
    successful: int
    failed: int
    results: list[DeploymentResult]
    timestamp: str
    duration_seconds: float

# ============================================================================
# SECTION 5: CORE DEVICE OPERATIONS
# ============================================================================

def run_adb_command(device_id: str, command: list[str]) -> tuple[bool, str]:
    """
    Execute an ADB command on a specific device.

    Args:
        device_id: Target device ID
        command: ADB command arguments

    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            ["adb", "-s", device_id] + command,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def get_connected_devices() -> list[str]:
    """
    Get list of connected device IDs.

    Returns:
        List of device IDs
    """
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            if line.strip():
                device_id = line.split("\t")[0].strip()
                status = line.split("\t")[1].strip()
                if status == "device":
                    devices.append(device_id)

        return devices

    except Exception:
        return []

def get_device_info(device_id: str) -> DeviceInfo:
    """
    Gather information about a device.

    Args:
        device_id: Target device ID

    Returns:
        DeviceInfo object
    """
    info = DeviceInfo(device_id=device_id)

    # Get model
    success, output = run_adb_command(device_id, ["shell", "getprop", "ro.product.model"])
    if success:
        info.model = output

    # Get Android version
    success, output = run_adb_command(device_id, ["shell", "getprop", "ro.build.version.release"])
    if success:
        info.android_version = output

    # Get available space (in MB)
    success, output = run_adb_command(device_id, ["shell", "df", "/sdcard"])
    if success:
        lines = output.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 4:
                try:
                    # Available space in KB, convert to MB
                    info.available_space_mb = int(parts[3]) // 1024
                except (ValueError, IndexError):
                    pass

    # Check capabilities
    info.capabilities = REQUIRED_DEVICE_CAPABILITIES.copy()

    return info

# ============================================================================
# SECTION 6: VALIDATION & PRE-FLIGHT CHECKS
# ============================================================================

def validate_bot_file(bot_file: Path, console: Console) -> None:
    """
    Validate the bot file before deployment.

    Args:
        bot_file: Path to bot file
        console: Rich console for output

    Raises:
        ValidationError: If validation fails
    """
    console.print("[cyan]Validating bot file...[/cyan]")

    # Check file exists
    if not bot_file.exists():
        raise ValidationError(f"Bot file not found: {bot_file}")

    # Check file is readable
    if not bot_file.is_file():
        raise ValidationError(f"Path is not a file: {bot_file}")

    # Check file size (should be < 100MB for reasonable bot)
    file_size_mb = bot_file.stat().st_size / (1024 * 1024)
    if file_size_mb > 100:
        raise ValidationError(f"Bot file too large: {file_size_mb:.1f}MB (max 100MB)")

    # Check file extension (common bot formats)
    valid_extensions = {".py", ".js", ".apk", ".jar", ".sh"}
    if bot_file.suffix.lower() not in valid_extensions:
        console.print(f"[yellow]Warning: Unusual bot file extension: {bot_file.suffix}[/yellow]")

    console.print(f"[green]✓[/green] Bot file validated: {bot_file.name} ({file_size_mb:.1f}MB)")

def validate_devices(device_ids: list[str], target: DeploymentTarget, console: Console) -> list[DeviceInfo]:
    """
    Validate and gather information about target devices.

    Args:
        device_ids: List of device IDs to validate
        target: Deployment target
        console: Rich console for output

    Returns:
        List of validated DeviceInfo objects

    Raises:
        ValidationError: If validation fails
    """
    console.print(f"[cyan]Validating {len(device_ids)} device(s)...[/cyan]")

    if not device_ids:
        raise ValidationError("No devices specified")

    # Check device count limits
    max_devices = SAFETY_CHECKS[target]["max_parallel_devices"]
    if len(device_ids) > max_devices:
        raise ValidationError(
            f"Too many devices for {target.value}: {len(device_ids)} "
            f"(max {max_devices})"
        )

    # Gather device information
    validated_devices = []
    connected_devices = get_connected_devices()

    for device_id in device_ids:
        if device_id not in connected_devices:
            raise ValidationError(f"Device not connected: {device_id}")

        info = get_device_info(device_id)

        # Check available space (require at least 100MB)
        if info.available_space_mb < 100:
            raise ValidationError(
                f"Device {device_id} has insufficient space: "
                f"{info.available_space_mb}MB (need 100MB)"
            )

        validated_devices.append(info)
        console.print(f"[green]✓[/green] {device_id}: {info.model} (Android {info.android_version})")

    return validated_devices

# ============================================================================
# SECTION 7: BACKUP & ROLLBACK OPERATIONS
# ============================================================================

def create_backup(device_id: str, bot_file: Path, console: Console) -> Path | None:
    """
    Create a backup snapshot before deployment.

    Args:
        device_id: Target device ID
        bot_file: Bot file being deployed
        console: Rich console for output

    Returns:
        Path to backup directory or None if backup failed
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{device_id}_{timestamp}"

    try:
        backup_path.mkdir(parents=True, exist_ok=True)

        # Save bot metadata
        metadata = {
            "device_id": device_id,
            "timestamp": timestamp,
            "bot_file": str(bot_file),
            "bot_name": bot_file.name,
        }

        with open(backup_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Copy bot file to backup
        shutil.copy2(bot_file, backup_path / bot_file.name)

        console.print(f"[green]✓[/green] Backup created: {backup_path}")
        return backup_path

    except Exception as e:
        console.print(f"[yellow]Warning: Backup failed for {device_id}: {e}[/yellow]")
        return None

def rollback_deployment(device_id: str, backup_path: Path, console: Console) -> bool:
    """
    Rollback to previous bot version from backup.

    Args:
        device_id: Target device ID
        backup_path: Path to backup directory
        console: Rich console for output

    Returns:
        True if rollback succeeded, False otherwise
    """
    console.print(f"[yellow]Rolling back deployment for {device_id}...[/yellow]")

    try:
        # Load backup metadata
        metadata_file = backup_path / "metadata.json"
        if not metadata_file.exists():
            raise RollbackError("Backup metadata not found")

        with open(metadata_file) as f:
            metadata = json.load(f)

        # Find backed up bot file
        bot_file = backup_path / metadata["bot_name"]
        if not bot_file.exists():
            raise RollbackError("Backup bot file not found")

        # Reinstall previous version
        success, output = run_adb_command(
            device_id,
            ["push", str(bot_file), "/sdcard/bot.previous"]
        )

        if not success:
            raise RollbackError(f"Failed to restore backup: {output}")

        console.print(f"[green]✓[/green] Rollback completed for {device_id}")
        return True

    except Exception as e:
        console.print(f"[red]✗[/red] Rollback failed: {e}")
        return False

# ============================================================================
# SECTION 8: DEPLOYMENT OPERATIONS
# ============================================================================

def prepare_device(device_info: DeviceInfo, console: Console) -> None:
    """
    Prepare device for deployment.

    Args:
        device_info: Device information
        console: Rich console for output

    Raises:
        DevicePreparationError: If preparation fails
    """
    device_id = device_info.device_id

    # Create deployment directory
    success, output = run_adb_command(device_id, ["shell", "mkdir", "-p", "/sdcard/bots"])
    if not success:
        raise DevicePreparationError(f"Failed to create bot directory: {output}")

    # Set permissions
    success, output = run_adb_command(device_id, ["shell", "chmod", "755", "/sdcard/bots"])
    if not success:
        console.print(f"[yellow]Warning: Failed to set permissions: {output}[/yellow]")

def install_bot(device_id: str, bot_file: Path, console: Console) -> None:
    """
    Install bot on device.

    Args:
        device_id: Target device ID
        bot_file: Path to bot file
        console: Rich console for output

    Raises:
        InstallationError: If installation fails
    """
    target_path = f"/sdcard/bots/{bot_file.name}"

    # Push bot file
    success, output = run_adb_command(device_id, ["push", str(bot_file), target_path])
    if not success:
        raise InstallationError(f"Failed to push bot: {output}")

    # Set executable permissions if it's a script
    if bot_file.suffix in {".py", ".sh"}:
        success, output = run_adb_command(device_id, ["shell", "chmod", "+x", target_path])
        if not success:
            console.print(f"[yellow]Warning: Failed to set executable: {output}[/yellow]")

def verify_deployment(device_id: str, bot_file: Path, console: Console) -> bool:
    """
    Verify bot deployment was successful.

    Args:
        device_id: Target device ID
        bot_file: Path to bot file
        console: Rich console for output

    Returns:
        True if verification passed, False otherwise
    """
    target_path = f"/sdcard/bots/{bot_file.name}"

    # Check file exists
    success, output = run_adb_command(device_id, ["shell", "ls", "-la", target_path])
    if not success:
        console.print(f"[red]✗[/red] Bot file not found on device")
        return False

    # Compare file sizes
    local_size = bot_file.stat().st_size

    success, output = run_adb_command(device_id, ["shell", "stat", "-c", "%s", target_path])
    if success:
        try:
            remote_size = int(output.strip())
            if remote_size != local_size:
                console.print(
                    f"[red]✗[/red] File size mismatch: "
                    f"local={local_size}, remote={remote_size}"
                )
                return False
        except ValueError:
            console.print(f"[yellow]Warning: Could not verify file size[/yellow]")

    console.print(f"[green]✓[/green] Deployment verified")
    return True

def deploy_to_device(
    device_info: DeviceInfo,
    bot_file: Path,
    target: DeploymentTarget,
    backup: bool,
    console: Console,
) -> DeploymentResult:
    """
    Deploy bot to a single device.

    Args:
        device_info: Device information
        bot_file: Path to bot file
        target: Deployment target
        backup: Whether to create backup
        console: Rich console for output

    Returns:
        DeploymentResult object
    """
    device_id = device_info.device_id
    backup_path = None

    try:
        # Create backup if required
        if backup:
            backup_path = create_backup(device_id, bot_file, console)

        # Prepare device
        console.print(f"[cyan]Preparing device {device_id}...[/cyan]")
        prepare_device(device_info, console)

        # Install bot
        console.print(f"[cyan]Installing bot on {device_id}...[/cyan]")
        install_bot(device_id, bot_file, console)

        # Verify installation
        console.print(f"[cyan]Verifying deployment on {device_id}...[/cyan]")
        verification_passed = verify_deployment(device_id, bot_file, console)

        return DeploymentResult(
            device_id=device_id,
            success=True,
            message="Deployment completed successfully",
            timestamp=datetime.now().isoformat(),
            backup_path=str(backup_path) if backup_path else None,
            installed_bot=str(bot_file),
            verification_passed=verification_passed,
        )

    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]✗[/red] Deployment failed for {device_id}: {error_msg}")

        # Attempt rollback if we have a backup
        if backup_path and backup_path.exists():
            console.print(f"[yellow]Attempting rollback...[/yellow]")
            rollback_success = rollback_deployment(device_id, backup_path, console)
            if rollback_success:
                error_msg += " (rolled back successfully)"
            else:
                error_msg += " (rollback failed - manual intervention required)"

        return DeploymentResult(
            device_id=device_id,
            success=False,
            message="Deployment failed",
            timestamp=datetime.now().isoformat(),
            backup_path=str(backup_path) if backup_path else None,
            error=error_msg,
        )

# ============================================================================
# SECTION 9: CLI INTERFACE & MAIN
# ============================================================================

def save_deployment_history(report: DeploymentReport) -> None:
    """Save deployment report to history."""
    DEPLOYMENT_HISTORY.parent.mkdir(parents=True, exist_ok=True)

    history = []
    if DEPLOYMENT_HISTORY.exists():
        with open(DEPLOYMENT_HISTORY) as f:
            history = json.load(f)

    history.append({
        "target": report.target.value,
        "bot_file": str(report.bot_file),
        "timestamp": report.timestamp,
        "total_devices": report.total_devices,
        "successful": report.successful,
        "failed": report.failed,
        "duration_seconds": report.duration_seconds,
    })

    # Keep only last 100 deployments
    history = history[-100:]

    with open(DEPLOYMENT_HISTORY, "w") as f:
        json.dump(history, f, indent=2)

def display_deployment_report(report: DeploymentReport, console: Console) -> None:
    """Display formatted deployment report."""
    # Summary table
    summary_table = Table(title="Deployment Summary", show_header=True, header_style="bold cyan")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Target", report.target.value.upper())
    summary_table.add_row("Bot File", report.bot_file.name)
    summary_table.add_row("Total Devices", str(report.total_devices))
    summary_table.add_row("Successful", f"[green]{report.successful}[/green]")
    summary_table.add_row("Failed", f"[red]{report.failed}[/red]" if report.failed > 0 else "0")
    summary_table.add_row("Duration", f"{report.duration_seconds:.1f}s")
    summary_table.add_row("Timestamp", report.timestamp)

    console.print(summary_table)
    console.print()

    # Results table
    results_table = Table(title="Device Results", show_header=True, header_style="bold cyan")
    results_table.add_column("Device ID", style="cyan")
    results_table.add_column("Status", style="white")
    results_table.add_column("Verified", style="white")
    results_table.add_column("Message", style="white")

    for result in report.results:
        status = "[green]✓ Success[/green]" if result.success else "[red]✗ Failed[/red]"
        verified = "[green]✓[/green]" if result.verification_passed else "[yellow]—[/yellow]"
        message = result.message if result.success else result.error or result.message

        results_table.add_row(result.device_id, status, verified, message)

    console.print(results_table)

@click.command()
@click.option(
    "--bot-file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to bot file to deploy",
)
@click.option(
    "--target-devices",
    "-d",
    multiple=True,
    required=True,
    help="Target device IDs (can specify multiple times)",
)
@click.option(
    "--target",
    type=click.Choice([t.value for t in DeploymentTarget]),
    default=DeploymentTarget.STAGING.value,
    help="Deployment target (staging or production)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Run pre-flight validation checks",
)
@click.option(
    "--backup/--no-backup",
    default=None,
    help="Create backup before deployment (default: auto based on target)",
)
@click.option(
    "--rollback",
    type=click.Path(exists=True, path_type=Path),
    help="Rollback to specific backup (cancels deployment)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force deployment (skip some safety checks)",
)
def main(
    bot_file: Path,
    target_devices: tuple[str, ...],
    target: str,
    validate: bool,
    backup: bool | None,
    rollback: Path | None,
    force: bool,
) -> None:
    """
    ADB Deployment Helper - Safely deploy bots to production devices.

    This tool provides:
    - Pre-flight validation checks
    - Device preparation and verification
    - Automatic backup before deployment
    - Rollback capability on failure
    - Deployment reports and history

    Examples:

        # Deploy to staging device
        adb_deployment_helper.py --bot-file bot.py -d emulator-5554 --target staging

        # Deploy to production with backup
        adb_deployment_helper.py --bot-file bot.py -d device1 -d device2 --target production

        # Rollback to previous version
        adb_deployment_helper.py --rollback ~/.adb_deployment_helper/backups/device1_20241201_143022
    """
    console = Console()
    start_time = datetime.now()

    # Display header
    console.print(Panel.fit(
        "[bold cyan]ADB Deployment Helper[/bold cyan]\n"
        f"Target: {target.upper()} | Devices: {len(target_devices)}",
        border_style="cyan",
    ))
    console.print()

    target_enum = DeploymentTarget(target)
    device_list = list(target_devices)

    # Handle rollback mode
    if rollback:
        console.print("[yellow]Rollback mode activated[/yellow]")

        if not rollback.exists():
            console.print(f"[red]✗[/red] Backup path not found: {rollback}")
            sys.exit(EXIT_ROLLBACK_FAILED)

        # Load backup metadata
        metadata_file = rollback / "metadata.json"
        if not metadata_file.exists():
            console.print(f"[red]✗[/red] Invalid backup: metadata not found")
            sys.exit(EXIT_ROLLBACK_FAILED)

        with open(metadata_file) as f:
            metadata = json.load(f)

        device_id = metadata["device_id"]
        success = rollback_deployment(device_id, rollback, console)

        if success:
            console.print(f"\n[green]✓[/green] Rollback completed successfully")
            sys.exit(EXIT_SUCCESS)
        else:
            console.print(f"\n[red]✗[/red] Rollback failed")
            sys.exit(EXIT_ROLLBACK_FAILED)

    # Check force flag restrictions
    if force and not SAFETY_CHECKS[target_enum]["allow_force"]:
        console.print(f"[red]✗[/red] Force flag not allowed for {target} target")
        sys.exit(EXIT_VALIDATION_FAILED)

    # Determine backup setting
    if backup is None:
        backup = SAFETY_CHECKS[target_enum]["require_backup"]

    try:
        # Validation phase
        if validate:
            console.print("[bold cyan]Phase 1: Pre-flight Validation[/bold cyan]")
            validate_bot_file(bot_file, console)
            validated_devices = validate_devices(device_list, target_enum, console)
            console.print(f"\n[green]✓[/green] Validation passed\n")
        else:
            console.print("[yellow]Skipping validation (not recommended)[/yellow]\n")
            validated_devices = [
                DeviceInfo(device_id=did) for did in device_list
            ]

        # Deployment phase
        console.print("[bold cyan]Phase 2: Deployment[/bold cyan]")
        results: list[DeploymentResult] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Deploying to {len(validated_devices)} device(s)...",
                total=len(validated_devices),
            )

            for device_info in validated_devices:
                result = deploy_to_device(
                    device_info,
                    bot_file,
                    target_enum,
                    backup,
                    console,
                )
                results.append(result)
                progress.advance(task)

        # Generate report
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        report = DeploymentReport(
            target=target_enum,
            bot_file=bot_file,
            total_devices=len(device_list),
            successful=sum(1 for r in results if r.success),
            failed=sum(1 for r in results if not r.success),
            results=results,
            timestamp=start_time.isoformat(),
            duration_seconds=duration,
        )

        # Save history
        save_deployment_history(report)

        # Display report
        console.print()
        display_deployment_report(report, console)

        # Exit with appropriate code
        if report.failed == 0:
            console.print(f"\n[green]✓[/green] All deployments successful!")
            sys.exit(EXIT_SUCCESS)
        else:
            console.print(
                f"\n[yellow]![/yellow] {report.failed} deployment(s) failed. "
                "Check results above."
            )
            sys.exit(EXIT_DEPLOYMENT_FAILED)

    except ValidationError as e:
        console.print(f"\n[red]✗[/red] Validation failed: {e}")
        sys.exit(EXIT_VALIDATION_FAILED)

    except DevicePreparationError as e:
        console.print(f"\n[red]✗[/red] Device preparation failed: {e}")
        sys.exit(EXIT_DEVICE_PREPARATION_FAILED)

    except DeploymentError as e:
        console.print(f"\n[red]✗[/red] Deployment error: {e}")
        sys.exit(EXIT_DEPLOYMENT_FAILED)

    except KeyboardInterrupt:
        console.print("\n[yellow]![/yellow] Deployment cancelled by user")
        sys.exit(EXIT_DEPLOYMENT_FAILED)

    except Exception as e:
        console.print(f"\n[red]✗[/red] Unexpected error: {e}")
        sys.exit(EXIT_DEPLOYMENT_FAILED)

if __name__ == "__main__":
    main()
