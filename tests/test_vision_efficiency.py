from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from coc_bot.config import BotConfig
from coc_bot.vision import TemplateMatch, VisionModule


class CountingVision(VisionModule):
    def __init__(self) -> None:
        self.config = BotConfig()
        self.screenshot_calls = 0
        self.template_checks: list[str] = []

    def screenshot_array(self) -> np.ndarray:
        self.screenshot_calls += 1
        return np.full((20, 20, 3), 16, dtype=np.uint8)

    def _find_template_in_image(
        self,
        screenshot_rgb: np.ndarray,
        template_path_value: str,
        threshold: float,
        search_area=None,
    ) -> TemplateMatch | None:
        self.template_checks.append(template_path_value)
        return None


class VisionEfficiencyTest(unittest.TestCase):
    def test_find_any_template_reuses_one_screenshot_for_all_templates(self) -> None:
        vision = CountingVision()

        found = vision._find_any_template(["one.png", "two.png", "three.png"], 0.7)

        self.assertFalse(found)
        self.assertEqual(vision.template_checks, ["one.png", "two.png", "three.png"])
        self.assertEqual(vision.screenshot_calls, 1)

    def test_find_any_template_skips_screenshot_when_no_paths_are_configured(self) -> None:
        vision = CountingVision()

        found = vision._find_any_template(["", ""], 0.7)

        self.assertFalse(found)
        self.assertEqual(vision.template_checks, [])
        self.assertEqual(vision.screenshot_calls, 0)

    def test_template_gray_image_is_cached_after_first_load(self) -> None:
        vision = VisionModule.__new__(VisionModule)
        vision._template_cache = {}
        vision._template_gray_cache = {}

        with TemporaryDirectory() as tmp_dir:
            template_path = Path(tmp_dir) / "template.png"
            image = np.full((4, 4, 3), 32, dtype=np.uint8)
            cv2.imwrite(str(template_path), image)

            first = vision._load_gray_template(str(template_path))
            second = vision._load_gray_template(str(template_path))

        self.assertIsNotNone(first)
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
