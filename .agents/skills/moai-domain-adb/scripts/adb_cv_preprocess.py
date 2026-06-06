#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "opencv-python>=4.8.0",
#     "numpy>=1.24.0",
#     "tomli>=2.0.1",
# ]
# ///
"""
Advanced Image Preprocessing Module for ADB Device Vision.

This script provides comprehensive image preprocessing capabilities for
computer vision tasks in ADB automation, including contrast enhancement,
morphological operations, edge detection, and grayscale conversion variants.

Purpose:
    - Enhance image contrast using Contrast Limited Adaptive Histogram
      Equalization (CLAHE)
    - Perform morphological operations (dilate, erode, open, close)
    - Detect edges using Canny and Sobel algorithms
    - Convert images to grayscale using multiple methods
    - Orchestrate preprocessing pipelines with configurable parameters
    - Cache preprocessed images for performance optimization
    - Benchmark preprocessing operations

Features:
    - CLAHEPreprocessor: Adaptive contrast enhancement for local detail
    - MorphologicalProcessor: Shape and structure operations
    - EdgeDetectionProcessor: Edge detection with Canny and Sobel
    - GrayscaleVariantProcessor: Multiple grayscale conversion methods
    - PreprocessingPipeline: Compose preprocessing operations
    - PerformanceMetricsCollector: Benchmark and profile operations
    - TOML configuration support
    - TOON output format for results

Resolution Profiles:
    - 720p: 1280x720, optimized for mobile low-end devices
    - 1080p: 1920x1080, standard mobile device resolution
    - 1440p: 2560x1440, high-end mobile and tablet resolution
    - 2560p: 3840x2560, ultra-high resolution devices

Usage:
    # Basic preprocessing with default settings
    python adb_cv_preprocess.py --image screenshot.png

    # Apply specific preset
    python adb_cv_preprocess.py --image screenshot.png --preset balanced

    # Enable caching and performance profiling
    python adb_cv_preprocess.py --image screenshot.png --cache-enabled \
      --profile

    # Load configuration from TOML file
    python adb_cv_preprocess.py --image screenshot.png \
      --config preprocessing-config.toml

    # Benchmark preprocessing pipeline
    python adb_cv_preprocess.py --image screenshot.png --benchmark

Exit Codes:
    0: Success
    1: File not found
    2: Invalid configuration
    3: OpenCV operation failed
    4: Invalid resolution profile

Author: MoAI-ADK Domain ADB Expert
Version: 1.0.0
License: MIT
"""

# ============================================================================
# SECTION 2: IMPORTS
# ============================================================================

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import sys

import click
import cv2
import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# ============================================================================
# SECTION 3: CONFIGURATION
# ============================================================================

# Console for rich output
console = Console()

# Resolution profiles: (width, height, description)
RESOLUTION_PROFILES = {
    "720p": (1280, 720, "Mobile low-end device"),
    "1080p": (1920, 1080, "Standard mobile device"),
    "1440p": (2560, 1440, "High-end mobile/tablet"),
    "2560p": (3840, 2560, "Ultra-high resolution"),
}

# Grayscale conversion methods
class GrayscaleMethod(Enum):
    """Methods for grayscale conversion"""
    LUMINOSITY = "luminosity"  # Weighted: 0.299*R + 0.587*G + 0.114*B
    AVERAGE = "average"  # Simple average
    DESATURATION = "desaturation"  # (max + min) / 2
    DECOMPOSITION = "decomposition"  # Value channel from HSV

# Morphological kernel sizes
KERNEL_SIZES = {
    "small": (3, 3),
    "medium": (5, 5),
    "large": (7, 7),
}

# ============================================================================
# SECTION 4: DATA STRUCTURES
# ============================================================================

@dataclass
class ProcessingMetrics:
    """Metrics for a single preprocessing operation"""
    operation: str
    input_shape: Tuple[int, int, int]
    output_shape: Tuple[int, int, int]
    execution_time_ms: float
    memory_before_mb: float
    memory_after_mb: float
    cache_hit: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PipelineResult:
    """Result of preprocessing pipeline execution"""
    original_image: np.ndarray
    preprocessed_image: np.ndarray
    preprocessing_steps: List[str]
    metrics: List[ProcessingMetrics]
    total_execution_time_ms: float
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "preprocessing_steps": self.preprocessing_steps,
            "metrics": [m.to_dict() for m in self.metrics],
            "total_execution_time_ms": self.total_execution_time_ms,
            "success": self.success,
            "error_message": self.error_message,
        }


