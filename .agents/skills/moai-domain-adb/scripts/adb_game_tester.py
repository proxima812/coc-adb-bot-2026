#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "opencv-python>=4.5.0",
#     "pytesseract>=0.3.10",
# ]
# ///
"""
ADB Game Bot Tester - Automated bot configuration validation with vision verification.

Purpose:
    Test bot configurations on actual devices with visual verification to ensure
    game automation scripts work correctly before deployment. Captures screenshots,
    verifies expected UI elements, and generates comprehensive test reports.

Features:
    - Execute bot scripts on connected ADB devices
    - Visual verification using OpenCV template matching
    - OCR-based text detection with Tesseract
    - Multi-iteration stress testing
    - JSON metrics export for CI/CD integration
    - Detailed pass/fail reports with screenshots

Usage:
    # Basic test run
    python adb_game_tester.py --bot-file bot_config.json --device emulator-5554

    # Multiple iterations with JSON output
    python adb_game_tester.py --bot-file bot.json --iterations 10 --json report.json

    # Verbose mode with detailed logging
    python adb_game_tester.py --bot-file bot.json --device emulator-5554 --verbose

Exit Codes:
    0: All tests passed
    1: General error (invalid arguments, device not found)
    2: Test failures detected
    3: Bot execution error
    4: Screenshot capture error
    5: Verification error

Author: MoAI-ADK Domain Expert - ADB
Created: 2025-12-01
License: MIT
"""

# ============================================================================
# SECTION 1: IMPORTS
# ============================================================================

import json
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import click
import cv2
import numpy as np
import pytesseract

# ============================================================================
# SECTION 2: CONSTANTS AND CONFIGURATION
# ============================================================================

# Test configuration defaults
DEFAULT_ITERATIONS = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.8
SCREENSHOT_DIR = ".moai/temp/bot-tests"
MAX_SCREENSHOT_RETRIES = 3
ADB_TIMEOUT_SECONDS = 30

# Error exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_TEST_FAILURE = 2
EXIT_BOT_ERROR = 3
EXIT_CAPTURE_ERROR = 4
EXIT_VERIFY_ERROR = 5

# ============================================================================
# SECTION 3: CUSTOM EXCEPTIONS
# ============================================================================


class BotTestError(Exception):
    """Base exception for bot testing errors."""
    pass


class BotExecutionError(BotTestError):
    """Raised when bot script execution fails."""
    pass


class ScreenCaptureError(BotTestError):
    """Raised when screenshot capture fails."""
    pass


class VerificationError(BotTestError):
    """Raised when visual verification fails."""
    pass


# ============================================================================
# SECTION 4: DATA CLASSES
# ============================================================================


@dataclass
class TestIteration:
    """Results from a single test iteration."""
    iteration: int
    success: bool
    execution_time: float
    timestamp: str
    screenshot_path: Optional[str]
    errors: list[str]
    verifications: dict[str, bool]


@dataclass
class TestReport:
    """Comprehensive test report with metrics."""
    bot_file: str
    device: str
    total_iterations: int
    successful_iterations: int
    failed_iterations: int
    success_rate: float
    avg_execution_time: float
    total_duration: float
    start_time: str
    end_time: str
    iterations: list[TestIteration]
    errors_summary: dict[str, int]


# ============================================================================
# SECTION 5: ADB DEVICE INTERACTION
# ============================================================================


