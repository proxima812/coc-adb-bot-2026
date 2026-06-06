#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "opencv-python>=4.5.0",
#     "pillow>=9.0.0",
#     "numpy>=1.24.0",
# ]
# ///
"""
ADB Template Creator - Create action templates from screenshots for template matching.

This script creates image templates from screenshots by cropping specific regions.
Templates are used for template matching in ADB automation to detect UI elements.

Purpose:
    - Crop specific regions from screenshots to create templates
    - Save templates with metadata for automation systems
    - Validate region coordinates and dimensions
    - Preview templates before saving
    - Generate JSON metadata with dimensions and coordinates

Features:
    - Multiple region format support (x1,y1,x2,y2 or x,y,width,height)
    - Template validation and preview
    - Automatic dimension calculation
    - Metadata JSON generation
    - Zero-context design (no external dependencies)
    - Error handling for invalid regions and missing files

Usage:
    # Create template from screenshot region
    python adb_template_creator.py --screenshot screenshot.png --region "100,200,300,400" --name button_ok

    # Use x,y,width,height format
    python adb_template_creator.py --screenshot screenshot.png --region "100,200,200,200" --name icon_settings --format xywh

    # Preview before saving
    python adb_template_creator.py --screenshot screenshot.png --region "100,200,300,400" --name button_ok --preview

    # Custom output directory
    python adb_template_creator.py --screenshot screenshot.png --region "100,200,300,400" --name button_ok --output-dir templates/

Exit Codes:
    0: Success
    1: Screenshot not found
    2: Invalid region format
    3: Region out of bounds
    4: File write error

Author: MoAI-ADK Domain ADB Expert
Version: 1.0.0
License: MIT
"""

# ============================================================================
# SECTION 2: IMPORTS
# ============================================================================

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import click
import cv2
import numpy as np
from PIL import Image

# ============================================================================
# SECTION 3: CONFIGURATION
# ============================================================================

# Default output directory for templates
DEFAULT_OUTPUT_DIR = Path("templates")

# Supported image formats
SUPPORTED_FORMATS = [".png", ".jpg", ".jpeg", ".bmp"]

# Maximum preview window size (width, height)
MAX_PREVIEW_SIZE = (800, 600)

# ============================================================================
# SECTION 4: ROOT DETECTION
# ============================================================================

def detect_project_root() -> Path:
    """
    Detect project root directory.

    Returns:
        Path: Absolute path to project root directory.

    Note:
        For zero-context design, this script assumes execution from
        within the project structure. Falls back to current directory.
    """
    current = Path.cwd()

    # Look for common project markers
    markers = [".git", "pyproject.toml", "package.json", ".moai"]

    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent

    return Path.cwd()


PROJECT_ROOT = detect_project_root()

# ============================================================================
# SECTION 5: DATA MODELS
# ============================================================================

@dataclass
class Region:
    """
    Region coordinates for template extraction.

    Attributes:
        x1: Top-left X coordinate
        y1: Top-left Y coordinate
        x2: Bottom-right X coordinate
        y2: Bottom-right Y coordinate
        width: Region width (calculated)
        height: Region height (calculated)
    """

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Calculate region width."""
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Calculate region height."""
        return self.y2 - self.y1

    def validate(self, img_width: int, img_height: int) -> None:
        """
        Validate region is within image bounds.

        Args:
            img_width: Image width in pixels
            img_height: Image height in pixels

        Raises:
            InvalidRegionError: If region is outside image bounds
        """
        if self.x1 < 0 or self.y1 < 0:
            raise InvalidRegionError(f"Region coordinates cannot be negative: ({self.x1}, {self.y1})")

        if self.x2 > img_width or self.y2 > img_height:
            raise InvalidRegionError(
                f"Region ({self.x1}, {self.y1}, {self.x2}, {self.y2}) "
                f"exceeds image bounds ({img_width}x{img_height})"
            )

        if self.width <= 0 or self.height <= 0:
            raise InvalidRegionError(
                f"Region must have positive dimensions: width={self.width}, height={self.height}"
            )

    def to_dict(self) -> dict:
        """Convert region to dictionary format."""
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class TemplateMetadata:
    """
    Template metadata for automation systems.

    Attributes:
        name: Template name
        source_screenshot: Original screenshot filename
        region: Cropped region coordinates
        dimensions: Template dimensions (width, height)
        template_path: Path to saved template file
        format: Image format (png, jpg, etc.)
    """

    name: str
    source_screenshot: str
    region: Region
    dimensions: Tuple[int, int]
    template_path: str
    format: str = "png"

    def to_dict(self) -> dict:
        """Convert metadata to dictionary format."""
        return {
            "name": self.name,
            "source_screenshot": self.source_screenshot,
            "region": self.region.to_dict(),
            "dimensions": {
                "width": self.dimensions[0],
                "height": self.dimensions[1],
            },
            "template_path": self.template_path,
            "format": self.format,
        }


# ============================================================================
# SECTION 6: CUSTOM EXCEPTIONS
# ============================================================================

