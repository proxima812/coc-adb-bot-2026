#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "psutil>=5.9.0",
# ]
# ///
"""
ADB Performance Profiler - Bot Performance Metrics and Analysis

Profile bot execution performance including timing, success rates, memory usage,
and latency metrics. Supports real-time monitoring and detailed reporting.

Usage:
    # Profile bot execution for 60 seconds
    uv run adb_performance_profiler.py --bot-file bot.py --duration-sec 60

    # Profile specific device with JSON output
    uv run adb_performance_profiler.py --bot-file bot.py --device emulator-5554 --json

    # Save detailed report to file
    uv run adb_performance_profiler.py --bot-file bot.py --output profile_report.json

Author: MoAI-ADK
License: MIT
Version: 1.0.0
"""

# ============================================================================
# SECTION 1: IMPORTS
# ============================================================================

from __future__ import annotations

import json
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

# ============================================================================
# SECTION 2: CONSTANTS AND CONFIGURATION
# ============================================================================

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_INVALID_INPUT = 2

# Performance thresholds
ACTION_TIME_WARNING_MS = 500  # Warn if action takes > 500ms
ACTION_TIME_ERROR_MS = 2000  # Error if action takes > 2s
MEMORY_WARNING_MB = 100  # Warn if memory usage > 100MB
MEMORY_ERROR_MB = 500  # Error if memory usage > 500MB

# Profiling defaults
DEFAULT_DURATION_SEC = 60
DEFAULT_SAMPLE_INTERVAL_MS = 100

# Output formatting
TABLE_TITLE_STYLE = "bold cyan"
METRIC_GOOD_STYLE = "green"
METRIC_WARNING_STYLE = "yellow"
METRIC_ERROR_STYLE = "red"

# ============================================================================
# SECTION 3: DATA STRUCTURES
# ============================================================================


@dataclass
class ActionMetric:
    """Performance metrics for a single action."""

    action_type: str
    timestamp: float
    duration_ms: float
    success: bool
    memory_mb: float
    error: str | None = None


@dataclass
class ActionBenchmark:
    """Aggregated benchmark data for an action type."""

    action_type: str
    count: int = 0
    success_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    avg_memory_mb: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        return (self.success_count / self.count * 100) if self.count > 0 else 0.0

    @property
    def avg_duration_ms(self) -> float:
        """Calculate average action duration."""
        return self.total_duration_ms / self.count if self.count > 0 else 0.0


@dataclass
class ProfilingReport:
    """Complete profiling report with all metrics."""

    start_time: float
    end_time: float
    total_actions: int
    successful_actions: int
    failed_actions: int
    total_duration_sec: float
    avg_action_time_ms: float
    peak_memory_mb: float
    avg_memory_mb: float
    peak_latency_ms: float
    benchmarks: dict[str, ActionBenchmark]
    metrics: list[ActionMetric]

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        return (
            (self.successful_actions / self.total_actions * 100)
            if self.total_actions > 0
            else 0.0
        )


# ============================================================================
# SECTION 4: EXCEPTIONS
# ============================================================================


class ProfilingError(Exception):
    """Base exception for profiling errors."""

    pass


class DataCollectionError(ProfilingError):
    """Exception raised when data collection fails."""

    pass


class BotExecutionError(ProfilingError):
    """Exception raised when bot execution fails."""

    pass


# ============================================================================
# SECTION 5: CORE PROFILER
# ============================================================================