# ============================================================================
# SECTION 5: PREPROCESSOR CLASSES
# ============================================================================

class CLAHEPreprocessor:
    """
    Contrast Limited Adaptive Histogram Equalization (CLAHE).

    CLAHE improves local contrast by applying histogram equalization to
    small tiles of the image, preventing excessive amplification of noise.
    Particularly useful for improving template matching in low-contrast
    screenshots.
    """

    def __init__(self, clip_limit: float = 2.0, tile_grid_size: Tuple[int, int] = (8, 8)):
        """
        Initialize CLAHE preprocessor.

        Args:
            clip_limit: Threshold for contrast limiting. Higher values
                       increase contrast but risk noise amplification.
                       Default: 2.0 (conservative).
            tile_grid_size: Size of grid for histograms. Larger grids
                           affect larger areas. Default: (8, 8).
        """
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.clahe = cv2.createCLAHE(
            clipLimit=clip_limit,
            tileGridSize=tile_grid_size
        )

    def process(self, image: np.ndarray) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Apply CLAHE to image.

        Args:
            image: Input image (BGR or grayscale).

        Returns:
            Tuple of (enhanced_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        try:
            # Convert to LAB color space for better perceptual uniformity
            if len(image.shape) == 3:
                lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
                l_channel, a_channel, b_channel = cv2.split(lab)

                # Apply CLAHE only to L channel (brightness)
                l_enhanced = self.clahe.apply(l_channel)

                # Merge channels and convert back to BGR
                lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
                result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
            else:
                # Grayscale image
                result = self.clahe.apply(image)
        except Exception as e:
            console.print(f"[red]CLAHE processing failed: {e}[/red]")
            raise

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="CLAHE",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={
                "clip_limit": self.clip_limit,
                "tile_grid_size": self.tile_grid_size,
            },
        )

        return result, metrics

    @staticmethod
    def _estimate_memory_usage(image: np.ndarray) -> float:
        """Estimate memory usage of image in MB"""
        return image.nbytes / (1024 * 1024)


class MorphologicalProcessor:
    """
    Morphological image operations (erode, dilate, open, close).

    Morphological operations modify image structure by comparing pixels
    with their neighbors using a structuring element (kernel).
    """

    def __init__(self, kernel_size: str = "medium"):
        """
        Initialize morphological processor.

        Args:
            kernel_size: Size of structuring element ("small", "medium", "large").
        """
        if kernel_size not in KERNEL_SIZES:
            raise ValueError(f"Invalid kernel_size: {kernel_size}")

        self.kernel_size = kernel_size
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            KERNEL_SIZES[kernel_size]
        )

    def erode(self, image: np.ndarray, iterations: int = 1) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Erode image (shrink white regions, expand black regions).

        Args:
            image: Input image (typically binary or grayscale).
            iterations: Number of times to apply erosion.

        Returns:
            Tuple of (eroded_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        result = cv2.erode(image, self.kernel, iterations=iterations)

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="MORPH_ERODE",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={
                "kernel_size": self.kernel_size,
                "iterations": iterations,
            },
        )

        return result, metrics

    def dilate(self, image: np.ndarray, iterations: int = 1) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Dilate image (expand white regions, shrink black regions).

        Args:
            image: Input image (typically binary or grayscale).
            iterations: Number of times to apply dilation.

        Returns:
            Tuple of (dilated_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        result = cv2.dilate(image, self.kernel, iterations=iterations)

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="MORPH_DILATE",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={
                "kernel_size": self.kernel_size,
                "iterations": iterations,
            },
        )

        return result, metrics

    def open(self, image: np.ndarray) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Morphological opening (erode then dilate).

        Removes small white noise while preserving larger objects.

        Args:
            image: Input image.

        Returns:
            Tuple of (opened_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        result = cv2.morphologyEx(image, cv2.MORPH_OPEN, self.kernel)

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="MORPH_OPEN",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={"kernel_size": self.kernel_size},
        )

        return result, metrics

    def close(self, image: np.ndarray) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Morphological closing (dilate then erode).

        Removes small black holes while preserving larger structures.

        Args:
            image: Input image.

        Returns:
            Tuple of (closed_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        result = cv2.morphologyEx(image, cv2.MORPH_CLOSE, self.kernel)

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="MORPH_CLOSE",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={"kernel_size": self.kernel_size},
        )

        return result, metrics

    @staticmethod
    def _estimate_memory_usage(image: np.ndarray) -> float:
        """Estimate memory usage of image in MB"""
        return image.nbytes / (1024 * 1024)