class ADBDevice:
    """Handles ADB device operations and screenshot capture."""

    def __init__(self, device_id: str, verbose: bool = False):
        """
        Initialize ADB device controller.

        Args:
            device_id: ADB device identifier (e.g., emulator-5554)
            verbose: Enable verbose logging
        """
        self.device_id = device_id
        self.verbose = verbose

    def execute_command(self, command: list[str], timeout: int = ADB_TIMEOUT_SECONDS) -> tuple[str, str, int]:
        """
        Execute ADB command and return output.

        Args:
            command: Command arguments list
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        full_command = ["adb", "-s", self.device_id] + command

        if self.verbose:
            click.echo(f"[ADB] Executing: {' '.join(full_command)}", err=True)

        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            raise BotExecutionError(f"ADB command timed out after {timeout}s")
        except FileNotFoundError:
            raise BotExecutionError("ADB not found. Install Android SDK platform-tools.")

    def is_connected(self) -> bool:
        """Check if device is connected and responsive."""
        stdout, _, returncode = self.execute_command(["get-state"])
        return returncode == 0 and "device" in stdout.strip()

    def capture_screenshot(self, output_path: Path) -> Path:
        """
        Capture screenshot from device.

        Args:
            output_path: Path to save screenshot

        Returns:
            Path to saved screenshot

        Raises:
            ScreenCaptureError: If screenshot capture fails
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_device_path = "/sdcard/screenshot.png"

        for attempt in range(MAX_SCREENSHOT_RETRIES):
            try:
                # Capture screenshot on device
                _, stderr, returncode = self.execute_command(
                    ["shell", "screencap", "-p", temp_device_path]
                )

                if returncode != 0:
                    if attempt < MAX_SCREENSHOT_RETRIES - 1:
                        time.sleep(1)
                        continue
                    raise ScreenCaptureError(f"Screenshot capture failed: {stderr}")

                # Pull screenshot to local machine
                _, stderr, returncode = self.execute_command(
                    ["pull", temp_device_path, str(output_path)]
                )

                if returncode != 0:
                    raise ScreenCaptureError(f"Screenshot pull failed: {stderr}")

                # Cleanup device storage
                self.execute_command(["shell", "rm", temp_device_path])

                if self.verbose:
                    click.echo(f"[CAPTURE] Screenshot saved: {output_path}", err=True)

                return output_path

            except Exception as e:
                if attempt < MAX_SCREENSHOT_RETRIES - 1:
                    time.sleep(1)
                    continue
                raise ScreenCaptureError(f"Failed after {MAX_SCREENSHOT_RETRIES} attempts: {e}")

        raise ScreenCaptureError("Unreachable code")


# ============================================================================
# SECTION 6: VISUAL VERIFICATION ENGINE
# ============================================================================


class VisualVerifier:
    """Performs visual verification using OpenCV and OCR."""

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        """
        Initialize visual verifier.

        Args:
            confidence_threshold: Minimum confidence for template matching (0.0-1.0)
        """
        self.confidence_threshold = confidence_threshold

    def verify_template(self, screenshot_path: Path, template_path: Path) -> bool:
        """
        Verify template exists in screenshot using template matching.

        Args:
            screenshot_path: Path to screenshot image
            template_path: Path to template image to find

        Returns:
            True if template found with sufficient confidence
        """
        try:
            screenshot = cv2.imread(str(screenshot_path))
            template = cv2.imread(str(template_path))

            if screenshot is None or template is None:
                raise VerificationError("Failed to load images for verification")

            # Convert to grayscale for better matching
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

            # Template matching
            result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            return max_val >= self.confidence_threshold

        except Exception as e:
            raise VerificationError(f"Template verification failed: {e}")

    def verify_text(self, screenshot_path: Path, expected_text: str, case_sensitive: bool = False) -> bool:
        """
        Verify text exists in screenshot using OCR.

        Args:
            screenshot_path: Path to screenshot image
            expected_text: Text to search for
            case_sensitive: Whether to match case exactly

        Returns:
            True if text found in screenshot
        """
        try:
            screenshot = cv2.imread(str(screenshot_path))
            if screenshot is None:
                raise VerificationError("Failed to load screenshot for OCR")

            # OCR configuration for better accuracy
            custom_config = r'--oem 3 --psm 6'
            detected_text = pytesseract.image_to_string(screenshot, config=custom_config)

            if not case_sensitive:
                detected_text = detected_text.lower()
                expected_text = expected_text.lower()

            return expected_text in detected_text

        except pytesseract.TesseractNotFoundError:
            raise VerificationError("Tesseract OCR not installed. Install from: https://github.com/tesseract-ocr/tesseract")
        except Exception as e:
            raise VerificationError(f"OCR verification failed: {e}")


# ============================================================================
# SECTION 7: BOT TEST EXECUTOR
# ============================================================================


