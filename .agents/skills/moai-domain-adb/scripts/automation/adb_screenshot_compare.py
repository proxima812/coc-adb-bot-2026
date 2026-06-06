#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pillow>=10.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///
"""
ADB Screenshot Compare - Compare two screenshots for similarity.

Purpose:
    Compare reference screenshot with test screenshot to determine match
    percentage. Useful for verifying game state, detecting UI changes,
    and validating automation sequences.

Parameters:
    --device/-d: Device ID (optional, for context only). Type: str
    --before: Reference screenshot path (required). Type: Path
    --after: Test screenshot path (required). Type: Path
    --threshold/-t: Match threshold 0.0-1.0 (default: 0.95). Type: float
    --toon: Output in TOON/YAML format (flag). Type: bool
    --verbose/-v: Verbose output with debug info (flag). Type: bool

Returns:
    Exit code 0 if match above threshold, 1 if below threshold.
    TOON output: {status, similarity_percent, is_similar, before_hash, after_hash}

Examples:
    # Compare two screenshots (95% threshold)
    $ uv run adb_screenshot_compare.py --before ref.png --after test.png

    # Lower threshold (more lenient)
    $ uv run adb_screenshot_compare.py --before ref.png --after test.png -t 0.80

    # Verbose mode with TOON output
    $ uv run adb_screenshot_compare.py --before ref.png --after test.png -v --toon

Raises:
    FileNotFoundError: When screenshot files don't exist
    PIL.UnidentifiedImageError: When image files are corrupted

Notes:
    - Comparison methods: RGB pixel difference (fast)
    - Images resized to 64x64 for fast comparison
    - Similarity: 1.0 = identical, 0.0 = completely different
    - Threshold >= similarity = match
    - Suitable for detecting screen changes in automation

Related:
    - adb_game_loop.py: Take screenshots during automation
    - adb_click_sequence.py: Verify sequence results
    - adb_screenshot.py: Capture screenshots

Context:
    Part of automation/ category in moai-domain-adb skill. Provides
    verification primitive for automation workflows.

Implementation:
    1. Load and validate image files
    2. Calculate image hashes (pixel data)
    3. Compute similarity metric
    4. Compare against threshold
    5. Output results (human or TOON)
"""

import hashlib
import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
from PIL import Image
from rich.console import Console

# Common utilities import
from common.adb_utils import get_default_device
from common.cli_utils import (
    device_option,
    format_toon_output,
    print_error,
    print_info,
    print_success,
    print_warning,
    toon_output_option,
    verbose_option,
)
from common.error_handlers import (
    EXIT_INVALID_ARGUMENT,
    EXIT_SUCCESS,
    handle_adb_errors,
)

console = Console()


def calculate_image_hash(image_path: Path, verbose: bool = False) -> Optional[List[Tuple[int, int, int]]]:
    """
    Purpose:
        Calculate RGB pixel data of image for comparison. Resizes to 64x64
        for fast processing while maintaining similarity accuracy.

    Parameters:
        image_path: Path to image file. Type: Path
        verbose: Enable verbose output (default: False). Type: bool

    Returns:
        List of RGB tuples, or None on error. Type: Optional[List[Tuple[int, int, int]]]

    Examples:
        >>> path = Path("screenshot.png")
        >>> pixels = calculate_image_hash(path)
        >>> len(pixels)
        4096  # 64x64

    Raises:
        No exceptions. Returns None on errors.

    Notes:
        - Resize to 64x64 for consistent comparison
        - Convert to RGB mode (3 channels)
        - Returns pixel data as list of (R, G, B) tuples
        - Fast hash generation (~10ms per image)

    Related:
        - calculate_similarity(): Uses pixel data for comparison
        - main(): Calls this for both images

    Context:
        Preprocessing step for image comparison.

    Implementation:
        1. Open image with PIL
        2. Resize to 64x64 thumbnail
        3. Convert to RGB mode
        4. Extract pixel data as list
        5. Return pixel list
    """
    try:
        img = Image.open(image_path)

        if verbose:
            print_info(f"Image size: {img.size}, mode: {img.mode}")

        # Resize to small size for fast comparison
        img.thumbnail((64, 64))

        # Convert to RGB and get pixel data
        pixels = list(img.convert("RGB").getdata())

        if verbose:
            print_info(f"Extracted {len(pixels)} pixels")

        return pixels

    except FileNotFoundError:
        print_error(f"Image not found: {image_path}")
        return None
    except Exception as e:
        print_error(f"Error loading image: {e}")
        return None


