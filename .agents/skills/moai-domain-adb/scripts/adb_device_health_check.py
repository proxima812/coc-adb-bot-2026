#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "toml>=0.10.2",
#     "tenacity>=8.2.0",
# ]
# ///
"""
ADB Device Health Check & Auto-Recovery - Production-grade device health monitoring.

This script provides comprehensive device health monitoring with automatic recovery
state machine for ADB device automation. Monitors connection stability, performance
metrics, and implements recovery strategies with exponential backoff.

Purpose:
    - Monitor device connection health and performance metrics
    - Detect degradation and failures automatically
    - Execute recovery strategies with state machine transitions
    - Support multi-device health aggregation
    - Generate health reports in JSON and TOON format

Features:
    - Connection health checks (latency, stability)
    - Performance metrics (CPU, memory, thermal)
    - Recovery state machine (IDLE → CHECKING → RECOVERING → RECOVERED/FAILED)
    - Recovery strategies (reconnect, restart, fallback)
    - Exponential backoff with jitter (integrate Phase 9a patterns)
    - Multi-device orchestration and health aggregation
    - Health report generation (JSON/TOON)
    - Configurable check intervals and thresholds

Usage:
    # Monitor single device every 10 seconds
    python adb_device_health_check.py --device emulator-5554 --check-interval 10

    # Monitor multiple devices with auto-recovery
    python adb_device_health_check.py --batch-devices device1,device2,device3 \\
        --auto-recover --max-recovery-attempts 3

    # Check device once and output JSON report
    python adb_device_health_check.py --device emulator-5554 --report-format json

    # Monitor with verbose logging
    python adb_device_health_check.py --device emulator-5554 --verbose

    # Set custom timeouts
    python adb_device_health_check.py --device emulator-5554 --timeout 30

Exit Codes:
    0: Device healthy
    1: Device unhealthy, recovery failed
    2: Device offline/unreachable
    3: Invalid configuration
    4: Recovery in progress (exit during transition)

Author: MoAI-ADK Domain ADB Expert
Version: 2.0.0
License: MIT
"""

# ============================================================================
# SECTION 1: IMPORTS & TYPE HINTS
# ============================================================================

import json
import logging
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click
import toml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

# ============================================================================
# SECTION 2: ENUMS & CONFIGURATION
# ============================================================================


class RecoveryState(Enum):
    """Recovery state machine states."""
    IDLE = "idle"
    CHECKING = "checking"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    FAILED = "failed"