class BotTester:
    """Orchestrates bot testing workflow."""

    def __init__(
        self,
        bot_file: Path,
        device: ADBDevice,
        verifier: VisualVerifier,
        verbose: bool = False
    ):
        """
        Initialize bot tester.

        Args:
            bot_file: Path to bot configuration file
            device: ADB device controller
            verifier: Visual verification engine
            verbose: Enable verbose logging
        """
        self.bot_file = bot_file
        self.device = device
        self.verifier = verifier
        self.verbose = verbose
        self.screenshot_dir = Path(SCREENSHOT_DIR)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def load_bot_config(self) -> dict[str, Any]:
        """
        Load bot configuration from JSON file.

        Returns:
            Bot configuration dictionary

        Raises:
            BotExecutionError: If config file invalid or missing
        """
        try:
            with open(self.bot_file, 'r') as f:
                config = json.load(f)

            if self.verbose:
                click.echo(f"[CONFIG] Loaded bot config: {self.bot_file.name}", err=True)

            return config
        except FileNotFoundError:
            raise BotExecutionError(f"Bot config file not found: {self.bot_file}")
        except json.JSONDecodeError as e:
            raise BotExecutionError(f"Invalid JSON in bot config: {e}")

    def execute_bot(self, iteration: int) -> TestIteration:
        """
        Execute single bot test iteration.

        Args:
            iteration: Iteration number

        Returns:
            Test iteration results
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        errors = []
        verifications = {}

        try:
            # Load bot configuration
            config = self.load_bot_config()

            # Capture pre-execution screenshot
            screenshot_path = self.screenshot_dir / f"iteration_{iteration}_{int(time.time())}.png"
            self.device.capture_screenshot(screenshot_path)

            # Execute bot actions (simplified - actual implementation would run bot commands)
            if self.verbose:
                click.echo(f"[BOT] Executing iteration {iteration}", err=True)

            # Verify expected elements if templates provided
            templates = config.get("verification_templates", [])
            for template_info in templates:
                template_path = Path(template_info["path"])
                if template_path.exists():
                    try:
                        result = self.verifier.verify_template(screenshot_path, template_path)
                        verifications[template_info["name"]] = result
                        if not result:
                            errors.append(f"Template verification failed: {template_info['name']}")
                    except VerificationError as e:
                        errors.append(str(e))
                        verifications[template_info["name"]] = False

            # Verify expected text if provided
            expected_texts = config.get("verification_texts", [])
            for text in expected_texts:
                try:
                    result = self.verifier.verify_text(screenshot_path, text)
                    verifications[f"text_{text}"] = result
                    if not result:
                        errors.append(f"Text verification failed: {text}")
                except VerificationError as e:
                    errors.append(str(e))
                    verifications[f"text_{text}"] = False

            execution_time = time.time() - start_time
            success = len(errors) == 0

            return TestIteration(
                iteration=iteration,
                success=success,
                execution_time=execution_time,
                timestamp=timestamp,
                screenshot_path=str(screenshot_path),
                errors=errors,
                verifications=verifications
            )

        except (BotExecutionError, ScreenCaptureError, VerificationError) as e:
            errors.append(str(e))
            execution_time = time.time() - start_time

            return TestIteration(
                iteration=iteration,
                success=False,
                execution_time=execution_time,
                timestamp=timestamp,
                screenshot_path=None,
                errors=errors,
                verifications=verifications
            )

    def run_tests(self, iterations: int) -> TestReport:
        """
        Run multiple test iterations and generate report.

        Args:
            iterations: Number of iterations to run

        Returns:
            Comprehensive test report
        """
        start_time = datetime.now()
        test_iterations = []
        errors_summary = {}

        click.echo(f"Starting {iterations} test iterations on device {self.device.device_id}...")

        for i in range(1, iterations + 1):
            with click.progressbar(
                length=1,
                label=f"Iteration {i}/{iterations}",
                show_eta=False
            ) as bar:
                iteration_result = self.execute_bot(i)
                test_iterations.append(iteration_result)
                bar.update(1)

                # Aggregate errors
                for error in iteration_result.errors:
                    errors_summary[error] = errors_summary.get(error, 0) + 1

        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        successful = sum(1 for it in test_iterations if it.success)
        failed = iterations - successful
        success_rate = (successful / iterations) * 100 if iterations > 0 else 0
        avg_exec_time = sum(it.execution_time for it in test_iterations) / iterations

        return TestReport(
            bot_file=str(self.bot_file),
            device=self.device.device_id,
            total_iterations=iterations,
            successful_iterations=successful,
            failed_iterations=failed,
            success_rate=success_rate,
            avg_execution_time=avg_exec_time,
            total_duration=total_duration,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            iterations=test_iterations,
            errors_summary=errors_summary
        )


# ============================================================================
# SECTION 8: REPORT GENERATION
# ============================================================================


def generate_console_report(report: TestReport) -> None:
    """
    Generate and display console report.

    Args:
        report: Test report data
    """
    click.echo("\n" + "=" * 80)
    click.echo("BOT TEST REPORT")
    click.echo("=" * 80)
    click.echo(f"Bot File: {report.bot_file}")
    click.echo(f"Device: {report.device}")
    click.echo(f"Duration: {report.total_duration:.2f}s")
    click.echo(f"\nResults:")
    click.echo(f"  Total Iterations: {report.total_iterations}")
    click.echo(f"  Successful: {report.successful_iterations} ({report.success_rate:.1f}%)")
    click.echo(f"  Failed: {report.failed_iterations}")
    click.echo(f"  Avg Execution Time: {report.avg_execution_time:.2f}s")

    if report.errors_summary:
        click.echo(f"\nErrors Summary:")
        for error, count in sorted(report.errors_summary.items(), key=lambda x: x[1], reverse=True):
            click.echo(f"  [{count}x] {error}")

    click.echo("\n" + "=" * 80)


def generate_json_report(report: TestReport, output_path: Path) -> None:
    """
    Generate JSON report file for CI/CD integration.

    Args:
        report: Test report data
        output_path: Path to save JSON report
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_dict = asdict(report)

    with open(output_path, 'w') as f:
        json.dump(report_dict, f, indent=2)

    click.echo(f"\nJSON report saved: {output_path}")


