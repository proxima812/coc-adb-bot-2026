from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from .calibration import CalibrationOverlay
from .adb_device import AdbDevice
from .config import BotConfig, RelativePoint
from .vision import BuilderSlotState, VisionModule


class UnsafeBuilderTapError(RuntimeError):
    pass


class BuilderBattleFlow:
    def __init__(self, device: AdbDevice, vision: VisionModule, config: BotConfig) -> None:
        self.device = device
        self.vision = vision
        self.config = config
        self.calibration = CalibrationOverlay(config)
        self._builder_overlay_count = 0

    def run_once(self) -> None:
        self._builder_overlay_count = 0
        logger.info("Builder cycle step: dismiss_popups")
        self.dismiss_popups()
        logger.info("Builder cycle step: wait_for_base")
        self._wait_until_builder_base()
        logger.info("Builder cycle step: open_attack")
        self._open_attack()
        logger.info("Builder cycle step: wait_for_battle")
        self._wait_until_builder_battle()
        logger.info("Builder cycle step: deploy_slots")
        self._deploy_slots()
        logger.info("Builder cycle step: wait_and_return_home")
        self._wait_and_return_home()
        logger.info("Builder cycle step: dismiss_popups_after_return")
        self.dismiss_popups()

    def dismiss_popups(self) -> bool:
        if self.vision.has_okay_button():
            logger.info(
                "Builder Okay button detected; pressing configured point {},{}",
                self.config.okay_button_point.x,
                self.config.okay_button_point.y,
            )
            self._tap(self.config.okay_button_point)
            time.sleep(self.config.tap_delay_seconds)
            return True

        if self.vision.has_configured_popup():
            logger.info(
                "Builder popup detected; pressing Okay point {},{}",
                self.config.okay_button_point.x,
                self.config.okay_button_point.y,
            )
            self._tap(self.config.okay_button_point)
            time.sleep(self.config.tap_delay_seconds)
            return True
        return False

    def _wait_until_builder_base(self) -> None:
        while True:
            if self.dismiss_popups():
                continue
            if self.vision.has_builder_attack_button():
                logger.info("Builder base detected by Attack template")
                return
            if self.vision.has_star_bonus_counter():
                logger.info("Builder base detected by star bonus template")
                return
            if self.vision.has_builder_return_home_button():
                logger.info("Return Home is visible while waiting for base; pressing R")
                self._tap(self.config.builder_return_home_point)
            else:
                logger.info("Builder base not detected yet")
            time.sleep(self.config.builder_state_poll_seconds)

    def _open_attack(self) -> None:
        if not self.config.builder_attack_taps:
            raise RuntimeError("builder_attack_taps is empty")

        self._tap(self.config.builder_attack_taps[0])
        self._wait_and_tap_find_match()

    def _wait_and_tap_find_match(self) -> None:
        deadline = time.monotonic() + self.config.wait_attack_ready_seconds
        fallback_point = self.config.builder_attack_taps[min(1, len(self.config.builder_attack_taps) - 1)]
        while time.monotonic() < deadline:
            match = self.vision.find_builder_find_match_button()
            if match is not None:
                logger.info("Builder Find Match detected at {},{} score={:.3f}", match.x, match.y, match.score)
                self.device.tap(match.x, match.y)
                time.sleep(self.config.tap_delay_seconds)
                return
            logger.info("Builder Find Match is not visible yet")
            time.sleep(self.config.builder_state_poll_seconds)

        logger.warning("Builder Find Match was not detected; pressing configured fallback point")
        self._tap(fallback_point)
        time.sleep(self.config.tap_delay_seconds)

    def _wait_until_builder_battle(self) -> None:
        deadline = time.monotonic() + self.config.wait_battle_seconds
        while time.monotonic() < deadline:
            if self.vision.has_builder_battle_marker():
                logger.info("Builder battle detected")
                return
            time.sleep(self.config.builder_state_poll_seconds)
        raise RuntimeError("Builder battle screen was not detected after pressing attack")

    def _deploy_slots(self) -> None:
        self._rapid_deploy_slots_through_g()
        self._check_builder_slot_states()

    def _rapid_deploy_slots_through_g(self) -> None:
        logger.info("Builder rapid deploy slots 1-8 through G point")
        for index, slot in enumerate(self.config.builder_troop_slots, start=1):
            logger.info("Builder rapid deploy slot {} through G", index)
            self._tap(slot)
            self._tap_many(self._with_neighbor_points([self.config.builder_deploy_point]))
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)

    def _check_builder_slot_states(self) -> None:
        if not self.config.builder_slot_state_checks_enabled:
            return

        for pass_index in range(1, self.config.builder_slot_state_check_passes + 1):
            logger.info("Builder slot state check pass {}", pass_index)
            screenshot = None
            for index, slot in enumerate(self.config.builder_troop_slots, start=1):
                if screenshot is None:
                    screenshot = self.vision.screenshot_array()
                state = self.vision.detect_builder_slot_state(slot, screenshot=screenshot)
                logger.info("Builder slot {} state: {}", index, state)
                if state == BuilderSlotState.NOT_DEPLOYED:
                    logger.warning("Builder slot {} was not deployed; retrying deploy", index)
                    self._tap(slot)
                    self._tap_many(self._with_neighbor_points([self.config.builder_deploy_point]))
                    screenshot = None
                elif state == BuilderSlotState.ABILITY_READY:
                    logger.info("Builder slot {} ability is ready; activating", index)
                    self._tap(slot)
                    screenshot = None
                time.sleep(self.config.rapid_deploy_tap_delay_seconds)

            if pass_index < self.config.builder_slot_state_check_passes:
                time.sleep(self.config.builder_slot_state_check_delay_seconds)

    def _deploy_slots_through_g(self) -> None:
        for index, slot in enumerate(self.config.builder_troop_slots, start=1):
            logger.info("Builder deploy slot {} through G", index)
            self._tap(slot)
            time.sleep(self.config.deploy_step_delay_seconds)
            self._tap_many(self._with_neighbor_points([self.config.builder_deploy_point]))
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)

    def _wait_and_return_home(self) -> None:
        deadline = time.monotonic() + self.config.builder_battle_timeout_seconds
        next_slot_one_at = time.monotonic() + self.config.builder_first_slot_retap_interval_seconds
        next_redeploy_at = time.monotonic() + self.config.builder_redeploy_slots_interval_seconds
        next_hero_ability_at = time.monotonic() + self.config.builder_hero_ability_interval_seconds
        while time.monotonic() < deadline:
            if self.vision.has_builder_return_home_button():
                logger.info("Builder Return Home detected; pressing R")
                self._tap(self.config.builder_return_home_point)
                time.sleep(self.config.tap_delay_seconds)
                return

            now = time.monotonic()
            if self.config.builder_first_slot_retap_enabled and now >= next_slot_one_at:
                logger.info("Builder retapping slot 1")
                self._tap(self.config.builder_troop_slots[0])
                next_slot_one_at = now + self.config.builder_first_slot_retap_interval_seconds

            if self.config.builder_redeploy_slots_enabled and now >= next_redeploy_at:
                logger.info("Builder redeploying slots 1-8 through G")
                self._rapid_deploy_slots_through_g()
                next_redeploy_at = now + self.config.builder_redeploy_slots_interval_seconds

            if self.config.builder_hero_ability_enabled and now >= next_hero_ability_at:
                if self.vision.has_builder_hero():
                    logger.info("Builder hero detected; activating ability")
                    self._tap(self.config.builder_hero_ability_point)
                else:
                    logger.info("Builder hero not detected; skipping hero ability tap")
                next_hero_ability_at = now + self.config.builder_hero_ability_interval_seconds

            time.sleep(self.config.builder_state_poll_seconds)
        logger.warning("Builder Return Home was not detected before timeout; pressing R anyway")
        self._tap(self.config.builder_return_home_point)
        time.sleep(self.config.tap_delay_seconds)

    def _tap(self, point: RelativePoint) -> None:
        self._calibrate_builder_tap([point], "tap")
        self._guard_builder_point(point)
        self.device.tap_percent(point.x, point.y)

    def _tap_many(self, points: list[tuple[float, float]]) -> None:
        batch_size = 24
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            active_points = [RelativePoint(x=x, y=y) for x, y in batch]
            self._calibrate_builder_tap(active_points, "tap_many")
            for point in active_points:
                self._guard_builder_point(point)
            self.device.tap_many_percent(batch)
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)

    def _calibrate_builder_tap(self, active_points: list[RelativePoint], reason: str) -> None:
        if not self.config.builder_calibration_enabled and not self.config.builder_tap_overlay_enabled:
            return
        if (
            self.config.builder_tap_overlay_max_per_cycle
            and self._builder_overlay_count >= self.config.builder_tap_overlay_max_per_cycle
        ):
            return

        screenshot = self.vision.screenshot_array()
        self._check_builder_screen_size(screenshot.shape[1], screenshot.shape[0])
        if self.config.builder_tap_overlay_enabled:
            safe_reason = f"{reason}_{self._builder_overlay_count + 1:03d}"
            self.calibration.save_builder_overlay(
                screenshot,
                Path(self.config.builder_tap_overlay_dir),
                safe_reason,
                active_points,
            )
            self._builder_overlay_count += 1

    def _check_builder_screen_size(self, width: int, height: int) -> None:
        if not self.config.builder_calibration_enabled:
            return
        expected_width = self.config.expected_screen_width
        expected_height = self.config.expected_screen_height
        if expected_width <= 0 or expected_height <= 0:
            return
        width_drift = abs(width - expected_width) / expected_width * 100.0
        height_drift = abs(height - expected_height) / expected_height * 100.0
        max_drift = max(width_drift, height_drift)
        if max_drift > self.config.builder_calibration_max_screen_drift_percent:
            raise RuntimeError(
                f"Builder screen calibration failed: current={width}x{height}, "
                f"expected={expected_width}x{expected_height}, drift={max_drift:.2f}%"
            )

    def _guard_builder_point(self, point: RelativePoint) -> None:
        if not self.config.builder_safe_tap_area.contains(point):
            raise UnsafeBuilderTapError(f"Builder tap outside safe area: {point}")
        for index, area in enumerate(self.config.builder_forbidden_tap_areas, start=1):
            if area.contains(point):
                raise UnsafeBuilderTapError(f"Builder tap blocked by forbidden area {index}: {point}")

    def _with_neighbor_points(self, points: list[RelativePoint]) -> list[tuple[float, float]]:
        if not self.config.deploy_neighbor_taps_enabled or self.config.deploy_neighbor_offset_percent <= 0:
            return [(point.x, point.y) for point in points]

        offset = self.config.deploy_neighbor_offset_percent
        expanded: list[tuple[float, float]] = []
        seen: set[tuple[float, float]] = set()
        for point in points:
            for x, y in (
                (point.x, point.y),
                (point.x + offset, point.y),
                (point.x - offset, point.y),
                (point.x, point.y + offset),
                (point.x, point.y - offset),
            ):
                clamped = (round(min(100.0, max(0.0, x)), 2), round(min(100.0, max(0.0, y)), 2))
                if clamped not in seen:
                    expanded.append(clamped)
                    seen.add(clamped)
        return expanded