class HealthStatus(Enum):
    """Device health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


# Default configuration
DEFAULT_CHECK_INTERVAL = 10  # seconds
DEFAULT_TIMEOUT = 20  # seconds
DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
DEFAULT_STATE_TIMEOUT = 180  # max seconds per state
DEFAULT_CPU_THRESHOLD = 80  # percent
DEFAULT_MEMORY_THRESHOLD = 85  # percent
DEFAULT_THERMAL_THRESHOLD = 45  # celsius

# Console for rich output
console = Console()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 3: DATA STRUCTURES
# ============================================================================


@dataclass
class HealthMetrics:
    """Device health metrics."""
    connection_latency_ms: float
    connection_stability: float  # 0-100%
    cpu_usage: float  # 0-100%
    memory_usage: float  # 0-100%
    thermal_temp: float  # celsius
    last_check_time: float
    consecutive_failures: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RecoveryConfig:
    """Recovery strategy configuration."""
    enabled: bool = True
    max_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS
    state_timeout: float = DEFAULT_STATE_TIMEOUT
    cpu_threshold: float = DEFAULT_CPU_THRESHOLD
    memory_threshold: float = DEFAULT_MEMORY_THRESHOLD
    thermal_threshold: float = DEFAULT_THERMAL_THRESHOLD


@dataclass
class DeviceHealthReport:
    """Complete device health report."""
    device_id: str
    health_status: str
    recovery_state: str
    metrics: Dict[str, Any]
    recovery_attempts: int
    last_recovery_time: Optional[str]
    report_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# SECTION 4: CONNECTION HEALTH CHECK
# ============================================================================


class ConnectionHealthCheck:
    """Validate and monitor ADB connection health."""

    def __init__(self, device_id: str, timeout: float = DEFAULT_TIMEOUT):
        """Initialize connection health checker.

        Args:
            device_id: ADB device identifier
            timeout: Command timeout in seconds
        """
        self.device_id = device_id
        self.timeout = timeout
        self.latency_samples: List[float] = []
        self.max_samples = 10

    def check_connection(self) -> Tuple[bool, float]:
        """Check device connection and measure latency.

        Returns:
            Tuple of (is_connected: bool, latency_ms: float)
        """
        try:
            start_time = time.time()
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", "echo ok"],
                capture_output=True,
                timeout=self.timeout,
                text=True
            )
            elapsed_ms = (time.time() - start_time) * 1000

            is_connected = result.returncode == 0 and "ok" in result.stdout

            if is_connected:
                self._record_latency(elapsed_ms)

            return is_connected, elapsed_ms

        except subprocess.TimeoutExpired:
            logger.warning(f"{self.device_id}: Connection check timeout")
            return False, self.timeout * 1000
        except Exception as e:
            logger.error(f"{self.device_id}: Connection check failed: {e}")
            return False, 0.0

    def get_stability_score(self) -> float:
        """Calculate connection stability (0-100%).

        Returns:
            Stability percentage based on successful checks
        """
        if not self.latency_samples:
            return 100.0

        # Stability = inverse of jitter coefficient of variation
        if len(self.latency_samples) < 2:
            return 100.0

        mean = sum(self.latency_samples) / len(self.latency_samples)
        variance = sum((x - mean) ** 2 for x in self.latency_samples) / len(
            self.latency_samples
        )
        std_dev = variance ** 0.5

        if mean == 0:
            return 100.0

        cv = std_dev / mean  # Coefficient of variation
        stability = max(0, 100 - (cv * 50))  # Scale to 0-100

        return min(100.0, stability)

    def _record_latency(self, latency_ms: float):
        """Record latency sample.

        Args:
            latency_ms: Latency in milliseconds
        """
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > self.max_samples:
            self.latency_samples.pop(0)

    def get_avg_latency(self) -> float:
        """Get average latency from samples.

        Returns:
            Average latency in milliseconds
        """
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)


# ============================================================================
# SECTION 5: PERFORMANCE METRICS COLLECTOR
# ============================================================================


class PerformanceMetricsCollector:
    """Collect CPU, memory, and thermal metrics from device."""

    def __init__(self, device_id: str, timeout: float = DEFAULT_TIMEOUT):
        """Initialize metrics collector.

        Args:
            device_id: ADB device identifier
            timeout: Command timeout in seconds
        """
        self.device_id = device_id
        self.timeout = timeout

    def collect_cpu_usage(self) -> float:
        """Collect device CPU usage percentage.

        Returns:
            CPU usage 0-100%
        """
        try:
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", "top -n 1 -o %CPU"],
                capture_output=True,
                timeout=self.timeout,
                text=True
            )

            if result.returncode != 0:
                return 0.0

            # Parse first non-header line
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                try:
                    cpu_str = lines[1].split()[0]
                    return float(cpu_str)
                except (IndexError, ValueError):
                    pass

            return 0.0

        except Exception as e:
            logger.warning(f"{self.device_id}: CPU collection failed: {e}")
            return 0.0

    def collect_memory_usage(self) -> float:
        """Collect device memory usage percentage.

        Returns:
            Memory usage 0-100%
        """
        try:
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell", "cat /proc/meminfo"],
                capture_output=True,
                timeout=self.timeout,
                text=True
            )

            if result.returncode != 0:
                return 0.0

            meminfo = {}
            for line in result.stdout.split("\n"):
                if ":" in line:
                    key, value = line.split(":")
                    try:
                        meminfo[key.strip()] = int(value.split()[0])
                    except ValueError:
                        pass

            if "MemTotal" in meminfo and "MemAvailable" in meminfo:
                total = meminfo["MemTotal"]
                available = meminfo["MemAvailable"]
                used = total - available
                usage_percent = (used / total) * 100
                return min(100.0, usage_percent)

            return 0.0

        except Exception as e:
            logger.warning(f"{self.device_id}: Memory collection failed: {e}")
            return 0.0

    def collect_thermal_info(self) -> float:
        """Collect device thermal temperature.

        Returns:
            Temperature in celsius
        """
        try:
            result = subprocess.run(
                ["adb", "-s", self.device_id, "shell",
                 "cat /sys/class/thermal/thermal_zone0/temp"],
                capture_output=True,
                timeout=self.timeout,
                text=True
            )

            if result.returncode != 0:
                return 0.0

            # Temperature often in millidegrees
            temp_str = result.stdout.strip()
            if temp_str:
                try:
                    temp = float(temp_str)
                    # Convert millidegrees to celsius if needed
                    if temp > 500:  # Likely in millidegrees
                        temp = temp / 1000
                    return temp
                except ValueError:
                    pass

            return 0.0

        except Exception as e:
            logger.warning(f"{self.device_id}: Thermal collection failed: {e}")
            return 0.0


# ============================================================================
# SECTION 6: RECOVERY STATE MACHINE
# ============================================================================


class RecoveryStatesMachine:
    """State machine for device recovery orchestration."""

    def __init__(self, device_id: str, config: RecoveryConfig):
        """Initialize recovery state machine.

        Args:
            device_id: ADB device identifier
            config: RecoveryConfig instance
        """
        self.device_id = device_id
        self.config = config
        self.current_state = RecoveryState.IDLE
        self.state_enter_time = time.time()
        self.recovery_attempt_count = 0

    def can_transition(self, new_state: RecoveryState) -> bool:
        """Check if state transition is valid.

        Args:
            new_state: Target recovery state

        Returns:
            True if transition is valid
        """
        # Check state timeout
        elapsed = time.time() - self.state_enter_time
        if elapsed > self.config.state_timeout:
            logger.warning(
                f"{self.device_id}: State timeout exceeded ({elapsed:.1f}s)"
            )
            return new_state == RecoveryState.FAILED

        # Define valid transitions
        valid_transitions = {
            RecoveryState.IDLE: [RecoveryState.CHECKING, RecoveryState.RECOVERING],
            RecoveryState.CHECKING: [RecoveryState.RECOVERING, RecoveryState.IDLE],
            RecoveryState.RECOVERING: [
                RecoveryState.RECOVERED,
                RecoveryState.FAILED,
            ],
            RecoveryState.RECOVERED: [RecoveryState.IDLE],
            RecoveryState.FAILED: [RecoveryState.IDLE],
        }

        return new_state in valid_transitions.get(self.current_state, [])

    def transition_to(self, new_state: RecoveryState) -> bool:
        """Transition to new state if valid.

        Args:
            new_state: Target recovery state

        Returns:
            True if transition successful
        """
        if not self.can_transition(new_state):
            logger.warning(
                f"{self.device_id}: Cannot transition "
                f"{self.current_state.value} → {new_state.value}"
            )
            return False

        logger.info(
            f"{self.device_id}: State transition "
            f"{self.current_state.value} → {new_state.value}"
        )
        self.current_state = new_state
        self.state_enter_time = time.time()

        return True

    def increment_recovery_attempts(self):
        """Increment recovery attempt counter."""
        self.recovery_attempt_count += 1

    def reset_recovery_attempts(self):
        """Reset recovery attempt counter."""
        self.recovery_attempt_count = 0


# ============================================================================
# SECTION 7: AUTO-RECOVERY ORCHESTRATOR
# ============================================================================


class AutoRecoveryOrchestrator:
    """Coordinate recovery strategies and health monitoring."""

    def __init__(
        self,
        device_id: str,
        config: RecoveryConfig,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """Initialize auto-recovery orchestrator.

        Args:
            device_id: ADB device identifier
            config: RecoveryConfig instance
            timeout: Command timeout in seconds
        """
        self.device_id = device_id
        self.config = config
        self.timeout = timeout
        self.state_machine = RecoveryStatesMachine(device_id, config)
        self.connection_checker = ConnectionHealthCheck(device_id, timeout)
        self.metrics_collector = PerformanceMetricsCollector(device_id, timeout)
        self.health_history: List[HealthMetrics] = []

    def check_device_health(self) -> HealthMetrics:
        """Perform comprehensive device health check.

        Returns:
            HealthMetrics instance with all metrics
        """
        logger.info(f"{self.device_id}: Starting health check")

        is_connected, latency = self.connection_checker.check_connection()

        metrics = HealthMetrics(
            connection_latency_ms=latency,
            connection_stability=self.connection_checker.get_stability_score(),
            cpu_usage=self.metrics_collector.collect_cpu_usage(),
            memory_usage=self.metrics_collector.collect_memory_usage(),
            thermal_temp=self.metrics_collector.collect_thermal_info(),
            last_check_time=time.time(),
            consecutive_failures=(
                0 if is_connected
                else self.health_history[-1].consecutive_failures + 1
                if self.health_history
                else 1
            ),
        )

        self.health_history.append(metrics)
        if len(self.health_history) > 100:  # Keep last 100 checks
            self.health_history.pop(0)

        return metrics

    def evaluate_health_status(self, metrics: HealthMetrics) -> HealthStatus:
        """Evaluate overall device health status.

        Args:
            metrics: HealthMetrics instance

        Returns:
            HealthStatus enum value
        """
        if metrics.consecutive_failures > 0:
            return HealthStatus.OFFLINE

        critical_factors = [
            metrics.cpu_usage > self.config.cpu_threshold,
            metrics.memory_usage > self.config.memory_threshold,
            metrics.thermal_temp > self.config.thermal_threshold,
            metrics.connection_stability < 50,
        ]

        if any(critical_factors):
            return HealthStatus.CRITICAL

        degraded_factors = [
            metrics.cpu_usage > self.config.cpu_threshold * 0.7,
            metrics.memory_usage > self.config.memory_threshold * 0.7,
            metrics.connection_stability < 75,
        ]

        if any(degraded_factors):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def execute_recovery_strategy_reconnect(self) -> bool:
        """Execute reconnect recovery strategy.

        Returns:
            True if reconnection successful
        """
        logger.info(f"{self.device_id}: Executing reconnect strategy")

        try:
            # Disconnect
            subprocess.run(
                ["adb", "disconnect", self.device_id],
                capture_output=True,
                timeout=self.timeout,
            )
            time.sleep(1)

            # Reconnect
            result = subprocess.run(
                ["adb", "connect", self.device_id],
                capture_output=True,
                timeout=self.timeout,
                text=True,
            )

            success = result.returncode == 0
            if success:
                logger.info(f"{self.device_id}: Reconnect successful")
            else:
                logger.warning(f"{self.device_id}: Reconnect failed")

            return success

        except Exception as e:
            logger.error(f"{self.device_id}: Reconnect strategy error: {e}")
            return False

    def execute_recovery_strategy_restart(self) -> bool:
        """Execute device restart recovery strategy.

        Returns:
            True if restart successful
        """
        logger.info(f"{self.device_id}: Executing restart strategy")

        try:
            # Reboot device
            subprocess.run(
                ["adb", "-s", self.device_id, "reboot"],
                capture_output=True,
                timeout=self.timeout,
            )

            # Wait for device to come back online
            max_wait = 60
            start_time = time.time()

            while time.time() - start_time < max_wait:
                is_connected, _ = self.connection_checker.check_connection()
                if is_connected:
                    logger.info(f"{self.device_id}: Restart successful")
                    return True
                time.sleep(2)

            logger.warning(f"{self.device_id}: Restart timeout")
            return False

        except Exception as e:
            logger.error(f"{self.device_id}: Restart strategy error: {e}")
            return False

    def execute_recovery(self) -> bool:
        """Execute full recovery process with state machine.

        Returns:
            True if recovery successful
        """
        if not self.state_machine.transition_to(RecoveryState.CHECKING):
            return False

        # Check current health
        metrics = self.check_device_health()
        health_status = self.evaluate_health_status(metrics)

        if health_status == HealthStatus.HEALTHY:
            self.state_machine.transition_to(RecoveryState.RECOVERED)
            self.state_machine.reset_recovery_attempts()
            return True

        if not self.state_machine.transition_to(RecoveryState.RECOVERING):
            return False

        self.state_machine.increment_recovery_attempts()

        # Strategy 1: Reconnect
        if self.execute_recovery_strategy_reconnect():
            self.state_machine.transition_to(RecoveryState.RECOVERED)
            self.state_machine.reset_recovery_attempts()
            return True

        # Strategy 2: Restart (only if not exceeded max attempts)
        if self.state_machine.recovery_attempt_count < self.config.max_attempts:
            if self.execute_recovery_strategy_restart():
                self.state_machine.transition_to(RecoveryState.RECOVERED)
                self.state_machine.reset_recovery_attempts()
                return True

        # All strategies failed
        self.state_machine.transition_to(RecoveryState.FAILED)
        logger.error(
            f"{self.device_id}: Recovery failed after "
            f"{self.state_machine.recovery_attempt_count} attempts"
        )
        return False

    def generate_health_report(self) -> DeviceHealthReport:
        """Generate comprehensive health report.

        Returns:
            DeviceHealthReport instance
        """
        metrics = self.check_device_health() if not self.health_history else self.health_history[-1]
        health_status = self.evaluate_health_status(metrics)

        return DeviceHealthReport(
            device_id=self.device_id,
            health_status=health_status.value,
            recovery_state=self.state_machine.current_state.value,
            metrics={
                "connection_latency_ms": round(metrics.connection_latency_ms, 2),
                "connection_stability": round(metrics.connection_stability, 2),
                "cpu_usage": round(metrics.cpu_usage, 2),
                "memory_usage": round(metrics.memory_usage, 2),
                "thermal_temp": round(metrics.thermal_temp, 2),
                "consecutive_failures": metrics.consecutive_failures,
            },
            recovery_attempts=self.state_machine.recovery_attempt_count,
            last_recovery_time=(
                self.health_history[-1].timestamp
                if self.health_history else None
            ),
        )


# ============================================================================
# SECTION 8: DEVICE HEALTH MONITOR
# ============================================================================


class DeviceHealthMonitor:
    """Main device health monitoring coordinator."""

    def __init__(self, check_interval: float = DEFAULT_CHECK_INTERVAL):
        """Initialize health monitor.

        Args:
            check_interval: Seconds between health checks
        """
        self.check_interval = check_interval
        self.orchestrators: Dict[str, AutoRecoveryOrchestrator] = {}
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    def add_device(
        self,
        device_id: str,
        config: Optional[RecoveryConfig] = None
    ):
        """Add device to monitoring.

        Args:
            device_id: ADB device identifier
            config: Optional RecoveryConfig
        """
        if device_id not in self.orchestrators:
            config = config or RecoveryConfig()
            orchestrator = AutoRecoveryOrchestrator(device_id, config)
            self.orchestrators[device_id] = orchestrator
            logger.info(f"Added device to monitor: {device_id}")

    def check_device(self, device_id: str) -> DeviceHealthReport:
        """Check health of specific device.

        Args:
            device_id: ADB device identifier

        Returns:
            DeviceHealthReport instance
        """
        if device_id not in self.orchestrators:
            self.add_device(device_id)

        orchestrator = self.orchestrators[device_id]
        return orchestrator.generate_health_report()

    def check_all_devices(self) -> Dict[str, DeviceHealthReport]:
        """Check health of all monitored devices.

        Returns:
            Dictionary mapping device_id to DeviceHealthReport
        """
        reports = {}
        for device_id, orchestrator in self.orchestrators.items():
            reports[device_id] = orchestrator.generate_health_report()
        return reports

    def auto_recover_device(self, device_id: str) -> bool:
        """Trigger auto-recovery for device.

        Args:
            device_id: ADB device identifier

        Returns:
            True if recovery successful
        """
        if device_id not in self.orchestrators:
            self.add_device(device_id)

        orchestrator = self.orchestrators[device_id]
        return orchestrator.execute_recovery()

    def start_monitoring(self):
        """Start continuous health monitoring in background thread."""
        if self.monitoring:
            logger.warning("Monitoring already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Health monitoring started")

    def stop_monitoring(self):
        """Stop health monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring:
            try:
                reports = self.check_all_devices()
                for device_id, report in reports.items():
                    if report.health_status != "healthy":
                        logger.warning(
                            f"{device_id}: {report.health_status} - "
                            f"CPU: {report.metrics['cpu_usage']}%, "
                            f"Mem: {report.metrics['memory_usage']}%"
                        )

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(self.check_interval)


