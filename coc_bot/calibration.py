from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from .config import BotConfig, RelativeArea, RelativePoint


class CalibrationOverlay:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    def save_overlay(self, screenshot: np.ndarray, output_dir: Path | str, reason: str = "calibration") -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        image = Image.fromarray(screenshot).convert("RGB")
        draw = ImageDraw.Draw(image)
        width, height = image.size

        self._draw_grid(draw, width, height)
        self._draw_area(draw, width, height, self.config.spell_deploy_area, "spells", (80, 180, 255))
        self._draw_points(draw, width, height, self.config.fallback_deploy_points, "G", (255, 80, 80))
        self._draw_points(draw, width, height, [step.point for step in self.config.deploy_plan], "slot", (255, 220, 80))

        safe_reason = "".join(char if char.isalnum() or char in "._-" else "_" for char in reason).strip("_")
        filename = f"{datetime.now():%Y%m%d-%H%M%S}-{safe_reason or 'calibration'}.png"
        path = output_path / filename
        image.save(path)
        logger.info("Calibration overlay saved: {}", path)
        return path

    def save_builder_overlay(
        self,
        screenshot: np.ndarray,
        output_dir: Path | str,
        reason: str = "builder",
        active_points: list[RelativePoint] | None = None,
    ) -> Path:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        image = Image.fromarray(screenshot).convert("RGB")
        draw = ImageDraw.Draw(image)
        width, height = image.size

        self._draw_grid(draw, width, height)
        self._draw_area(draw, width, height, self.config.builder_safe_tap_area, "builder-safe", (80, 210, 120))
        for index, area in enumerate(self.config.builder_forbidden_tap_areas, start=1):
            self._draw_area(draw, width, height, area, f"no-tap{index}", (255, 80, 80))
        self._draw_points(draw, width, height, self.config.builder_attack_taps, "attack", (255, 220, 80))
        self._draw_points(draw, width, height, self.config.builder_troop_slots, "slot", (80, 180, 255))
        self._draw_points(draw, width, height, [self.config.builder_deploy_point], "deploy", (255, 120, 255))
        self._draw_points(draw, width, height, [self.config.builder_return_home_point], "home", (120, 255, 180))
        if active_points:
            self._draw_active_points(draw, width, height, active_points)

        safe_reason = "".join(char if char.isalnum() or char in "._-" else "_" for char in reason).strip("_")
        filename = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{safe_reason or 'builder'}.png"
        path = output_path / filename
        image.save(path)
        logger.info("Builder calibration overlay saved: {}", path)
        return path

    def _draw_grid(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        step = self.config.calibration_overlay_grid_step_percent
        value = 0.0
        while value <= 100.0:
            x = round(width * value / 100)
            y = round(height * value / 100)
            color = (80, 80, 80) if value not in (0.0, 100.0) else (160, 160, 160)
            draw.line([(x, 0), (x, height)], fill=color, width=1)
            draw.line([(0, y), (width, y)], fill=color, width=1)
            self._label(draw, x + 3, 3, f"x{value:g}")
            self._label(draw, 3, y + 3, f"y{value:g}")
            value += step

    def _draw_area(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        area: RelativeArea,
        label: str,
        color: tuple[int, int, int],
    ) -> None:
        x_min = round(width * area.x_min / 100)
        x_max = round(width * area.x_max / 100)
        y_min = round(height * area.y_min / 100)
        y_max = round(height * area.y_max / 100)
        draw.rectangle([(x_min, y_min), (x_max, y_max)], outline=color, width=2)
        self._label(draw, x_min + 4, y_min + 4, label)

    def _draw_points(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        points: list[RelativePoint],
        label_prefix: str,
        color: tuple[int, int, int],
    ) -> None:
        for index, point in enumerate(points, start=1):
            x = round(width * point.x / 100)
            y = round(height * point.y / 100)
            radius = 5
            draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], outline=color, width=2)
            draw.line([(x - 8, y), (x + 8, y)], fill=color, width=1)
            draw.line([(x, y - 8), (x, y + 8)], fill=color, width=1)
            self._label(draw, x + 7, y + 7, f"{label_prefix}{index} {point.x:g},{point.y:g}")

    def _draw_active_points(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        points: list[RelativePoint],
    ) -> None:
        for index, point in enumerate(points, start=1):
            x = round(width * point.x / 100)
            y = round(height * point.y / 100)
            radius = 9
            draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], fill=(0, 255, 60), outline=(0, 0, 0), width=2)
            draw.line([(x - 14, y), (x + 14, y)], fill=(255, 255, 255), width=2)
            draw.line([(x, y - 14), (x, y + 14)], fill=(255, 255, 255), width=2)
            self._label(draw, x + 12, y + 12, f"ACTIVE{index} {point.x:g},{point.y:g}")

    @staticmethod
    def _label(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> None:
        font = ImageFont.load_default()
        bbox = draw.textbbox((x, y), text, font=font)
        draw.rectangle(bbox, fill=(0, 0, 0))
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