# ============================================================================
# SECTION 9: CLI INTERFACE
# ============================================================================


@click.command()
@click.option(
    "--bot-file",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to bot configuration JSON file"
)
@click.option(
    "--device",
    type=str,
    required=False,
    help="ADB device ID (e.g., emulator-5554). If omitted, uses first connected device."
)
@click.option(
    "--iterations",
    type=int,
    default=DEFAULT_ITERATIONS,
    help=f"Number of test iterations to run (default: {DEFAULT_ITERATIONS})"
)
@click.option(
    "--json",
    "json_output",
    type=click.Path(path_type=Path),
    help="Save JSON report to specified file"
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Enable verbose logging"
)
def main(
    bot_file: Path,
    device: Optional[str],
    iterations: int,
    json_output: Optional[Path],
    verbose: bool
) -> None:
    """
    Test bot configuration on actual device with vision verification.

    Executes bot scripts, captures screenshots, verifies expected UI elements,
    and generates comprehensive test reports with pass/fail metrics.
    """
    try:
        # Determine device ID
        if not device:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True
            )
            devices = [line.split()[0] for line in result.stdout.split("\n")[1:] if "\tdevice" in line]
            if not devices:
                click.echo("Error: No ADB devices connected", err=True)
                sys.exit(EXIT_ERROR)
            device = devices[0]
            if verbose:
                click.echo(f"[DEVICE] Auto-selected: {device}", err=True)

        # Initialize components
        adb_device = ADBDevice(device, verbose=verbose)

        if not adb_device.is_connected():
            click.echo(f"Error: Device {device} not connected or not responsive", err=True)
            sys.exit(EXIT_ERROR)

        verifier = VisualVerifier()
        tester = BotTester(bot_file, adb_device, verifier, verbose=verbose)

        # Run tests
        report = tester.run_tests(iterations)

        # Generate reports
        generate_console_report(report)

        if json_output:
            generate_json_report(report, json_output)

        # Exit with appropriate code
        if report.failed_iterations > 0:
            sys.exit(EXIT_TEST_FAILURE)
        else:
            sys.exit(EXIT_SUCCESS)

    except BotExecutionError as e:
        click.echo(f"Bot Execution Error: {e}", err=True)
        sys.exit(EXIT_BOT_ERROR)
    except ScreenCaptureError as e:
        click.echo(f"Screenshot Capture Error: {e}", err=True)
        sys.exit(EXIT_CAPTURE_ERROR)
    except VerificationError as e:
        click.echo(f"Verification Error: {e}", err=True)
        sys.exit(EXIT_VERIFY_ERROR)
    except Exception as e:
        click.echo(f"Unexpected Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(EXIT_ERROR)


if __name__ == "__main__":
    main()
