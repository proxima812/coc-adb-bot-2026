#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "opencv-python>=4.8.0",
#     "numpy>=1.24.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""
ADB Template Multi-Resolution Matcher - Density-independent UI detection.

This script implements multi-scale template matching for handling UI detection
across different device resolutions and densities without creating separate
templates for each resolution.

Purpose:
    - Match templates at multiple scales (0.8x to 1.2x) simultaneously
    - Support resolution-independent UI detection
    - Reduce template creation overhead for multi-device deployment
    - Provide fallback chain: multi-scale → single-scale → feature matching

Features:
    - Image pyramid generation with caching
    - Multi-scale template matching with confidence scoring
    - Fallback chain for robust detection
    - Performance profiling and cache statistics
    - YAML/JSON export for integration pipelines
    - Resolution profile configuration

Usage:
    # Basic matching
    python adb_template_multiresolution.py --template button.png --screenshot current.png

    # With custom scales
    python adb_template_multiresolution.py \\
        --template button.png --screenshot current.png \\
        --scales 0.8 0.9 1.0 1.1 1.2 \\
        --threshold 0.75

    # YAML output for integration
    python adb_template_multiresolution.py \\
        --template button.png --screenshot current.png \\
        --toon

    # Verbose with debug visualization
    python adb_template_multiresolution.py \\
        --template button.png --screenshot current.png \\
        --verbose --save-debug output.png

Exit Codes:
    0: Match found and reported
    1: No match found (below threshold)
    2: Invalid template or screenshot path
    3: Configuration error
    4: OpenCV processing error

Author: MoAI-ADK Domain ADB Expert
Version: 1.0.0
License: MIT
"""

# ============================================================================
# SECTION 1: IMPORTS & CONFIGURATION
# ============================================================================

import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

import click
import cv2
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# ============================================================================
# SECTION 2: DATA STRUCTURES
# ============================================================================


@dataclass
class MatchResult:
    """Result from template matching operation"""
    x: int
    y: int
    confidence: float
    scale: float
    method: str  # multi_scale, single_scale, feature_matching
    execution_time_ms: float
    template_size: tuple = field(default_factory=tuple)
    screenshot_size: tuple = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class CacheStats:
    """Cache performance statistics"""
    hits: int = 0
    misses: int = 0
    total_operations: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage"""
        if self.total_operations == 0:
            return 0.0
        return self.hits / self.total_operations


# ============================================================================
# SECTION 3: TEMPLATE SCALER
# ============================================================================


class TemplateScaler:
    """Generate and cache template pyramids at multiple scales"""

    def __init__(self, scales: List[float] = None, max_cache_size: int = 50):
        """
        Initialize scaler with scale factors

        Args:
            scales: List of scale factors (default: [0.8, 0.9, 1.0, 1.1, 1.2])
            max_cache_size: Maximum number of pyramids to cache
        """
        self.scales = scales or [0.8, 0.9, 1.0, 1.1, 1.2]
        self.max_cache_size = max_cache_size
        self.pyramid_cache: Dict[str, Dict[float, np.ndarray]] = {}
        self.stats = CacheStats()

    def generate_pyramid(
        self, template: np.ndarray, template_id: str
    ) -> Dict[float, np.ndarray]:
        """
        Generate image pyramid for template at multiple scales

        Args:
            template: Input template image
            template_id: Unique identifier for caching

        Returns:
            Dictionary mapping scale factor to scaled template
        """
        # Check cache first
        if template_id in self.pyramid_cache:
            self.stats.hits += 1
            self.stats.total_operations += 1
            return self.pyramid_cache[template_id]

        self.stats.misses += 1
        self.stats.total_operations += 1

        pyramid: Dict[float, np.ndarray] = {}

        for scale in self.scales:
            # Calculate new dimensions
            height = int(template.shape[0] * scale)
            width = int(template.shape[1] * scale)

            # Skip degenerate cases
            if height > 2 and width > 2:
                # Use linear interpolation for quality/speed balance
                scaled = cv2.resize(
                    template, (width, height), interpolation=cv2.INTER_LINEAR
                )
                pyramid[scale] = scaled

        # Cache pyramid with LRU eviction
        if len(self.pyramid_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.pyramid_cache))
            del self.pyramid_cache[oldest_key]

        self.pyramid_cache[template_id] = pyramid
        return pyramid

    def clear_cache(self):
        """Clear pyramid cache and reset statistics"""
        self.pyramid_cache.clear()
        self.stats = CacheStats()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "total": self.stats.total_operations,
            "hit_rate": self.stats.hit_rate,
            "cached_pyramids": len(self.pyramid_cache),
        }


