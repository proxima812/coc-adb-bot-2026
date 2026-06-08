from __future__ import annotations

import unittest

import numpy as np

from coc_bot.builder_flow import BuilderBattleFlow, UnsafeBuilderTapError
from coc_bot.config import BotConfig, RelativeArea, RelativePoint


class FakeDevice:
    def __init__(self) -> None:
        self.taps: list[tuple[float, float]] = []
        self.tap_batches: list[list[tuple[float, float]]] = []

    def tap_percent(self, x: float, y: float) -> None:
        self.taps.append((x, y))

    def tap_many_percent(self, points: list[tuple[float, float]]) -> None:
        self.tap_batches.append(points)


class FakeVision:
    def __init__(self) -> None:
        self.okay_results: list[bool] = []
        self.popup_results: list[bool] = []

    def screenshot_array(self) -> np.ndarray:
        return np.full((100, 200, 3), 32, dtype=np.uint8)

    def has_okay_button(self) -> bool:
        return self.okay_results.pop(0) if self.okay_results else False

    def has_configured_popup(self) -> bool:
        return self.popup_results.pop(0) if self.popup_results else False


class BuilderFlowGuardTest(unittest.TestCase):
    def test_allows_builder_slot_tap(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=True,
            builder_forbidden_tap_areas=[RelativeArea(x_min=72.0, x_max=100.0, y_min=78.0, y_max=100.0)],
        )
        flow = BuilderBattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        flow._tap(RelativePoint(x=10.94, y=88.89))

        self.assertEqual(device.taps, [(10.94, 88.89)])

    def test_blocks_forbidden_shop_area_before_adb_tap(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=True,
            builder_forbidden_tap_areas=[RelativeArea(x_min=72.0, x_max=100.0, y_min=78.0, y_max=100.0)],
        )
        flow = BuilderBattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        with self.assertRaises(UnsafeBuilderTapError):
            flow._tap(RelativePoint(x=88.0, y=89.0))

        self.assertEqual(device.taps, [])

    def test_screen_size_drift_blocks_tap(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=True,
            expected_screen_width=1600,
            expected_screen_height=900,
            builder_calibration_max_screen_drift_percent=2.0,
        )
        flow = BuilderBattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        with self.assertRaises(RuntimeError):
            flow._tap(RelativePoint(x=10.94, y=88.89))

        self.assertEqual(device.taps, [])

    def test_dismisses_builder_okay_popup_with_configured_okay_point(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.okay_results = [True]
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            okay_button_point=RelativePoint(x=50.32, y=79.04),
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        self.assertTrue(flow.dismiss_popups())

        self.assertEqual(device.taps, [(50.32, 79.04)])


if __name__ == "__main__":
    unittest.main()
