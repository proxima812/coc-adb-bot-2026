from __future__ import annotations

import unittest
from contextlib import contextmanager

import numpy as np

from coc_bot.builder_flow import BuilderBattleFlow, UnsafeBuilderTapError
from coc_bot.config import BotConfig, RelativeArea, RelativePoint
from coc_bot.vision import BuilderSlotState


class FakeDevice:
    def __init__(self) -> None:
        self.pixel_taps: list[tuple[int, int]] = []
        self.taps: list[tuple[float, float]] = []
        self.tap_batches: list[list[tuple[float, float]]] = []

    def tap(self, x: int, y: int) -> None:
        self.pixel_taps.append((x, y))

    def tap_percent(self, x: float, y: float) -> None:
        self.taps.append((x, y))

    def tap_many_percent(self, points: list[tuple[float, float]]) -> None:
        self.tap_batches.append(points)


class FakeVision:
    def __init__(self) -> None:
        self.okay_results: list[bool] = []
        self.popup_results: list[bool] = []
        self.find_match_results: list[object | None] = []
        self.return_home_results: list[bool] = []
        self.slot_state_results: list[str] = []
        self.hero_results: list[bool] = []
        self.screenshot_calls = 0
        self.slot_state_screenshots: list[object | None] = []

    def screenshot_array(self) -> np.ndarray:
        self.screenshot_calls += 1
        return np.full((100, 200, 3), 32, dtype=np.uint8)

    @contextmanager
    def frame(self):  # no-op кэш-контекст для совместимости с продакшеном
        yield self.screenshot_array()

    def has_okay_button(self) -> bool:
        return self.okay_results.pop(0) if self.okay_results else False

    def has_configured_popup(self) -> bool:
        return self.popup_results.pop(0) if self.popup_results else False

    def find_builder_find_match_button(self) -> object | None:
        return self.find_match_results.pop(0) if self.find_match_results else None

    def has_builder_return_home_button(self) -> bool:
        return self.return_home_results.pop(0) if self.return_home_results else False

    def detect_builder_slot_state(self, slot: RelativePoint, screenshot: object | None = None) -> str:
        self.slot_state_screenshots.append(screenshot)
        return self.slot_state_results.pop(0) if self.slot_state_results else BuilderSlotState.DEPLOYED

    def has_builder_hero(self) -> bool:
        return self.hero_results.pop(0) if self.hero_results else False


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

    def test_open_attack_waits_for_find_match_before_second_tap(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.find_match_results = [
            None,
            type("Match", (), {"x": 1192, "y": 592, "score": 0.91})(),
        ]
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_state_poll_seconds=0.0,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._open_attack()

        self.assertEqual(device.taps, [(6.81, 88.78)])
        self.assertEqual(device.pixel_taps, [(1192, 592)])

    def test_wait_return_home_does_not_redeploy_when_disabled(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_battle_timeout_seconds=0.01,
            builder_state_poll_seconds=0.0,
            builder_first_slot_retap_enabled=False,
            builder_redeploy_slots_enabled=False,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._wait_and_return_home()

        self.assertEqual(device.tap_batches, [])

    def test_wait_return_home_redeploys_slots_after_interval(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_battle_timeout_seconds=0.03,
            builder_state_poll_seconds=0.0,
            builder_redeploy_slots_enabled=True,
            builder_redeploy_slots_interval_seconds=0.0,
            builder_hero_ability_enabled=False,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._wait_and_return_home()

        self.assertGreaterEqual(len(device.tap_batches), len(config.builder_troop_slots))

    def test_wait_return_home_skips_hero_ability_when_hero_missing(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_battle_timeout_seconds=0.03,
            builder_state_poll_seconds=0.0,
            builder_first_slot_retap_enabled=False,
            builder_redeploy_slots_enabled=False,
            builder_hero_ability_enabled=True,
            builder_hero_ability_interval_seconds=0.0,
            builder_hero_ability_point=RelativePoint(x=5.7, y=90.0),
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._wait_and_return_home()

        self.assertNotIn((5.7, 90.0), device.taps)

    def test_wait_return_home_activates_hero_ability_when_hero_present(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.hero_results = [True]
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_battle_timeout_seconds=0.01,
            builder_state_poll_seconds=0.0,
            builder_first_slot_retap_enabled=False,
            builder_redeploy_slots_enabled=False,
            builder_hero_ability_enabled=True,
            builder_hero_ability_interval_seconds=0.0,
            builder_hero_ability_point=RelativePoint(x=5.7, y=90.0),
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._wait_and_return_home()

        self.assertIn((5.7, 90.0), device.taps)

    def test_rapid_deploy_taps_all_builder_slots_before_state_checks(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_slot_state_checks_enabled=False,
        )
        flow = BuilderBattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        flow._deploy_slots()

        self.assertEqual(device.taps, [(slot.x, slot.y) for slot in config.builder_troop_slots])
        self.assertEqual(len(device.tap_batches), len(config.builder_troop_slots))

    def test_slot_state_check_retries_not_deployed_and_activates_ready_skill(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.slot_state_results = [
            BuilderSlotState.NOT_DEPLOYED,
            BuilderSlotState.ABILITY_READY,
            *([BuilderSlotState.DEPLOYED] * 6),
        ]
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_slot_state_check_passes=1,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._check_builder_slot_states()

        self.assertEqual(device.taps, [(10.94, 88.89), (19.56, 89.44)])
        self.assertEqual(len(device.tap_batches), 1)

    def test_slot_state_check_reuses_single_screenshot_when_no_actions_change_screen(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.slot_state_results = [BuilderSlotState.DEPLOYED] * 8
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_slot_state_check_passes=1,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._check_builder_slot_states()

        self.assertEqual(vision.screenshot_calls, 1)
        self.assertEqual(len(vision.slot_state_screenshots), len(config.builder_troop_slots))
        self.assertTrue(all(screenshot is vision.slot_state_screenshots[0] for screenshot in vision.slot_state_screenshots))

    def test_slot_state_check_refreshes_screenshot_after_builder_action(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.slot_state_results = [
            BuilderSlotState.NOT_DEPLOYED,
            *([BuilderSlotState.DEPLOYED] * 7),
        ]
        config = BotConfig(
            builder_tap_overlay_enabled=False,
            builder_calibration_enabled=False,
            builder_slot_state_check_passes=1,
        )
        flow = BuilderBattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._check_builder_slot_states()

        self.assertEqual(vision.screenshot_calls, 2)
        self.assertIsNot(vision.slot_state_screenshots[0], vision.slot_state_screenshots[1])


if __name__ == "__main__":
    unittest.main()