class TemplateCreatorError(Exception):
    """Base exception for template creator errors."""
    pass


class ScreenshotNotFoundError(TemplateCreatorError):
    """Raised when screenshot file is not found."""
    pass


class InvalidRegionError(TemplateCreatorError):
    """Raised when region format or coordinates are invalid."""
    pass


class FileWriteError(TemplateCreatorError):
    """Raised when template or metadata cannot be saved."""
    pass


# ============================================================================
# SECTION 7: CORE LOGIC
# ============================================================================

def parse_region(region_str: str, format_type: str = "xyxy") -> Region:
    """
    Parse region string into Region object.

    Args:
        region_str: Region string in format "x1,y1,x2,y2" or "x,y,width,height"
        format_type: Format type - "xyxy" or "xywh"

    Returns:
        Region: Parsed region object

    Raises:
        InvalidRegionError: If region format is invalid

    Examples:
        >>> parse_region("100,200,300,400", "xyxy")
        Region(x1=100, y1=200, x2=300, y2=400)

        >>> parse_region("100,200,200,200", "xywh")
        Region(x1=100, y1=200, x2=300, y2=400)
    """
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) != 4:
            raise ValueError("Region must have exactly 4 values")

        if format_type == "xyxy":
            x1, y1, x2, y2 = parts
        elif format_type == "xywh":
            x, y, width, height = parts
            x1, y1 = x, y
            x2, y2 = x + width, y + height
        else:
            raise InvalidRegionError(f"Unknown format type: {format_type}")

        return Region(x1=x1, y1=y1, x2=x2, y2=y2)

    except ValueError as e:
        raise InvalidRegionError(
            f"Invalid region format '{region_str}'. "
            f"Expected format: 'x1,y1,x2,y2' or 'x,y,width,height'"
        ) from e


def load_screenshot(screenshot_path: Path) -> np.ndarray:
    """
    Load screenshot image from file.

    Args:
        screenshot_path: Path to screenshot file

    Returns:
        np.ndarray: Loaded image in BGR format (OpenCV format)

    Raises:
        ScreenshotNotFoundError: If screenshot file doesn't exist
        TemplateCreatorError: If image cannot be loaded
    """
    if not screenshot_path.exists():
        raise ScreenshotNotFoundError(f"Screenshot not found: {screenshot_path}")

    if screenshot_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise TemplateCreatorError(
            f"Unsupported image format: {screenshot_path.suffix}. "
            f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )

    img = cv2.imread(str(screenshot_path))
    if img is None:
        raise TemplateCreatorError(f"Failed to load image: {screenshot_path}")

    return img


def crop_region(img: np.ndarray, region: Region) -> np.ndarray:
    """
    Crop region from image.

    Args:
        img: Source image (OpenCV BGR format)
        region: Region to crop

    Returns:
        np.ndarray: Cropped image

    Raises:
        InvalidRegionError: If region is invalid or out of bounds
    """
    height, width = img.shape[:2]
    region.validate(width, height)

    cropped = img[region.y1:region.y2, region.x1:region.x2]

    if cropped.size == 0:
        raise InvalidRegionError(f"Cropped region is empty: {region}")

    return cropped


def save_template(
    template_img: np.ndarray,
    name: str,
    output_dir: Path,
    format: str = "png"
) -> Path:
    """
    Save template image to file.

    Args:
        template_img: Template image to save
        name: Template name (without extension)
        output_dir: Output directory
        format: Image format (png, jpg, etc.)

    Returns:
        Path: Path to saved template file

    Raises:
        FileWriteError: If template cannot be saved
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    template_filename = f"{name}.{format}"
    template_path = output_dir / template_filename

    try:
        cv2.imwrite(str(template_path), template_img)
        if not template_path.exists():
            raise FileWriteError(f"Failed to save template: {template_path}")

        return template_path

    except Exception as e:
        raise FileWriteError(f"Error saving template to {template_path}: {str(e)}") from e


def save_metadata(metadata: TemplateMetadata, output_dir: Path) -> Path:
    """
    Save template metadata to JSON file.

    Args:
        metadata: Template metadata
        output_dir: Output directory

    Returns:
        Path: Path to saved metadata file

    Raises:
        FileWriteError: If metadata cannot be saved
    """
    metadata_filename = f"{metadata.name}.json"
    metadata_path = output_dir / metadata_filename

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

        return metadata_path

    except Exception as e:
        raise FileWriteError(f"Error saving metadata to {metadata_path}: {str(e)}") from e


def preview_template(template_img: np.ndarray, name: str) -> None:
    """
    Display template preview in window.

    Args:
        template_img: Template image to preview
        name: Template name for window title

    Note:
        Press any key to close the preview window.
    """
    height, width = template_img.shape[:2]

    # Calculate scaled size if template is too large
    scale = 1.0
    if width > MAX_PREVIEW_SIZE[0] or height > MAX_PREVIEW_SIZE[1]:
        scale_w = MAX_PREVIEW_SIZE[0] / width
        scale_h = MAX_PREVIEW_SIZE[1] / height
        scale = min(scale_w, scale_h)

    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        preview_img = cv2.resize(template_img, (new_width, new_height))
        window_title = f"Template Preview: {name} (scaled {scale:.2f}x)"
    else:
        preview_img = template_img
        window_title = f"Template Preview: {name}"

    cv2.imshow(window_title, preview_img)
    print(f"\n[Preview] Template: {name} | Size: {width}x{height}px")
    print("[Preview] Press any key to close preview window...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def validate_region_format(region_str: str, format_type: str) -> None:
    """
    Validate region string format without parsing.

    Args:
        region_str: Region string to validate
        format_type: Expected format type

    Raises:
        InvalidRegionError: If format is invalid
    """
    if not region_str:
        raise InvalidRegionError("Region string cannot be empty")

    parts = region_str.split(",")
    if len(parts) != 4:
        raise InvalidRegionError(
            f"Region must have exactly 4 comma-separated values, got {len(parts)}"
        )

    for part in parts:
        if not part.strip().lstrip("-").isdigit():
            raise InvalidRegionError(f"Invalid numeric value in region: '{part}'")


# ============================================================================
# SECTION 8: OUTPUT FORMATTERS
# ============================================================================

def format_success_message(
    template_path: Path,
    metadata_path: Path,
    metadata: TemplateMetadata
) -> str:
    """
    Format success message with template information.

    Args:
        template_path: Path to saved template file
        metadata_path: Path to saved metadata file
        metadata: Template metadata

    Returns:
        str: Formatted success message
    """
    return f"""