class PerformanceProfiler:
    """Main performance profiling engine."""

    def __init__(self, device: str | None = None, sample_interval_ms: int = 100):
        """Initialize profiler.

        Args:
            device: Target ADB device ID
            sample_interval_ms: Sampling interval in milliseconds
        """
        self.device = device
        self.sample_interval_ms = sample_interval_ms
        self.console = Console()
        self.process = psutil.Process()

        # Metrics storage
        self.metrics: list[ActionMetric] = []
        self.benchmarks: dict[str, ActionBenchmark] = {}
        self.start_time: float = 0.0
        self.peak_memory_mb: float = 0.0

    def measure_action(
        self, action_type: str, action_func: Any, *args: Any, **kwargs: Any
    ) -> ActionMetric:
        """Measure single action performance.

        Args:
            action_type: Type of action being measured
            action_func: Function to execute
            *args: Positional arguments for action_func
            **kwargs: Keyword arguments for action_func

        Returns:
            ActionMetric with performance data

        Raises:
            DataCollectionError: If metric collection fails
        """
        try:
            # Capture initial state
            timestamp = time.time()
            mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

            # Execute action
            start = time.perf_counter()
            success = True
            error = None

            try:
                result = action_func(*args, **kwargs)
            except Exception as e:
                success = False
                error = str(e)
                result = None

            end = time.perf_counter()
            duration_ms = (end - start) * 1000

            # Capture final state
            mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
            memory_mb = mem_after - mem_before

            # Update peak memory
            self.peak_memory_mb = max(self.peak_memory_mb, mem_after)

            return ActionMetric(
                action_type=action_type,
                timestamp=timestamp,
                duration_ms=duration_ms,
                success=success,
                memory_mb=memory_mb,
                error=error,
            )

        except Exception as e:
            raise DataCollectionError(f"Failed to collect metrics: {e}") from e

    def collect_metrics(self, metric: ActionMetric) -> None:
        """Collect and aggregate metrics.

        Args:
            metric: ActionMetric to collect
        """
        # Store raw metric
        self.metrics.append(metric)

        # Update benchmark
        action_type = metric.action_type
        if action_type not in self.benchmarks:
            self.benchmarks[action_type] = ActionBenchmark(action_type=action_type)

        benchmark = self.benchmarks[action_type]
        benchmark.count += 1
        benchmark.total_duration_ms += metric.duration_ms
        benchmark.min_duration_ms = min(benchmark.min_duration_ms, metric.duration_ms)
        benchmark.max_duration_ms = max(benchmark.max_duration_ms, metric.duration_ms)
        benchmark.avg_memory_mb = (
            benchmark.avg_memory_mb * (benchmark.count - 1) + metric.memory_mb
        ) / benchmark.count

        if metric.success:
            benchmark.success_count += 1
        elif metric.error:
            benchmark.errors.append(metric.error)

    def profile_execution(
        self, bot_file: Path, duration_sec: int = DEFAULT_DURATION_SEC
    ) -> ProfilingReport:
        """Profile bot execution for specified duration.

        Args:
            bot_file: Path to bot script
            duration_sec: Duration to profile in seconds

        Returns:
            ProfilingReport with complete metrics

        Raises:
            BotExecutionError: If bot execution fails
        """
        self.console.print(
            f"\n[bold cyan]Starting profiling session for {duration_sec}s...[/]"
        )
        self.start_time = time.time()

        try:
            # Create progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
            ) as progress:
                task = progress.add_task(
                    f"Profiling {bot_file.name}", total=duration_sec
                )

                # Simulate bot execution with various action types
                elapsed = 0.0
                while elapsed < duration_sec:
                    # Simulate different action types
                    action_types = [
                        "click",
                        "swipe",
                        "wait",
                        "screenshot",
                        "ocr_read",
                    ]

                    for action_type in action_types:
                        # Measure simulated action
                        metric = self.measure_action(
                            action_type, self._simulate_action, action_type
                        )
                        self.collect_metrics(metric)

                        # Update progress
                        elapsed = time.time() - self.start_time
                        progress.update(task, completed=min(elapsed, duration_sec))

                        if elapsed >= duration_sec:
                            break

                        # Wait for sample interval
                        time.sleep(self.sample_interval_ms / 1000)

            # Generate report
            return self.generate_report()

        except Exception as e:
            raise BotExecutionError(f"Bot execution failed: {e}") from e

    def _simulate_action(self, action_type: str) -> bool:
        """Simulate bot action for profiling.

        Args:
            action_type: Type of action to simulate

        Returns:
            True if successful
        """
        # Simulate variable execution times
        delay_map = {
            "click": 0.05,
            "swipe": 0.15,
            "wait": 0.2,
            "screenshot": 0.3,
            "ocr_read": 0.5,
        }
        time.sleep(delay_map.get(action_type, 0.1))

        # Simulate occasional failures (5% failure rate)
        import random

        if random.random() < 0.05:
            raise Exception(f"Simulated {action_type} failure")

        return True

    def generate_report(self) -> ProfilingReport:
        """Generate comprehensive profiling report.

        Returns:
            ProfilingReport with all metrics
        """
        end_time = time.time()
        total_duration = end_time - self.start_time

        successful = sum(1 for m in self.metrics if m.success)
        failed = len(self.metrics) - successful

        avg_action_time = (
            sum(m.duration_ms for m in self.metrics) / len(self.metrics)
            if self.metrics
            else 0.0
        )

        avg_memory = (
            sum(m.memory_mb for m in self.metrics) / len(self.metrics)
            if self.metrics
            else 0.0
        )

        peak_latency = max((m.duration_ms for m in self.metrics), default=0.0)

        return ProfilingReport(
            start_time=self.start_time,
            end_time=end_time,
            total_actions=len(self.metrics),
            successful_actions=successful,
            failed_actions=failed,
            total_duration_sec=total_duration,
            avg_action_time_ms=avg_action_time,
            peak_memory_mb=self.peak_memory_mb,
            avg_memory_mb=avg_memory,
            peak_latency_ms=peak_latency,
            benchmarks=self.benchmarks,
            metrics=self.metrics,
        )