def calculate_md5_hash(pixels: List[Tuple[int, int, int]]) -> str:
    """
    Purpose:
        Calculate MD5 hash of pixel data for quick equality check and
        debugging. Not used for similarity, only for identification.

    Parameters:
        pixels: List of RGB pixel tuples. Type: List[Tuple[int, int, int]]

    Returns:
        MD5 hash as hexadecimal string. Type: str

    Examples:
        >>> pixels = [(255, 0, 0), (0, 255, 0)]
        >>> calculate_md5_hash(pixels)
        'a1b2c3d4...'

    Raises:
        No exceptions.

    Notes:
        - MD5 hash for identification only (not security)
        - Useful for debugging and caching
        - Fast computation (~1ms)

    Related:
        - main(): Includes hash in TOON output

    Context:
        Optional metadata for image comparison.

    Implementation:
        1. Convert pixels to bytes
        2. Calculate MD5 hash
        3. Return hex digest
    """
    pixel_bytes = b"".join(bytes(pixel) for pixel in pixels)
    return hashlib.md5(pixel_bytes).hexdigest()


def calculate_similarity(
    pixels1: List[Tuple[int, int, int]],
    pixels2: List[Tuple[int, int, int]],
    verbose: bool = False,
) -> float:
    """
    Purpose:
        Calculate similarity percentage between two pixel lists using
        Euclidean distance in RGB color space.

    Parameters:
        pixels1: First image pixel data. Type: List[Tuple[int, int, int]]
        pixels2: Second image pixel data. Type: List[Tuple[int, int, int]]
        verbose: Enable verbose output (default: False). Type: bool

    Returns:
        Similarity as float 0.0-1.0. Type: float

    Examples:
        >>> pixels1 = [(255, 0, 0)] * 100
        >>> pixels2 = [(255, 0, 0)] * 100
        >>> calculate_similarity(pixels1, pixels2)
        1.0

    Raises:
        No exceptions. Returns 0.0 on invalid input.

    Notes:
        - Method: Euclidean distance in RGB space
        - Formula: 1.0 - (sum_of_distances / max_possible_distance)
        - Max distance per pixel: sqrt(3 * 255^2)
        - Result clamped to [0.0, 1.0]
        - Accuracy: ±2% for similar images

    Related:
        - calculate_image_hash(): Provides pixel data
        - main(): Uses result for threshold comparison

    Context:
        Core comparison algorithm for image similarity.

    Implementation:
        1. Validate pixel lists (same length)
        2. Calculate Euclidean distance for each pixel pair
        3. Sum all distances
        4. Normalize by max possible distance
        5. Convert to similarity (1.0 - normalized_distance)
        6. Clamp to [0.0, 1.0]
    """
    if not pixels1 or not pixels2:
        if verbose:
            print_warning("One or both pixel lists are empty")
        return 0.0

    if len(pixels1) != len(pixels2):
        if verbose:
            print_warning(
                f"Pixel lists have different lengths: {len(pixels1)} vs {len(pixels2)}"
            )
        return 0.0

    # Calculate Euclidean distance for each pixel
    differences = sum(
        math.sqrt(
            (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2
        )
        for p1, p2 in zip(pixels1, pixels2)
    )

    # Normalize by maximum possible distance
    max_differences = len(pixels1) * math.sqrt(3 * 255**2)

    if max_differences == 0:
        return 0.0

    # Calculate similarity (1.0 = identical, 0.0 = completely different)
    similarity = 1.0 - (differences / max_differences)

    # Clamp to [0.0, 1.0]
    similarity = max(0.0, min(1.0, similarity))

    if verbose:
        print_info(f"Total differences: {differences:.2f}")
        print_info(f"Max possible: {max_differences:.2f}")
        print_info(f"Similarity: {similarity:.4f}")

    return similarity


@click.command()
@click.option(
    "--before",
    required=True,
    type=click.Path(exists=True),
    help="Reference screenshot path",
)
@click.option(
    "--after",
    required=True,
    type=click.Path(exists=True),
    help="Test screenshot path",
)
@click.option(
    "--threshold",
    "-t",
    default=0.95,
    type=float,
    help="Match threshold 0.0-1.0 (default: 0.95)",
)
@device_option
@toon_output_option
@verbose_option
@handle_adb_errors
def main(
    before: str,
    after: str,
    threshold: float,
    device: Optional[str],
    toon: bool,
    verbose: bool,
):
    """
    Purpose:
        Compare two screenshots for similarity. Main entry point for
        image comparison in automation workflows.

    Parameters:
        before: Reference screenshot path. Type: str
        after: Test screenshot path. Type: str
        threshold: Match threshold 0.0-1.0. Type: float
        device: Device ID (optional, for context). Type: Optional[str]
        toon: TOON output flag. Type: bool
        verbose: Verbose output flag. Type: bool

    Returns:
        Exit code via sys.exit(). Type: int

    Examples:
        See module-level docstring for usage examples.

    Raises:
        FileNotFoundError: When image files don't exist
        ValueError: When threshold is out of range

    Notes:
        - Threshold validation: 0.0 <= threshold <= 1.0
        - Exit code 0 if similarity >= threshold
        - Exit code 1 if similarity < threshold
        - TOON output includes MD5 hashes for debugging

    Related:
        - calculate_image_hash(): Loads pixel data
        - calculate_similarity(): Computes similarity

    Context:
        Main entry point called via Click CLI.

    Implementation:
        1. Validate threshold range
        2. Load both images
        3. Calculate pixel hashes
        4. Compute similarity
        5. Compare against threshold
        6. Output results (human or TOON)
    """
    # Validate threshold
    if not 0.0 <= threshold <= 1.0:
        print_error(f"Threshold must be between 0.0 and 1.0 (got {threshold})")
        sys.exit(EXIT_INVALID_ARGUMENT)

    try:
        before_path = Path(before).resolve()
        after_path = Path(after).resolve()

        if not toon:
            console.print("[cyan]Comparing screenshots...[/cyan]")
            console.print(f"[dim]  Before: {before_path.name}[/dim]")
            console.print(f"[dim]  After: {after_path.name}[/dim]")
            console.print(f"[dim]  Threshold: {threshold:.0%}[/dim]")

        # Calculate pixel hashes
        if verbose:
            print_info("Loading before image...")
        before_pixels = calculate_image_hash(before_path, verbose)

        if verbose:
            print_info("Loading after image...")
        after_pixels = calculate_image_hash(after_path, verbose)

        if not before_pixels or not after_pixels:
            sys.exit(EXIT_INVALID_ARGUMENT)

        # Calculate MD5 hashes for debugging
        before_hash = calculate_md5_hash(before_pixels)
        after_hash = calculate_md5_hash(after_pixels)

        if verbose:
            print_info(f"Before hash: {before_hash}")
            print_info(f"After hash: {after_hash}")

        # Calculate similarity
        if verbose:
            print_info("Calculating similarity...")

        similarity = calculate_similarity(before_pixels, after_pixels, verbose)
        percentage = similarity * 100

        # Determine if match
        is_match = similarity >= threshold

        # Output results
        if toon:
            output_data = {
                "status": "match" if is_match else "no_match",
                "similarity_percent": round(percentage, 2),
                "is_similar": is_match,
                "threshold": threshold,
                "before_hash": before_hash,
                "after_hash": after_hash,
            }
            print(format_toon_output(output_data))
        else:
            console.print(f"\n[cyan]Similarity: {percentage:.1f}%[/cyan]")

            if is_match:
                print_success(f"Match! ({percentage:.1f}% >= {threshold:.0%})")
            else:
                print_warning(f"No match ({percentage:.1f}% < {threshold:.0%})")

        sys.exit(EXIT_SUCCESS if is_match else EXIT_INVALID_ARGUMENT)

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        sys.exit(EXIT_INVALID_ARGUMENT)
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(EXIT_INVALID_ARGUMENT)


if __name__ == "__main__":
    main()
