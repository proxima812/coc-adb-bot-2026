from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from coc_bot.calibration import CalibrationOverlay
from coc_bot.config import BotConfig, DeployStep, RelativeArea, RelativePoint


class CalibrationOverlayTest(unittest.TestCase):
    def test_saves_overlay_with_grid_and_config_points(self) -> None:
        config = BotConfig(
            deploy_plan=[
                DeployStep(name="slot_a", point=RelativePoint(x=50.0, y=90.0)),
            ],
            fallback_deploy_points=[
                RelativePoint(x=10.0, y=20.0),
            ] * 19,
            spell_deploy_area=RelativeArea(x_min=40.0, x_max=60.0, y_min=40.0, y_max=60.0),
        )
        screenshot = np.full((100, 200, 3), 32, dtype=np.uint8)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output = CalibrationOverlay(config).save_overlay(screenshot, Path(tmp_dir), "test")

            self.assertTrue(output.exists())
            image = Image.open(output).convert("RGB")
            self.assertEqual(image.size, (200, 100))
            self.assertNotEqual(image.getpixel((100, 50)), (32, 32, 32))
            self.assertNotEqual(image.getpixel((20, 20)), (32, 32, 32))


if __name__ == "__main__":
    unittest.main()