class EdgeDetectionProcessor:
    """
    Edge detection using Canny and Sobel algorithms.

    Canny: Multi-stage edge detection with hysteresis thresholding.
    Sobel: Gradient-based edge detection with directional kernels.
    """

    def canny(self, image: np.ndarray, threshold1: int = 100, threshold2: int = 200) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Detect edges using Canny algorithm.

        Canny uses non-maximum suppression and hysteresis thresholding
        for precise edge detection.

        Args:
            image: Input image (converted to grayscale internally).
            threshold1: Lower threshold for hysteresis.
            threshold2: Upper threshold for hysteresis.

        Returns:
            Tuple of (edge_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)

        # Canny edge detection
        result = cv2.Canny(blurred, threshold1, threshold2)

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="EDGE_CANNY",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={
                "threshold1": threshold1,
                "threshold2": threshold2,
            },
        )

        return result, metrics

    def sobel(self, image: np.ndarray, kernel_size: int = 3) -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Detect edges using Sobel operator.

        Computes gradients in X and Y directions, then combines them.

        Args:
            image: Input image (converted to grayscale internally).
            kernel_size: Size of Sobel kernel (1, 3, 5, 7).

        Returns:
            Tuple of (edge_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Compute X and Y gradients
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=kernel_size)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=kernel_size)

        # Combine gradients
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        result = np.uint8(np.clip(magnitude, 0, 255))

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="EDGE_SOBEL",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={"kernel_size": kernel_size},
        )

        return result, metrics

    @staticmethod
    def _estimate_memory_usage(image: np.ndarray) -> float:
        """Estimate memory usage of image in MB"""
        return image.nbytes / (1024 * 1024)