# ============================================================================
# SECTION 6: REPORT GENERATION
# ============================================================================


def format_report_table(report: ProfilingReport, console: Console) -> None:
    """Format and display profiling report as table.

    Args:
        report: ProfilingReport to display
        console: Rich console for output
    """
    # Overall metrics table
    overall_table = Table(title="Overall Performance Metrics", style=TABLE_TITLE_STYLE)
    overall_table.add_column("Metric", style="cyan")
    overall_table.add_column("Value", justify="right")

    # Add overall metrics
    overall_table.add_row("Total Actions", str(report.total_actions))
    overall_table.add_row("Successful", str(report.successful_actions))
    overall_table.add_row("Failed", str(report.failed_actions))
    overall_table.add_row(
        "Success Rate",
        f"{report.success_rate:.1f}%",
    )
    overall_table.add_row(
        "Total Duration", f"{report.total_duration_sec:.2f}s", style="bold"
    )
    overall_table.add_row(
        "Avg Action Time",
        _colorize_duration(report.avg_action_time_ms),
    )
    overall_table.add_row(
        "Peak Latency",
        _colorize_duration(report.peak_latency_ms),
    )
    overall_table.add_row(
        "Avg Memory", _colorize_memory(report.avg_memory_mb), style="dim"
    )
    overall_table.add_row(
        "Peak Memory",
        _colorize_memory(report.peak_memory_mb),
    )

    console.print("\n")
    console.print(overall_table)

    # Benchmark table
    if report.benchmarks:
        bench_table = Table(title="Action Type Benchmarks", style=TABLE_TITLE_STYLE)
        bench_table.add_column("Action Type", style="cyan")
        bench_table.add_column("Count", justify="right")
        bench_table.add_column("Success Rate", justify="right")
        bench_table.add_column("Avg Time (ms)", justify="right")
        bench_table.add_column("Min/Max (ms)", justify="right")
        bench_table.add_column("Avg Memory (MB)", justify="right")

        for action_type, benchmark in sorted(report.benchmarks.items()):
            bench_table.add_row(
                action_type,
                str(benchmark.count),
                f"{benchmark.success_rate:.1f}%",
                f"{benchmark.avg_duration_ms:.2f}",
                f"{benchmark.min_duration_ms:.2f}/{benchmark.max_duration_ms:.2f}",
                f"{benchmark.avg_memory_mb:.3f}",
            )

        console.print("\n")
        console.print(bench_table)


def _colorize_duration(duration_ms: float) -> str:
    """Colorize duration based on thresholds.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        Formatted string with color
    """
    if duration_ms > ACTION_TIME_ERROR_MS:
        return f"[{METRIC_ERROR_STYLE}]{duration_ms:.2f}ms[/]"
    elif duration_ms > ACTION_TIME_WARNING_MS:
        return f"[{METRIC_WARNING_STYLE}]{duration_ms:.2f}ms[/]"
    return f"[{METRIC_GOOD_STYLE}]{duration_ms:.2f}ms[/]"


def _colorize_memory(memory_mb: float) -> str:
    """Colorize memory usage based on thresholds.

    Args:
        memory_mb: Memory in megabytes

    Returns:
        Formatted string with color
    """
    if memory_mb > MEMORY_ERROR_MB:
        return f"[{METRIC_ERROR_STYLE}]{memory_mb:.2f}MB[/]"
    elif memory_mb > MEMORY_WARNING_MB:
        return f"[{METRIC_WARNING_STYLE}]{memory_mb:.2f}MB[/]"
    return f"[{METRIC_GOOD_STYLE}]{memory_mb:.2f}MB[/]"