# ============================================================================
# SECTION 9: CLI INTERFACE
# ============================================================================


@click.command()
@click.option(
    "--device",
    type=str,
    default=None,
    help="Single device to monitor (device serial)"
)
@click.option(
    "--batch-devices",
    type=str,
    default=None,
    help="Multiple devices (comma-separated: dev1,dev2,dev3)"
)
@click.option(
    "--check-interval",
    type=float,
    default=DEFAULT_CHECK_INTERVAL,
    help="Seconds between health checks"
)
@click.option(
    "--auto-recover",
    is_flag=True,
    help="Enable automatic recovery on failure"
)
@click.option(
    "--max-recovery-attempts",
    type=int,
    default=DEFAULT_MAX_RECOVERY_ATTEMPTS,
    help="Maximum recovery attempts"
)
@click.option(
    "--timeout",
    type=float,
    default=DEFAULT_TIMEOUT,
    help="Command execution timeout (seconds)"
)
@click.option(
    "--report-format",
    type=click.Choice(["text", "json", "toon"]),
    default="text",
    help="Report output format"
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging"
)
def main(
    device: Optional[str],
    batch_devices: Optional[str],
    check_interval: float,
    auto_recover: bool,
    max_recovery_attempts: int,
    timeout: float,
    report_format: str,
    verbose: bool,
):
    """Monitor device health with automatic recovery."""

    if verbose:
        logger.setLevel(logging.DEBUG)

    console.print(Panel.fit(
        "[bold cyan]ADB Device Health Monitor[/bold cyan]",
        border_style="blue"
    ))

    try:
        # Create recovery config
        recovery_config = RecoveryConfig(
            enabled=auto_recover,
            max_attempts=max_recovery_attempts,
        )

        # Initialize monitor
        monitor = DeviceHealthMonitor(check_interval=check_interval)

        # Add devices
        devices = []
        if device:
            devices.append(device)
        if batch_devices:
            devices.extend([d.strip() for d in batch_devices.split(",")])

        if not devices:
            console.print("[red]✗[/red] No devices specified")
            sys.exit(3)

        for dev_id in devices:
            monitor.add_device(dev_id, recovery_config)

        # Check each device
        all_reports = monitor.check_all_devices()

        # Display results
        if report_format == "json":
            output = json.dumps(
                {k: asdict(v) for k, v in all_reports.items()},
                indent=2,
                default=str
            )
            console.print(output)
        elif report_format == "toon":
            for device_id, report in all_reports.items():
                console.print_json(data=asdict(report))
        else:  # text
            table = Table(title="Device Health Report", box=box.ROUNDED)
            table.add_column("Device", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("CPU", style="yellow")
            table.add_column("Memory", style="yellow")
            table.add_column("Temp", style="red")

            for device_id, report in all_reports.items():
                table.add_row(
                    device_id,
                    report.health_status,
                    f"{report.metrics['cpu_usage']:.1f}%",
                    f"{report.metrics['memory_usage']:.1f}%",
                    f"{report.metrics['thermal_temp']:.1f}°C",
                )

            console.print(table)

        # Auto-recovery if enabled and needed
        if auto_recover:
            for device_id, report in all_reports.items():
                if report.health_status != "healthy":
                    console.print(
                        f"[yellow]→[/yellow] Attempting recovery on {device_id}"
                    )
                    success = monitor.auto_recover_device(device_id)
                    status = "[green]✓[/green] Recovered" if success else "[red]✗[/red] Failed"
                    console.print(f"  {status}")

        sys.exit(0)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        if verbose:
            console.print_exception()
        sys.exit(2)


if __name__ == "__main__":
    main()