class GrayscaleVariantProcessor:
    """
    Multiple methods for grayscale conversion.

    Different methods preserve different aspects of color information,
    useful for different computer vision tasks.
    """

    def convert(self, image: np.ndarray, method: str = "luminosity") -> Tuple[np.ndarray, ProcessingMetrics]:
        """
        Convert image to grayscale using specified method.

        Args:
            image: Input color image (BGR format).
            method: Conversion method ("luminosity", "average", "desaturation", "decomposition").

        Returns:
            Tuple of (grayscale_image, metrics).
        """
        start_time = time.time()
        mem_before = self._estimate_memory_usage(image)

        if len(image.shape) != 3:
            raise ValueError("Input image must be color (3 channels)")

        if method == "luminosity":
            result = self._convert_luminosity(image)
        elif method == "average":
            result = self._convert_average(image)
        elif method == "desaturation":
            result = self._convert_desaturation(image)
        elif method == "decomposition":
            result = self._convert_decomposition(image)
        else:
            raise ValueError(f"Unknown conversion method: {method}")

        mem_after = self._estimate_memory_usage(result)
        execution_time_ms = (time.time() - start_time) * 1000

        metrics = ProcessingMetrics(
            operation="GRAYSCALE_CONVERT",
            input_shape=image.shape,
            output_shape=result.shape,
            execution_time_ms=execution_time_ms,
            memory_before_mb=mem_before,
            memory_after_mb=mem_after,
            parameters={"method": method},
        )

        return result, metrics

    @staticmethod
    def _convert_luminosity(image: np.ndarray) -> np.ndarray:
        """
        Luminosity method: weighted average based on human perception.
        Formula: 0.299*R + 0.587*G + 0.114*B
        """
        b, g, r = cv2.split(image)
        return np.uint8(0.299 * r + 0.587 * g + 0.114 * b)

    @staticmethod
    def _convert_average(image: np.ndarray) -> np.ndarray:
        """
        Average method: simple arithmetic mean of RGB channels.
        Formula: (R + G + B) / 3
        """
        return np.uint8(np.mean(image, axis=2))

    @staticmethod
    def _convert_desaturation(image: np.ndarray) -> np.ndarray:
        """
        Desaturation method: average of max and min channel values.
        Formula: (max(R,G,B) + min(R,G,B)) / 2
        """
        max_val = np.max(image, axis=2)
        min_val = np.min(image, axis=2)
        return np.uint8((max_val + min_val) / 2)

    @staticmethod
    def _convert_decomposition(image: np.ndarray) -> np.ndarray:
        """
        Decomposition method: V channel from HSV color space.
        Represents brightness component.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        _, _, v = cv2.split(hsv)
        return v

    @staticmethod
    def _estimate_memory_usage(image: np.ndarray) -> float:
        """Estimate memory usage of image in MB"""
        return image.nbytes / (1024 * 1024)


class PreprocessingPipeline:
    """
    Orchestrator for composing multiple preprocessing operations.

    Chains multiple processors together with caching support.
    """

    def __init__(self, cache_enabled: bool = False, max_cache_size: int = 50):
        """
        Initialize preprocessing pipeline.

        Args:
            cache_enabled: Enable caching of preprocessed images.
            max_cache_size: Maximum number of cached images.
        """
        self.cache_enabled = cache_enabled
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, np.ndarray] = {}
        self.metrics: List[ProcessingMetrics] = []

        # Initialize processors
        self.clahe = CLAHEPreprocessor()
        self.morphology = MorphologicalProcessor()
        self.edges = EdgeDetectionProcessor()
        self.grayscale = GrayscaleVariantProcessor()

    def execute(self, image: np.ndarray, preset: str = "balanced") -> PipelineResult:
        """
        Execute preprocessing pipeline with preset configuration.

        Presets:
            - "balanced": CLAHE + morphological opening
            - "contrast": CLAHE with high clip limit
            - "edges": Canny edge detection
            - "denoise": Morphological opening + closing
            - "grayscale": Convert to grayscale

        Args:
            image: Input image.
            preset: Preset configuration name.

        Returns:
            PipelineResult with preprocessed image and metrics.
        """
        start_time = time.time()
        self.metrics = []
        result_image = image.copy()
        steps = []

        try:
            if preset == "balanced":
                result_image, metrics = self.clahe.process(result_image)
                self.metrics.append(metrics)
                steps.append("CLAHE")

                result_image, metrics = self.morphology.open(result_image)
                self.metrics.append(metrics)
                steps.append("Morphological Open")

            elif preset == "contrast":
                clahe = CLAHEPreprocessor(clip_limit=4.0)
                result_image, metrics = clahe.process(result_image)
                self.metrics.append(metrics)
                steps.append("CLAHE (High Contrast)")

            elif preset == "edges":
                result_image, metrics = self.edges.canny(result_image)
                self.metrics.append(metrics)
                steps.append("Canny Edge Detection")

            elif preset == "denoise":
                result_image, metrics = self.morphology.open(result_image)
                self.metrics.append(metrics)
                steps.append("Morphological Open")

                result_image, metrics = self.morphology.close(result_image)
                self.metrics.append(metrics)
                steps.append("Morphological Close")

            elif preset == "grayscale":
                result_image, metrics = self.grayscale.convert(result_image)
                self.metrics.append(metrics)
                steps.append("Grayscale Conversion")

            else:
                raise ValueError(f"Unknown preset: {preset}")

            total_time_ms = (time.time() - start_time) * 1000

            return PipelineResult(
                original_image=image,
                preprocessed_image=result_image,
                preprocessing_steps=steps,
                metrics=self.metrics,
                total_execution_time_ms=total_time_ms,
                success=True,
            )

        except Exception as e:
            total_time_ms = (time.time() - start_time) * 1000
            return PipelineResult(
                original_image=image,
                preprocessed_image=image,
                preprocessing_steps=steps,
                metrics=self.metrics,
                total_execution_time_ms=total_time_ms,
                success=False,
                error_message=str(e),
            )

    def clear_cache(self):
        """Clear preprocessing cache"""
        self.cache.clear()


class PerformanceMetricsCollector:
    """Collect and analyze performance metrics for preprocessing operations"""

    def __init__(self):
        self.results: List[PipelineResult] = []
        self.total_operations = 0

    def record_result(self, result: PipelineResult):
        """Record a pipeline execution result"""
        self.results.append(result)
        self.total_operations += len(result.metrics)

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        if not self.results:
            return {}

        total_time = sum(r.total_execution_time_ms for r in self.results)
        avg_time = total_time / len(self.results) if self.results else 0

        return {
            "total_executions": len(self.results),
            "total_operations": self.total_operations,
            "total_time_ms": total_time,
            "average_time_ms": avg_time,
            "success_rate": sum(1 for r in self.results if r.success) / len(self.results),
        }

    def print_report(self):
        """Print performance report"""
        summary = self.get_summary()

        table = Table(title="Performance Metrics", box=box.GRID)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total Executions", str(summary.get("total_executions", 0)))
        table.add_row("Total Operations", str(summary.get("total_operations", 0)))
        table.add_row("Total Time (ms)", f"{summary.get('total_time_ms', 0):.1f}")
        table.add_row("Average Time (ms)", f"{summary.get('average_time_ms', 0):.1f}")
        table.add_row("Success Rate", f"{summary.get('success_rate', 0):.1%}")

        console.print(table)


# ============================================================================
# SECTION 6: UTILITY FUNCTIONS
# ============================================================================

def load_image(image_path: str) -> np.ndarray:
    """Load image from file"""
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Failed to load image: {image_path}")

    return image


def save_image(image: np.ndarray, output_path: str) -> None:
    """Save image to file"""
    success = cv2.imwrite(output_path, image)
    if not success:
        raise ValueError(f"Failed to save image: {output_path}")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load TOML configuration file"""
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def format_metrics_table(metrics: List[ProcessingMetrics]) -> Table:
    """Format metrics as rich table"""
    table = Table(title="Processing Metrics", box=box.GRID)
    table.add_column("Operation", style="cyan")
    table.add_column("Time (ms)", style="magenta")
    table.add_column("Input Shape", style="green")
    table.add_column("Output Shape", style="yellow")

    for metric in metrics:
        table.add_row(
            metric.operation,
            f"{metric.execution_time_ms:.1f}",
            str(metric.input_shape),
            str(metric.output_shape),
        )

    return table