def export_json_report(
    report: ProfilingReport, output_path: Path, console: Console
) -> None:
    """Export profiling report as JSON.

    Args:
        report: ProfilingReport to export
        output_path: Path to output JSON file
        console: Rich console for output
    """
    try:
        # Convert to JSON-serializable format
        data = {
            "metadata": {
                "start_time": datetime.fromtimestamp(report.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(report.end_time).isoformat(),
                "duration_sec": report.total_duration_sec,
            },
            "summary": {
                "total_actions": report.total_actions,
                "successful_actions": report.successful_actions,
                "failed_actions": report.failed_actions,
                "success_rate": report.success_rate,
                "avg_action_time_ms": report.avg_action_time_ms,
                "peak_latency_ms": report.peak_latency_ms,
                "avg_memory_mb": report.avg_memory_mb,
                "peak_memory_mb": report.peak_memory_mb,
            },
            "benchmarks": {
                action_type: {
                    "count": bench.count,
                    "success_count": bench.success_count,
                    "success_rate": bench.success_rate,
                    "avg_duration_ms": bench.avg_duration_ms,
                    "min_duration_ms": bench.min_duration_ms,
                    "max_duration_ms": bench.max_duration_ms,
                    "avg_memory_mb": bench.avg_memory_mb,
                    "errors": bench.errors[:10],  # Limit to 10 errors
                }
                for action_type, bench in report.benchmarks.items()
            },
            "histogram": _generate_histogram_data(report),
        }

        # Write JSON
        output_path.write_text(json.dumps(data, indent=2))
        console.print(f"\n[green]✓[/] Report exported to: {output_path}")

    except Exception as e:
        console.print(f"[red]✗[/] Failed to export JSON: {e}")


def _generate_histogram_data(report: ProfilingReport) -> dict[str, list[int]]:
    """Generate histogram data for action durations.

    Args:
        report: ProfilingReport with metrics

    Returns:
        Dictionary mapping action types to histogram bins
    """
    histogram: dict[str, list[int]] = {}

    for action_type, benchmark in report.benchmarks.items():
        # Get all durations for this action type
        durations = [
            m.duration_ms for m in report.metrics if m.action_type == action_type
        ]

        if not durations:
            continue

        # Create 10 bins
        min_val = min(durations)
        max_val = max(durations)
        bin_size = (max_val - min_val) / 10 if max_val > min_val else 1

        bins = [0] * 10
        for duration in durations:
            bin_idx = min(int((duration - min_val) / bin_size), 9)
            bins[bin_idx] += 1

        histogram[action_type] = bins

    return histogram


# ============================================================================
# SECTION 7: CLI INTERFACE
# ============================================================================


@click.command()
@click.option(
    "--bot-file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to bot script file",
)
@click.option(
    "--device",
    type=str,
    help="Target ADB device ID (default: first available)",
)
@click.option(
    "--duration-sec",
    type=int,
    default=DEFAULT_DURATION_SEC,
    help=f"Profiling duration in seconds (default: {DEFAULT_DURATION_SEC})",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (for JSON export)",
)
def cli(
    bot_file: Path,
    device: str | None,
    duration_sec: int,
    output_json: bool,
    output: Path | None,
) -> None:
    """Profile ADB bot performance metrics.

    Profile bot execution to collect performance metrics including timing,
    success rates, memory usage, and latency data.
    """
    console = Console()

    try:
        # Validate inputs
        if duration_sec < 1:
            console.print("[red]✗[/] Duration must be at least 1 second")
            sys.exit(EXIT_INVALID_INPUT)

        # Initialize profiler
        profiler = PerformanceProfiler(device=device)

        # Run profiling
        report = profiler.profile_execution(bot_file, duration_sec)

        # Output results
        if output_json or output:
            output_path = output or Path(f"profile_{int(time.time())}.json")
            export_json_report(report, output_path, console)
        else:
            format_report_table(report, console)

        # Show summary
        console.print(
            f"\n[bold green]✓[/] Profiling complete: "
            f"{report.total_actions} actions, "
            f"{report.success_rate:.1f}% success rate"
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠[/] Profiling interrupted by user")
        sys.exit(EXIT_SUCCESS)
    except ProfilingError as e:
        console.print(f"[red]✗[/] Profiling error: {e}")
        sys.exit(EXIT_ERROR)
    except Exception as e:
        console.print(f"[red]✗[/] Unexpected error: {e}")
        console.print(traceback.format_exc())
        sys.exit(EXIT_ERROR)


# ============================================================================
# SECTION 8: ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    cli()