# ============================================================================
# SECTION 4: MULTI-SCALE MATCHER
# ============================================================================


class MultiScaleMatcher:
    """Match templates at multiple scales with intelligent fallback chain"""

    def __init__(
        self,
        scales: List[float] = None,
        threshold: float = 0.7,
        method: int = cv2.TM_CCOEFF_NORMED,
    ):
        """
        Initialize multi-scale matcher

        Args:
            scales: List of scale factors
            threshold: Confidence threshold for matches (0.0-1.0)
            method: OpenCV template matching method
        """
        self.scaler = TemplateScaler(scales)
        self.threshold = threshold
        self.method = method
        self.execution_stats: List[Dict[str, Any]] = []

    def match(
        self, screenshot: np.ndarray, template: np.ndarray, template_id: str = "template"
    ) -> Optional[MatchResult]:
        """
        Match template at multiple scales with fallback chain

        Fallback chain:
        1. Multi-scale matching (0.8x-1.2x)
        2. Single-scale matching (1.0x)
        3. Feature matching (ORB)

        Args:
            screenshot: Screenshot image to search
            template: Template image to find
            template_id: Unique identifier for caching

        Returns:
            MatchResult if match found, None otherwise
        """
        start_time = time.time()

        # Step 1: Multi-scale matching
        result = self._match_multi_scale(screenshot, template, template_id)
        if result:
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        # Step 2: Single-scale fallback
        result = self._match_single_scale(screenshot, template, template_id)
        if result:
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        # Step 3: Feature matching fallback
        result = self._match_features(screenshot, template)
        if result:
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        return None

    def _match_multi_scale(
        self, screenshot: np.ndarray, template: np.ndarray, template_id: str
    ) -> Optional[MatchResult]:
        """Try matching at multiple scales"""
        pyramid = self.scaler.generate_pyramid(template, template_id)
        best_result = None
        best_confidence = 0.0

        for scale, scaled_template in pyramid.items():
            # Skip scales larger than screenshot
            if (
                scaled_template.shape[0] > screenshot.shape[0]
                or scaled_template.shape[1] > screenshot.shape[1]
            ):
                continue

            # Match at this scale
            try:
                result = cv2.matchTemplate(screenshot, scaled_template, self.method)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)

                if max_val > best_confidence:
                    best_confidence = max_val
                    h, w = scaled_template.shape[:2]
                    center_x = max_loc[0] + w // 2
                    center_y = max_loc[1] + h // 2

                    best_result = MatchResult(
                        x=center_x,
                        y=center_y,
                        confidence=float(best_confidence),
                        scale=scale,
                        method="multi_scale",
                        execution_time_ms=0,
                        template_size=template.shape[:2],
                        screenshot_size=screenshot.shape[:2],
                    )
            except Exception:
                continue

        # Return only if confidence exceeds threshold
        if best_result and best_result.confidence > self.threshold:
            return best_result

        return None

    def _match_single_scale(
        self, screenshot: np.ndarray, template: np.ndarray, template_id: str
    ) -> Optional[MatchResult]:
        """Fallback: Match template at 1.0x scale only"""
        if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
            return None

        try:
            result = cv2.matchTemplate(screenshot, template, self.method)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > self.threshold:
                h, w = template.shape[:2]
                return MatchResult(
                    x=max_loc[0] + w // 2,
                    y=max_loc[1] + h // 2,
                    confidence=float(max_val),
                    scale=1.0,
                    method="single_scale",
                    execution_time_ms=0,
                    template_size=template.shape[:2],
                    screenshot_size=screenshot.shape[:2],
                )
        except Exception:
            pass

        return None

    def _match_features(self, screenshot: np.ndarray, template: np.ndarray) -> Optional[MatchResult]:
        """Fallback: Match using ORB features (lightweight alternative to SIFT)"""
        try:
            orb = cv2.ORB_create(nfeatures=500)

            kp1, des1 = orb.detectAndCompute(screenshot, None)
            kp2, des2 = orb.detectAndCompute(template, None)

            if des1 is None or des2 is None or len(kp1) < 5:
                return None

            # Match features using Hamming distance
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des2, des1)
            matches = sorted(matches, key=lambda x: x.distance)

            # Need at least 10 good matches
            if len(matches) >= 10:
                positions = [kp1[m.trainIdx].pt for m in matches[:10]]
                avg_x = int(sum(x for x, y in positions) / len(positions))
                avg_y = int(sum(y for x, y in positions) / len(positions))

                return MatchResult(
                    x=avg_x,
                    y=avg_y,
                    confidence=0.95,
                    scale=1.0,
                    method="feature_matching",
                    execution_time_ms=0,
                    template_size=template.shape[:2],
                    screenshot_size=screenshot.shape[:2],
                )
        except Exception:
            pass

        return None

    def get_scaler_stats(self) -> Dict[str, Any]:
        """Get scaler cache statistics"""
        return self.scaler.get_stats()