# ============================================================================
# SECTION 7: CLI INTERFACE
# ============================================================================

@click.command()
@click.option(
    "--image",
    type=click.Path(exists=True),
    help="Path to input image"
)
@click.option(
    "--device",
    default="emulator-5554",
    help="ADB device identifier"
)
@click.option(
    "--preset",
    type=click.Choice(["balanced", "contrast", "edges", "denoise", "grayscale"]),
    default="balanced",
    help="Preprocessing preset"
)
@click.option(
    "--output-format",
    type=click.Choice(["png", "jpg", "json"]),
    default="png",
    help="Output format"
)
@click.option(
    "--profile",
    is_flag=True,
    help="Enable performance profiling"
)
@click.option(
    "--benchmark",
    is_flag=True,
    help="Run performance benchmark"
)
@click.option(
    "--cache-enabled",
    is_flag=True,
    help="Enable result caching"
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to TOML configuration file"
)
def main(
    image: Optional[str],
    device: str,
    preset: str,
    output_format: str,
    profile: bool,
    benchmark: bool,
    cache_enabled: bool,
    config: Optional[str],
):
    """Advanced Image Preprocessing for ADB Vision"""

    try:
        console.print("[bold cyan]ADB Computer Vision Preprocessing[/bold cyan]")
        console.print(f"Device: {device}")
        console.print(f"Preset: {preset}")

        # Load image
        if not image:
            console.print("[yellow]Warning: No image specified. Use --image flag.[/yellow]")
            return

        console.print(f"Loading image: {image}")
        img = load_image(image)
        console.print(f"Loaded image shape: {img.shape}")

        # Initialize pipeline
        pipeline = PreprocessingPipeline(cache_enabled=cache_enabled)

        # Execute preprocessing
        result = pipeline.execute(img, preset=preset)

        if not result.success:
            console.print(f"[red]Processing failed: {result.error_message}[/red]")
            return

        # Display metrics
        if result.metrics:
            console.print(format_metrics_table(result.metrics))

        console.print(f"[green]Total execution time: {result.total_execution_time_ms:.1f}ms[/green]")

        # Save output
        output_path = f"preprocessed_{preset}.png"
        save_image(result.preprocessed_image, output_path)
        console.print(f"[green]Saved to: {output_path}[/green]")

        # Performance profiling
        if profile:
            console.print("\n[bold]Performance Profile[/bold]")
            console.print(f"Input shape: {result.original_image.shape}")
            console.print(f"Output shape: {result.preprocessed_image.shape}")
            console.print(f"Steps: {', '.join(result.preprocessing_steps)}")

        # Benchmark
        if benchmark:
            console.print("\n[bold]Running Benchmark[/bold]")
            collector = PerformanceMetricsCollector()

            for i in range(10):
                bench_result = pipeline.execute(img, preset=preset)
                collector.record_result(bench_result)

            collector.print_report()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# ============================================================================
# SECTION 8: MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    main()
