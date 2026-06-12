from __future__ import annotations

import random
import time

from loguru import logger

from .adb_device import AdbDevice
from .calibration import CalibrationOverlay
from .config import BotConfig, DeployStep, RelativePoint
from .vision import GameState, Loot, VisionModule


class BattleFlow:
    def __init__(self, device: AdbDevice, vision: VisionModule, config: BotConfig) -> None:
        self.device = device
        self.vision = vision
        self.config = config
        self.calibration = CalibrationOverlay(config)

    def run_once(self) -> None:
        logger.info("Cycle step: dismiss_popups")
        self.dismiss_popups()
        logger.info("Cycle step: open_battle_from_base")
        self._open_battle_from_base()
        logger.info("Cycle step: wait_for_battle")
        if not self._wait_until_acceptable_battle():
            raise RuntimeError("Battle screen was not detected after pressing final attack button")
        logger.info("Cycle step: prepare_battle_camera")
        self._prepare_battle_camera()
        logger.info("Cycle step: deploy_army")
        self._deploy_army()
        logger.info("Waiting after deploy: {} seconds", self.config.wait_after_deploy_seconds)
        time.sleep(self.config.wait_after_deploy_seconds)
        logger.info("Cycle step: finish_and_return_home")
        self._finish_and_return_home()
        logger.info("Cycle step: dismiss_popups_after_return")
        self.dismiss_popups()

    def dismiss_popups(self) -> bool:
        # Один кадр на оба template-чека (раньше — два независимых screencap).
        with self.vision.frame():
            has_okay = self.vision.has_okay_button()
            has_popup = False if has_okay else self.vision.has_configured_popup()
        if has_okay:
            logger.info(
                "Okay button detected; pressing configured point {},{}",
                self.config.okay_button_point.x,
                self.config.okay_button_point.y,
            )
            self._tap(self.config.okay_button_point)
            time.sleep(self.config.tap_delay_seconds)
            return True

        if has_popup:
            logger.info(
                "Configured popup detected; pressing Okay point {},{}",
                self.config.okay_button_point.x,
                self.config.okay_button_point.y,
            )
            self._tap(self.config.okay_button_point)
            time.sleep(self.config.tap_delay_seconds)
            return True
        return False

    def _open_battle_from_base(self) -> None:
        logger.info("Opening battle from base")
        if not self.config.home_free_check_enabled:
            for point in self.config.base_attack_taps:
                self._tap(point)
                time.sleep(self.config.base_search_tap_delay_seconds)
            return

        for index, point in enumerate(self.config.base_attack_taps):
            if index > self.config.home_free_first_tap_index:
                break
            self._tap(point)
            time.sleep(self.config.base_search_tap_delay_seconds)
        if self.vision.has_free_button():
            logger.info("Home village free button found; collecting before attack")
            for point in (
                self.config.home_free_open_point,
                self.config.home_free_collect_point,
                self.config.home_free_close_point,
            ):
                self._tap(point)
                time.sleep(self.config.base_search_tap_delay_seconds)
        else:
            logger.info("Home village free button was not detected; continuing attack")

        self._tap(self.config.home_attack_start_point)
        time.sleep(self.config.base_search_tap_delay_seconds)

    def _wait_until_attack_ready(self) -> None:
        logger.info("Waiting until attack button is ready")
        deadline = time.monotonic() + self.config.wait_attack_ready_seconds
        while time.monotonic() < deadline:
            if self.vision.is_attack_ready():
                logger.info("Attack is ready")
                return
            logger.info("Attack is not ready yet")
            time.sleep(3)
        logger.warning("Attack readiness was not detected quickly; pressing final attack button anyway")

    def _wait_until_battle(self) -> bool:
        logger.info("Waiting for battle screen")
        deadline = time.monotonic() + self.config.wait_battle_seconds
        while time.monotonic() < deadline:
            state = self.vision.detect_state()
            if state == GameState.BATTLE:
                logger.info("Battle screen detected")
                return True
            time.sleep(1)
        logger.warning("Battle screen was not detected")
        return False

    def _wait_until_acceptable_battle(self) -> bool:
        while True:
            if not self._wait_until_battle():
                return False
            if not self.config.loot_check_enabled:
                logger.info("Loot check disabled, starting attack")
                return True

            loot = self._read_loot_with_retries()
            logger.info(
                "Available loot: gold={}, elixir={}, dark_elixir={}",
                loot.gold,
                loot.elixir,
                loot.dark_elixir,
            )
            if loot.gold >= self.config.loot_min_gold and loot.elixir >= self.config.loot_min_elixir:
                logger.info("Loot accepted, starting attack")
                return True

            logger.info(
                "Loot rejected: need gold>={} and elixir>={}; pressing next",
                self.config.loot_min_gold,
                self.config.loot_min_elixir,
            )
            self._tap(self.config.next_base_point)
            time.sleep(self.config.next_search_delay_seconds)

    def _read_loot_with_retries(self) -> Loot:
        best = None
        for _ in range(self.config.loot_ocr_attempts):
            loot = self.vision.read_battle_loot()
            if best is None or (loot.gold + loot.elixir) > (best.gold + best.elixir):
                best = loot
            if loot.gold > 0 and loot.elixir > 0:
                return loot
            time.sleep(0.5)
        return best

    def _deploy_army(self) -> None:
        if self.config.deploy_mode == "templates":
            self._deploy_army_by_templates()
            return
        if self.config.deploy_mode == "hotkeys":
            self._deploy_army_by_hotkeys()
            return

        logger.info("Deploying configured coordinate plan")
        for step in self.config.deploy_plan:
            if step.random_deploy_area == "spells":
                self._activate_hero_abilities()
                if self.config.pre_spell_delay_seconds > 0:
                    logger.info("Waiting before spells: {} seconds", self.config.pre_spell_delay_seconds)
                    time.sleep(self.config.pre_spell_delay_seconds)

            if not self.config.deploy_slot_detection_area.contains(step.point):
                logger.warning(
                    "Deploy slot {} is outside bottom detection area: {},{}",
                    step.name,
                    step.point.x,
                    step.point.y,
                )
            logger.info(
                "Selecting deploy slot: {} taps={} hold={}s",
                step.name,
                step.deploy_taps,
                step.deploy_hold_seconds,
            )
            self._tap(step.point)
            time.sleep(self.config.deploy_step_delay_seconds)
            if step.random_deploy_area:
                self._deploy_random_points(step)
                continue

            if self.config.deploy_mode == "g_key" and step.deploy_point_group == "troops":
                self._deploy_step_with_g_key(step)
                continue

            self._deploy_step_to_primary_and_fallbacks(step)

    def _deploy_army_by_templates(self) -> None:
        logger.info("Deploying configured targets")
        for target in self.config.deploy_targets:
            match = self.vision.find_template(
                target.template_path,
                self.config.deploy_template_threshold,
                self.config.deploy_slot_detection_area,
            )
            if match is None:
                logger.warning("Deploy target not found: {}", target.name)
                continue

            logger.info("Deploy target found: {} at {},{} score={:.3f}", target.name, match.x, match.y, match.score)
            self.device.tap(match.x, match.y)
            time.sleep(self.config.tap_delay_seconds)
            self._tap(self.config.troop_deploy_point)
            time.sleep(self.config.tap_delay_seconds)

    def _finish_and_return_home(self) -> None:
        logger.info("Ending battle and returning home")
        self._tap(self.config.end_battle_point)
        time.sleep(self.config.tap_delay_seconds)
        self._tap(self.config.confirm_end_point)
        time.sleep(self.config.tap_delay_seconds)
        self._tap(self.config.return_home_point)

    def _prepare_battle_camera(self) -> None:
        if not self.config.battle_camera_prepare_enabled:
            return
        if self.config.battle_camera_direct_ctrl_scroll_enabled:
            logger.info(
                "Preparing battle camera with direct Ctrl+mouse wheel: ticks={}",
                self.config.battle_camera_direct_ctrl_scroll_ticks,
            )
            self.device.ctrl_mouse_wheel_zoom_out(self.config.battle_camera_direct_ctrl_scroll_ticks)
            time.sleep(self.config.battle_camera_center_settle_seconds)
            if self.config.calibration_overlay_enabled and self.config.calibration_overlay_after_camera_prepare:
                screenshot = self.vision.screenshot_array()
                self.calibration.save_overlay(screenshot, self.config.calibration_overlay_dir, "after-camera-prepare")
            return
        logger.info(
            "Preparing battle camera: adb_zoom_out_attempts={} pan_enabled={} pan_repeats={}",
            self.config.battle_camera_zoom_out_attempts,
            self.config.battle_camera_pan_enabled,
            self.config.battle_camera_pan_repeats,
        )
        for attempt in range(1, self.config.battle_camera_zoom_out_attempts + 1):
            logger.info("Battle camera zoom-out attempt {}/{}", attempt, self.config.battle_camera_zoom_out_attempts)
            self.device.pinch_zoom_out_percent(self.config.battle_camera_zoom_out_seconds)
            time.sleep(self.config.battle_camera_pan_settle_seconds)
        if self.config.battle_camera_pan_enabled:
            if self.config.battle_camera_pan_mode == "diagonal":
                for attempt in range(1, self.config.battle_camera_pan_repeats + 1):
                    logger.info("Battle camera diagonal pan up-right attempt {}/{}", attempt, self.config.battle_camera_pan_repeats)
                    self.device.swipe_percent(72.0, 35.0, 25.0, 82.0, self.config.battle_camera_pan_swipe_duration_ms)
                    time.sleep(self.config.battle_camera_pan_settle_seconds)
            else:
                for attempt in range(1, self.config.battle_camera_pan_repeats + 1):
                    logger.info("Battle camera pan up attempt {}/{}", attempt, self.config.battle_camera_pan_repeats)
                    self.device.swipe_percent(50.0, 30.0, 50.0, 82.0, self.config.battle_camera_pan_swipe_duration_ms)
                    time.sleep(self.config.battle_camera_pan_settle_seconds)
                for attempt in range(1, self.config.battle_camera_pan_repeats + 1):
                    logger.info("Battle camera pan right attempt {}/{}", attempt, self.config.battle_camera_pan_repeats)
                    self.device.swipe_percent(72.0, 50.0, 25.0, 50.0, self.config.battle_camera_pan_swipe_duration_ms)
                    time.sleep(self.config.battle_camera_pan_settle_seconds)
        time.sleep(self.config.battle_camera_center_settle_seconds)
        if self.config.calibration_overlay_enabled and self.config.calibration_overlay_after_camera_prepare:
            screenshot = self.vision.screenshot_array()
            self.calibration.save_overlay(screenshot, self.config.calibration_overlay_dir, "after-camera-prepare")

    def _tap(self, point: RelativePoint) -> None:
        self.device.tap_percent(point.x, point.y)

    def _deploy_points_for_step(self, group: str) -> list[RelativePoint]:
        if group == "troops":
            return self.config.troop_deploy_points
        if group == "heroes":
            return self.config.hero_deploy_points
        return self.config.default_deploy_points

    def _deploy_step_to_primary_and_fallbacks(self, step: DeployStep) -> None:
        taps_count = max(1, step.deploy_taps)
        deploy_points = self._fast_deploy_points_for_step(step)
        logger.info(
            "Deploying {} to primary point and parallel-tapping {} deploy points {} times",
            step.name,
            len(deploy_points),
            taps_count,
        )
        if step.deploy_hold_seconds > 0:
            self.device.hold_percent(
                self.config.primary_deploy_point.x,
                self.config.primary_deploy_point.y,
                step.deploy_hold_seconds,
            )
            if step.deploy_point_group == "primary":
                return
        else:
            for _ in range(taps_count):
                self._tap(self.config.primary_deploy_point)
                time.sleep(self.config.rapid_deploy_tap_delay_seconds)

        burst_started_at = time.monotonic()
        burst_duration_seconds = 1.0 if step.deploy_point_group == "troops" else 0.0
        marker_detected = False
        for tap_index in range(taps_count):
            if step.deploy_point_group == "troops" and self.config.fallback_deploy_hold_seconds > 0:
                self._hold_neighbor_batches(deploy_points, self.config.fallback_deploy_hold_seconds)
            else:
                self._tap_neighbor_batches(deploy_points)
            if (
                step.deploy_point_group != "troops"
                or not self.config.troop_marker_check_during_burst
                or not self.vision.has_troops_deployed_marker()
            ):
                if burst_duration_seconds > 0:
                    next_tap_at = burst_started_at + ((tap_index + 1) * burst_duration_seconds / taps_count)
                    time.sleep(max(0.0, next_tap_at - time.monotonic()))
                else:
                    time.sleep(self.config.rapid_deploy_tap_delay_seconds)
                continue
            logger.info("All troops marker found after {}; continuing with heroes/siege", step.name)
            marker_detected = True
            break
        if (
            step.deploy_point_group == "troops"
            and not marker_detected
            and not self.config.troop_marker_check_during_burst
            and self.vision.has_troops_deployed_marker()
        ):
            logger.info("All troops marker found after fast deploy burst")

    def _deploy_step_with_g_key(self, step: DeployStep) -> None:
        logger.info(
            "Deploying {} with emulator key {} presses={}",
            step.name,
            self.config.g_key_deploy_key,
            self.config.g_key_deploy_presses,
        )
        self.device.press_emulator_key(
            self.config.g_key_deploy_key,
            self.config.g_key_deploy_presses,
            self.config.g_key_deploy_press_delay_seconds,
        )
        if step.deploy_point_group == "troops":
            logger.info("Reinforcing {} with configured G deploy points", step.name)
            self._tap_neighbor_batches(self._fast_deploy_points_for_step(step))
        self._verify_troops_deployed(step)

    def _deploy_army_by_hotkeys(self) -> None:
        logger.info("Deploying home village army by direct LDPlayer hotkeys")
        self.device.press_emulator_key(
            self.config.home_hotkey_troop_key,
            1,
            self.config.home_hotkey_key_delay_seconds,
        )
        self._press_g_point_passes(
            self.config.home_hotkey_troop_key,
            self.config.home_hotkey_troop_g_point_passes,
        )

        for slot_key in self.config.home_hotkey_all_point_keys:
            self.device.press_emulator_key(slot_key, 1, self.config.home_hotkey_key_delay_seconds)
            self._press_g_point_passes(slot_key, self.config.home_hotkey_all_point_passes)

        spell_step = next((step for step in self.config.deploy_plan if step.name == "spells"), None)
        if spell_step is None:
            logger.warning("Spell step not found; skipping hotkey spell deploy")
            return
        self.device.press_emulator_key(
            self.config.home_hotkey_spell_key,
            1,
            self.config.home_hotkey_key_delay_seconds,
        )
        self._deploy_random_points(spell_step)
        self._activate_hotkey_hero_abilities()

    def _activate_hotkey_hero_abilities(self) -> None:
        if not self.config.home_hotkey_hero_keys:
            return
        if self.config.home_hotkey_hero_ability_delay_seconds > 0:
            logger.info(
                "Waiting before hotkey hero abilities: {} seconds",
                self.config.home_hotkey_hero_ability_delay_seconds,
            )
            time.sleep(self.config.home_hotkey_hero_ability_delay_seconds)
        logger.info("Activating hotkey hero abilities: {}", ", ".join(self.config.home_hotkey_hero_keys))
        for hero_key in self.config.home_hotkey_hero_keys:
            self.device.press_emulator_key(hero_key, 1, self.config.home_hotkey_key_delay_seconds)

    def _press_g_point_passes(self, slot_key: str, passes: int) -> None:
        logger.info(
            "Deploying slot {} through G points: points={} passes={}",
            slot_key,
            ", ".join(self.config.home_hotkey_g_point_keys),
            passes,
        )
        for pass_index in range(1, passes + 1):
            logger.info("Slot {} G-point pass {}/{}", slot_key, pass_index, passes)
            for point_key in self.config.home_hotkey_g_point_keys:
                self.device.press_emulator_key_combo(
                    self.config.g_key_deploy_key,
                    point_key,
                    1,
                    self.config.g_key_deploy_press_delay_seconds,
                )

    def _fast_deploy_points_for_step(self, step: DeployStep) -> list[tuple[float, float]]:
        return self._with_neighbor_points(self._deploy_points_for_step(step.deploy_point_group))

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

    def _verify_troops_deployed(self, step: DeployStep) -> None:
        if step.deploy_point_group != "troops" or not self.config.troops_deployed_template_path:
            return
        if self.vision.has_troops_deployed_marker():
            logger.info("All troops marker found after {}", step.name)
            return

        deploy_points = self._fast_deploy_points_for_step(step)
        for attempt in range(1, self.config.troop_deploy_verify_retries + 1):
            logger.warning("All troops marker not found; retrying G deploy points attempt {}", attempt)
            self._tap_neighbor_batches(deploy_points)
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)
            if self.vision.has_troops_deployed_marker():
                logger.info("All troops marker found after retry {}", attempt)
                return
        logger.warning("All troops marker was not found after deploy retries")

    def _tap_neighbor_batches(self, points: list[tuple[float, float]]) -> None:
        batch_size = 24
        for start in range(0, len(points), batch_size):
            self.device.tap_many_percent(points[start : start + batch_size])
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)

    def _hold_neighbor_batches(self, points: list[tuple[float, float]], seconds: float) -> None:
        batch_size = 12
        for start in range(0, len(points), batch_size):
            self.device.hold_many_percent(points[start : start + batch_size], seconds)
            time.sleep(self.config.rapid_deploy_tap_delay_seconds)

    def _fallback_hold_seconds_for_step(self, step: DeployStep) -> float:
        if step.deploy_point_group == "heroes" or step.name == "battle_machine":
            return self.config.hero_fallback_deploy_hold_seconds
        return self.config.fallback_deploy_hold_seconds

    def _activate_hero_abilities(self) -> None:
        if not self.config.hero_ability_slots:
            return
        if self.config.hero_ability_delay_seconds > 0:
            logger.info("Waiting before hero abilities: {} seconds", self.config.hero_ability_delay_seconds)
            time.sleep(self.config.hero_ability_delay_seconds)

        deploy_steps = {step.name: step for step in self.config.deploy_plan}
        logger.info("Activating hero abilities: {}", ", ".join(self.config.hero_ability_slots))
        for slot_name in self.config.hero_ability_slots:
            step = deploy_steps.get(slot_name)
            if step is None:
                logger.warning("Hero ability slot not found: {}", slot_name)
                continue
            self._tap(step.point)
            time.sleep(self.config.hero_ability_tap_delay_seconds)

    def _deploy_random_points(self, step: DeployStep) -> None:
        if step.random_deploy_area != "spells":
            logger.warning("Unknown random deploy area: {}", step.random_deploy_area)
            return

        taps_count = random.randint(step.random_taps_min, step.random_taps_max)
        logger.info("Deploying {} random spell taps", taps_count)
        for _ in range(taps_count):
            self._tap(self.config.spell_deploy_area.random_point())
            time.sleep(self.config.spell_tap_delay_seconds)