# ============================================================================
# SECTION 5: CONFIGURATION LOADER
# ============================================================================


class ConfigLoader:
    """Load and validate multi-scale matching configuration"""

    DEFAULT_CONFIG = {
        "scales": [0.8, 0.9, 1.0, 1.1, 1.2],
        "threshold": 0.7,
        "method": "TM_CCOEFF_NORMED",
        "max_cache_size": 50,
    }

    @classmethod
    def load_from_dict(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load and validate configuration from dictionary"""
        result = cls.DEFAULT_CONFIG.copy()
        result.update(config)

        # Validate scales
        if not isinstance(result["scales"], list):
            raise ValueError("scales must be a list")
        if not all(isinstance(s, (int, float)) for s in result["scales"]):
            raise ValueError("all scales must be numeric")
        if not all(0.5 <= s <= 2.0 for s in result["scales"]):
            raise ValueError("scales must be between 0.5 and 2.0")

        # Validate threshold
        if not 0.0 <= result["threshold"] <= 1.0:
            raise ValueError("threshold must be between 0.0 and 1.0")

        return result

    @classmethod
    def get_default(cls) -> Dict[str, Any]:
        """Get default configuration"""
        return cls.DEFAULT_CONFIG.copy()


# ============================================================================
# SECTION 6: CLI INTERFACE
# ============================================================================


@click.command()
@click.option(
    "--template",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to template image",
)
@click.option(
    "--screenshot",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to screenshot image",
)
@click.option(
    "--scales",
    multiple=True,
    type=float,
    default=[0.8, 0.9, 1.0, 1.1, 1.2],
    help="Scale factors to try",
)
@click.option(
    "--threshold",
    type=float,
    default=0.7,
    help="Confidence threshold (0.0-1.0)",
)
@click.option(
    "--toon",
    is_flag=True,
    help="Output as YAML (human-readable)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output with debug info",
)
@click.option(
    "--save-debug",
    type=click.Path(path_type=Path),
    help="Save debug visualization image",
)
def main(
    template: Path,
    screenshot: Path,
    scales: tuple,
    threshold: float,
    toon: bool,
    output_json: bool,
    verbose: bool,
    save_debug: Optional[Path],
) -> None:
    """
    Match template in screenshot using multi-scale template matching.

    Detects UI elements across different device resolutions and densities
    by trying multiple scale factors simultaneously.
    """
    console = Console()

    try:
        # Load images
        template_img = cv2.imread(str(template))
        screenshot_img = cv2.imread(str(screenshot))

        if template_img is None or screenshot_img is None:
            console.print("[red]Error: Could not load images[/red]")
            sys.exit(2)

        # Convert to list and validate scales
        scale_list = list(scales) if scales else [0.8, 0.9, 1.0, 1.1, 1.2]
        if not scale_list:
            console.print("[red]Error: No scales provided[/red]")
            sys.exit(3)

        # Initialize matcher
        matcher = MultiScaleMatcher(
            scales=scale_list,
            threshold=threshold,
        )

        # Perform matching
        result = matcher.match(screenshot_img, template_img, "cli_template")

        # Output results
        if result:
            if output_json:
                output = {
                    "status": "match_found",
                    "result": result.to_dict(),
                    "cache_stats": matcher.get_scaler_stats(),
                }
                click.echo(json.dumps(output, indent=2))
            elif toon:
                output = {
                    "status": "match_found",
                    "match": {
                        "x": result.x,
                        "y": result.y,
                        "confidence": f"{result.confidence:.2%}",
                        "scale": f"{result.scale}x",
                        "method": result.method,
                        "time_ms": f"{result.execution_time_ms:.1f}",
                    },
                    "cache": matcher.get_scaler_stats(),
                }
                import yaml
                click.echo(yaml.dump(output, default_flow_style=False))
            else:
                # Rich formatted output
                if verbose:
                    console.print(
                        Panel(
                            f"[bold green]Match Found![/bold green]\n"
                            f"Position: ({result.x}, {result.y})\n"
                            f"Confidence: {result.confidence:.2%}\n"
                            f"Scale: {result.scale}x\n"
                            f"Method: {result.method}\n"
                            f"Execution: {result.execution_time_ms:.1f}ms",
                            title="Match Result",
                        )
                    )

                    # Cache stats
                    stats = matcher.get_scaler_stats()
                    table = Table(title="Cache Statistics")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    for key, value in stats.items():
                        if isinstance(value, float):
                            table.add_row(key, f"{value:.2%}")
                        else:
                            table.add_row(key, str(value))
                    console.print(table)
                else:
                    click.echo(
                        f"MATCH {result.x},{result.y} {result.confidence:.2%} {result.scale}x {result.method}"
                    )

            # Save debug visualization if requested
            if save_debug:
                debug_img = screenshot_img.copy()
                # Draw match location
                h, w = template_img.shape[:2]
                cv2.rectangle(
                    debug_img,
                    (result.x - w // 2, result.y - h // 2),
                    (result.x + w // 2, result.y + h // 2),
                    (0, 255, 0),
                    2,
                )
                cv2.circle(debug_img, (result.x, result.y), 5, (0, 0, 255), -1)
                cv2.imwrite(str(save_debug), debug_img)
                if verbose:
                    console.print(f"[green]Debug image saved to {save_debug}[/green]")

            sys.exit(0)
        else:
            if output_json:
                output = {
                    "status": "no_match",
                    "threshold": threshold,
                    "scales_tried": scale_list,
                    "cache_stats": matcher.get_scaler_stats(),
                }
                click.echo(json.dumps(output, indent=2))
            elif toon:
                output = {
                    "status": "no_match",
                    "threshold": str(threshold),
                    "scales_tried": scale_list,
                    "cache": matcher.get_scaler_stats(),
                }
                import yaml
                click.echo(yaml.dump(output, default_flow_style=False))
            else:
                if verbose:
                    console.print(
                        Panel(
                            "[red]No match found[/red]",
                            title="Match Result",
                        )
                    )
                else:
                    click.echo("NO_MATCH")

            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(4)


# ============================================================================
# SECTION 7: ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    main()