✓ Template created successfully!

Template Details:
  Name:       {metadata.name}
  Source:     {metadata.source_screenshot}
  Region:     ({metadata.region.x1}, {metadata.region.y1}) to ({metadata.region.x2}, {metadata.region.y2})
  Dimensions: {metadata.dimensions[0]}x{metadata.dimensions[1]}px

Saved Files:
  Template:   {template_path}
  Metadata:   {metadata_path}
"""


# ============================================================================
# SECTION 9: CLI INTERFACE
# ============================================================================

@click.command()
@click.option(
    "--screenshot-path",
    "-s",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to source screenshot image",
)
@click.option(
    "--region",
    "-r",
    required=True,
    help="Region to crop in format 'x1,y1,x2,y2' or 'x,y,width,height'",
)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Template name (without extension)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help="Output directory for template and metadata files",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["xyxy", "xywh"], case_sensitive=False),
    default="xyxy",
    help="Region format: xyxy (x1,y1,x2,y2) or xywh (x,y,width,height)",
)
@click.option(
    "--preview",
    "-p",
    is_flag=True,
    help="Preview template before saving",
)
@click.option(
    "--image-format",
    type=click.Choice(["png", "jpg", "jpeg"], case_sensitive=False),
    default="png",
    help="Output image format",
)
def main(
    screenshot_path: Path,
    region: str,
    name: str,
    output_dir: Path,
    format: str,
    preview: bool,
    image_format: str,
) -> None:
    """
    ADB Template Creator - Create action templates from screenshots.

    Creates image templates by cropping specific regions from screenshots.
    Templates are used for template matching in ADB automation.

    Examples:
        adb_template_creator.py -s screenshot.png -r "100,200,300,400" -n button_ok

        adb_template_creator.py -s screenshot.png -r "100,200,200,200" -n icon_settings -f xywh

        adb_template_creator.py -s screenshot.png -r "100,200,300,400" -n button_ok --preview
    """
    try:
        # Validate region format
        validate_region_format(region, format)

        # Parse region
        region_obj = parse_region(region, format)

        # Load screenshot
        print(f"Loading screenshot: {screenshot_path}")
        img = load_screenshot(screenshot_path)
        img_height, img_width = img.shape[:2]
        print(f"Screenshot size: {img_width}x{img_height}px")

        # Crop region
        print(f"Cropping region: ({region_obj.x1}, {region_obj.y1}) to ({region_obj.x2}, {region_obj.y2})")
        template_img = crop_region(img, region_obj)
        print(f"Template size: {region_obj.width}x{region_obj.height}px")

        # Preview if requested
        if preview:
            preview_template(template_img, name)

        # Save template
        print(f"\nSaving template to: {output_dir}")
        template_path = save_template(template_img, name, output_dir, image_format)

        # Create and save metadata
        metadata = TemplateMetadata(
            name=name,
            source_screenshot=str(screenshot_path),
            region=region_obj,
            dimensions=(region_obj.width, region_obj.height),
            template_path=str(template_path),
            format=image_format,
        )
        metadata_path = save_metadata(metadata, output_dir)

        # Display success message
        print(format_success_message(template_path, metadata_path, metadata))

        sys.exit(0)

    except ScreenshotNotFoundError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

    except InvalidRegionError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)

    except TemplateCreatorError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(3)

    except FileWriteError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(4)

    except Exception as e:
        print(f"Unexpected error: {str(e)}", file=sys.stderr)
        sys.exit(5)


if __name__ == "__main__":
    main()
