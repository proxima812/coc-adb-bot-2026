from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass(frozen=True)
class RelativePoint:
    x: float
    y: float


@dataclass(frozen=True)
class DeployTarget:
    name: str
    template_path: str


@dataclass(frozen=True)
class PopupTemplate:
    name: str
    template_path: str


@dataclass(frozen=True)
class DeployStep:
    name: str
    point: RelativePoint
    deploy_taps: int = 1
    deploy_hold_seconds: float = 0.0
    deploy_point_group: str = "default"
    random_deploy_area: str = ""
    random_taps_min: int = 0
    random_taps_max: int = 0


@dataclass(frozen=True)
class RelativeArea:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def random_point(self) -> RelativePoint:
        return RelativePoint(
            x=random.uniform(self.x_min, self.x_max),
            y=random.uniform(self.y_min, self.y_max),
        )

    def contains(self, point: RelativePoint) -> bool:
        return self.x_min <= point.x <= self.x_max and self.y_min <= point.y <= self.y_max


@dataclass(frozen=True)
class BotConfig:
    adb_path: str = r"D:\LDPlayer\LDPlayer9\adb.exe"
    ldplayer_player_path: str = r"D:\LDPlayer\LDPlayer9\dnplayer.exe"
    ldplayer_instance: str = ""
    emulator_type: str = "ldplayer"
    device_serial: str = "127.0.0.1:5555"
    package_name: str = "com.supercell.clashofclans"
    dry_run: bool = False
    log_level: str = "INFO"
    debug_screenshots_enabled: bool = True
    debug_screenshot_dir: str = "logs/screenshots"
    expected_screen_width: int = 0
    expected_screen_height: int = 0
    loot_min_gold: int = 500_000
    loot_min_elixir: int = 500_000
    loot_check_enabled: bool = False
    loot_ocr_attempts: int = 2
    next_base_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=92.27, y=70.87))
    clan_chat_message: str = "Hello clan!"
    cycle_delay_seconds: float = 2.0
    next_search_delay_seconds: float = 1.5
    restart_delay_seconds: float = 8.0
    max_recovery_attempts: int = 3
    wait_battle_seconds: float = 14.0
    wait_attack_ready_seconds: float = 12.0
    wait_after_deploy_seconds: float = 30.0
    tap_delay_seconds: float = 0.35
    deploy_step_delay_seconds: float = 0.15
    rapid_deploy_tap_delay_seconds: float = 0.05
    battle_camera_prepare_enabled: bool = True
    battle_camera_zoom_out_attempts: int = 2
    battle_camera_zoom_out_seconds: float = 0.35
    battle_camera_pan_enabled: bool = False
    battle_camera_pan_repeats: int = 1
    battle_camera_pan_mode: str = "separate"
    battle_camera_pan_swipe_duration_ms: int = 700
    battle_camera_pan_settle_seconds: float = 0.35
    battle_camera_center_settle_seconds: float = 0.25
    calibration_overlay_enabled: bool = False
    calibration_overlay_dir: str = "logs/calibration"
    calibration_overlay_grid_step_percent: float = 10.0
    calibration_overlay_after_camera_prepare: bool = True
    auto_deploy_boundaries_enabled: bool = False
    auto_deploy_scan_enabled: bool = False
    auto_deploy_scan_settle_seconds: float = 0.35
    auto_deploy_scan_swipe_duration_ms: int = 450
    auto_deploy_boundary_points: int = 19
    auto_deploy_boundary_min_points: int = 1
    auto_deploy_boundary_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=4.0, x_max=96.0, y_min=3.0, y_max=82.0))
    troop_marker_check_during_burst: bool = False
    troop_deploy_verify_retries: int = 2
    deploy_neighbor_taps_enabled: bool = True
    deploy_neighbor_offset_percent: float = 0.45
    fallback_deploy_hold_seconds: float = 0.0
    hero_fallback_deploy_hold_seconds: float = 0.4
    pre_spell_delay_seconds: float = 1.0
    hero_deploy_taps: int = 1
    hero_ability_delay_seconds: float = 1.0
    hero_ability_tap_delay_seconds: float = 0.5
    hero_ability_slots: list[str] = field(default_factory=lambda: ["hero_3", "hero_4", "hero_5", "hero_6"])
    base_search_tap_delay_seconds: float = 0.5
    spell_tap_delay_seconds: float = 0.08
    battle_template_path: str = "assets/templates/end_battle.png"
    battle_template_threshold: float = 0.82
    popup_template_threshold: float = 0.78
    okay_button_enabled: bool = True
    okay_button_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=50.32, y=79.04))
    okay_button_detection_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=34.0, x_max=66.0, y_min=76.0, y_max=92.0))
    account_switch_tap_delay_seconds: float = 1.0
    account_settings_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=96.06, y=72.22))
    account_change_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=64.5, y=21.0))
    account_proxima_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=68.06, y=61.22))
    account_yung_proxima_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=68.0, y=77.22))
    account_old_proxima_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=68.0, y=93.11))
    popup_templates: list[PopupTemplate] = field(
        default_factory=lambda: [
            PopupTemplate(name="star_bonus_title", template_path="assets/templates/popups/star_bonus_title.png"),
            PopupTemplate(name="star_bonus_stars", template_path="assets/templates/popups/star_bonus_stars.png"),
            PopupTemplate(name="star_bonus_okay_1", template_path="assets/templates/popups/star_bonus_okay_1.png"),
            PopupTemplate(name="star_bonus_okay_2", template_path="assets/templates/popups/star_bonus_okay_2.png"),
            PopupTemplate(name="star_bonus_builder_title", template_path="assets/templates/popups/star_bonus_builder_title.png"),
            PopupTemplate(name="okay_green_builder", template_path="assets/templates/popups/okay_green_builder.png"),
            PopupTemplate(name="hero_skin_dragon", template_path="assets/templates/popups/hero_skin_dragon.png"),
            PopupTemplate(name="hero_skin_title", template_path="assets/templates/popups/hero_skin_title.png"),
        ]
    )
    deploy_template_threshold: float = 0.78
    troops_deployed_template_path: str = ""
    troops_deployed_template_threshold: float = 0.78
    troops_deployed_detection_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=24.0, y_min=78.0, y_max=100.0))
    attack_template_path: str = ""
    attack_template_paths: list[str] = field(default_factory=list)
    star_bonus_template_paths: list[str] = field(
        default_factory=lambda: [
            "assets/templates/builder/star_bonus_counter_0_9.png",
            "assets/templates/builder/star_bonus_counter_blue.png",
            "assets/templates/builder/star_bonus_counter_gold.png",
        ]
    )
    next_template_path: str = ""
    next_template_paths: list[str] = field(default_factory=list)
    attack_template_threshold: float = 0.78
    star_bonus_template_threshold: float = 0.78
    next_template_threshold: float = 0.78
    state_confirmations_required: int = 2
    health_state_attempts: int = 4
    health_state_retry_delay_seconds: float = 1.0
    battle_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=22.0, y_min=64.0, y_max=84.0))
    next_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=78.0, x_max=100.0, y_min=58.0, y_max=86.0))
    attack_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=36.0, y_min=66.0, y_max=96.0))
    star_bonus_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=36.0, y_min=0.0, y_max=24.0))
    deploy_mode: str = "coordinates"
    bot_mode: str = "home"
    g_key_deploy_key: str = "G"
    g_key_deploy_presses: int = 5
    g_key_deploy_press_delay_seconds: float = 0.05
    deploy_slot_detection_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=100.0, y_min=67.0, y_max=100.0))
    state_ocr_bottom_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=97.5, y_min=64.36, y_max=100.0))
    state_ocr_battle_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=97.5, y_min=64.36, y_max=100.0))
    state_ocr_village_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=97.5, y_min=67.56, y_max=100.0))
    state_ocr_top_left_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=38.0, y_min=0.0, y_max=45.0))
    primary_deploy_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=28.56, y=32.11))
    fallback_deploy_points: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=28.56, y=32.11),
            RelativePoint(x=39.44, y=19.67),
            RelativePoint(x=60.44, y=24.0),
            RelativePoint(x=75.81, y=44.0),
            RelativePoint(x=86.31, y=57.78),
            RelativePoint(x=17.63, y=46.11),
            RelativePoint(x=77.44, y=72.0),
            RelativePoint(x=12.56, y=65.89),
        ]
    )
    default_deploy_points: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=28.56, y=32.11),
        ]
    )
    troop_deploy_points: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=28.56, y=32.11),
            RelativePoint(x=39.44, y=19.67),
            RelativePoint(x=60.44, y=24.0),
            RelativePoint(x=75.81, y=44.0),
            RelativePoint(x=86.31, y=57.78),
            RelativePoint(x=17.63, y=46.11),
            RelativePoint(x=77.44, y=72.0),
            RelativePoint(x=12.56, y=65.89),
        ]
    )
    hero_deploy_points: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=28.56, y=32.11),
        ]
    )
    spell_deploy_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=35.0, x_max=65.0, y_min=35.0, y_max=65.0))
    deploy_plan: list[DeployStep] = field(
        default_factory=lambda: [
            DeployStep(
                name="new_troop_1",
                point=RelativePoint(x=6.44, y=95.11),
                deploy_taps=1,
                deploy_point_group="troops",
            ),
            DeployStep(name="battle_machine", point=RelativePoint(x=15.31, y=85.89), deploy_taps=1),
            DeployStep(name="hero_3", point=RelativePoint(x=23.31, y=85.33), deploy_taps=1),
            DeployStep(name="hero_4", point=RelativePoint(x=31.13, y=85.11), deploy_taps=1),
            DeployStep(name="hero_5", point=RelativePoint(x=38.44, y=85.56), deploy_taps=1),
            DeployStep(name="hero_6", point=RelativePoint(x=45.5, y=85.33), deploy_taps=1),
            DeployStep(
                name="spells",
                point=RelativePoint(x=54.19, y=85.67),
                random_deploy_area="spells",
                random_taps_min=11,
                random_taps_max=13,
            ),
        ]
    )
    deploy_targets: list[DeployTarget] = field(
        default_factory=lambda: [
            DeployTarget(name="target_01", template_path="assets/templates/deploy/target_01.png"),
            DeployTarget(name="target_02", template_path="assets/templates/deploy/target_02.png"),
            DeployTarget(name="target_03", template_path="assets/templates/deploy/target_03.png"),
            DeployTarget(name="target_04", template_path="assets/templates/deploy/target_04.png"),
            DeployTarget(name="target_05", template_path="assets/templates/deploy/target_05.png"),
            DeployTarget(name="target_06", template_path="assets/templates/deploy/target_06.png"),
            DeployTarget(name="target_07", template_path="assets/templates/deploy/target_07.png"),
            DeployTarget(name="target_08", template_path="assets/templates/deploy/target_08.png"),
        ]
    )
    base_attack_taps: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=6.88, y=87.33),
            RelativePoint(x=16.75, y=73.22),
            RelativePoint(x=89.56, y=88.67),
        ]
    )
    troop_deploy_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=28.56, y=32.11))
    end_battle_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=6.88, y=74.83))
    confirm_end_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=60.8, y=64.33))
    return_home_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=49.95, y=85.22))
    builder_attack_taps: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=6.81, y=88.78),
            RelativePoint(x=74.5, y=65.78),
        ]
    )
    builder_troop_slots: list[RelativePoint] = field(
        default_factory=lambda: [
            RelativePoint(x=10.94, y=88.89),
            RelativePoint(x=19.56, y=89.44),
            RelativePoint(x=26.19, y=89.22),
            RelativePoint(x=35.63, y=88.67),
            RelativePoint(x=42.88, y=88.44),
            RelativePoint(x=49.81, y=88.33),
            RelativePoint(x=57.81, y=88.67),
            RelativePoint(x=66.63, y=88.56),
        ]
    )
    builder_deploy_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=9.69, y=51.22))
    builder_return_home_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=50.38, y=83.33))
    builder_first_slot_retap_interval_seconds: float = 7.0
    builder_redeploy_slots_interval_seconds: float = 25.0
    builder_first_slot_retap_enabled: bool = False
    builder_redeploy_slots_enabled: bool = True
    builder_hero_ability_enabled: bool = True
    builder_hero_ability_point: RelativePoint = field(default_factory=lambda: RelativePoint(x=5.7, y=90.0))
    builder_hero_ability_interval_seconds: float = 10.0
    builder_slot_state_checks_enabled: bool = True
    builder_slot_state_check_passes: int = 2
    builder_slot_state_check_delay_seconds: float = 0.25
    builder_battle_timeout_seconds: float = 240.0
    builder_state_poll_seconds: float = 1.0
    builder_tap_overlay_enabled: bool = True
    builder_tap_overlay_dir: str = "logs/calibration/builder"
    builder_tap_overlay_max_per_cycle: int = 200
    builder_calibration_enabled: bool = True
    builder_calibration_max_screen_drift_percent: float = 2.0
    builder_safe_tap_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=100.0, y_min=0.0, y_max=96.0))
    builder_forbidden_tap_areas: list[RelativeArea] = field(
        default_factory=lambda: [
            RelativeArea(x_min=72.0, x_max=100.0, y_min=78.0, y_max=100.0),
            RelativeArea(x_min=82.0, x_max=100.0, y_min=58.0, y_max=78.0),
            RelativeArea(x_min=0.0, x_max=8.0, y_min=0.0, y_max=18.0),
        ]
    )
    builder_attack_template_paths: list[str] = field(
        default_factory=lambda: [
            "assets/templates/builder/attack_1.png",
            "assets/templates/builder/attack_2.png",
            "assets/templates/builder/base_attack_star_partial.png",
            "assets/templates/builder/base_attack_axes.png",
            "assets/templates/builder/base_attack_text.png",
        ]
    )
    builder_find_match_template_paths: list[str] = field(default_factory=lambda: ["assets/templates/builder/attack_2.png"])
    builder_slot_not_deployed_template_paths: list[str] = field(default_factory=lambda: ["assets/templates/builder/slots/not_deployed.png"])
    builder_slot_deployed_template_paths: list[str] = field(
        default_factory=lambda: [
            "assets/templates/builder/slots/deployed.png",
            "assets/templates/builder/slots/deployed_alt.png",
        ]
    )
    builder_slot_ability_ready_template_paths: list[str] = field(default_factory=lambda: ["assets/templates/builder/slots/ability_ready.png"])
    builder_hero_present_template_paths: list[str] = field(default_factory=lambda: ["assets/templates/builder/slots/hero_present.png"])
    builder_battle_template_paths: list[str] = field(default_factory=list)
    builder_return_home_template_paths: list[str] = field(default_factory=list)
    builder_attack_template_threshold: float = 0.78
    builder_find_match_template_threshold: float = 0.78
    builder_slot_state_template_threshold: float = 0.78
    builder_hero_present_template_threshold: float = 0.72
    builder_battle_template_threshold: float = 0.78
    builder_return_home_template_threshold: float = 0.78
    builder_attack_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=26.0, y_min=65.0, y_max=96.0))
    builder_find_match_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=55.0, x_max=84.0, y_min=50.0, y_max=76.0))
    builder_slot_state_area_radius_x: float = 4.5
    builder_slot_state_area_y_min_offset: float = -18.0
    builder_slot_state_area_y_max_offset: float = 2.5
    builder_hero_present_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=12.0, y_min=66.0, y_max=100.0))
    builder_battle_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=0.0, x_max=100.0, y_min=0.0, y_max=100.0))
    builder_return_home_template_area: RelativeArea = field(default_factory=lambda: RelativeArea(x_min=34.0, x_max=66.0, y_min=72.0, y_max=94.0))


def _point(raw: dict[str, float] | RelativePoint) -> RelativePoint:
    if isinstance(raw, RelativePoint):
        return raw
    point = RelativePoint(x=float(raw["x"]), y=float(raw["y"]))
    if not 0 <= point.x <= 100 or not 0 <= point.y <= 100:
        raise ValueError(f"Relative point out of range: {point}")
    return point


def _area(raw: dict[str, float] | RelativeArea) -> RelativeArea:
    if isinstance(raw, RelativeArea):
        return raw
    area = RelativeArea(
        x_min=float(raw["x_min"]),
        x_max=float(raw["x_max"]),
        y_min=float(raw["y_min"]),
        y_max=float(raw["y_max"]),
    )
    if not 0 <= area.x_min <= area.x_max <= 100 or not 0 <= area.y_min <= area.y_max <= 100:
        raise ValueError(f"Relative area out of range: {area}")
    return area


def _config_from_dict(raw: dict) -> BotConfig:
    data = dict(raw)
    valid_keys = {field.name for field in fields(BotConfig)}
    unknown_keys = sorted(set(data) - valid_keys)
    if unknown_keys:
        raise ValueError(f"Unknown bot config key(s): {', '.join(unknown_keys)}")
    if "base_attack_taps" in data:
        data["base_attack_taps"] = [_point(item) for item in data["base_attack_taps"]]
    if "builder_attack_taps" in data:
        data["builder_attack_taps"] = [_point(item) for item in data["builder_attack_taps"]]
    if "builder_troop_slots" in data:
        data["builder_troop_slots"] = [_point(item) for item in data["builder_troop_slots"]]
    if "deploy_targets" in data:
        data["deploy_targets"] = [DeployTarget(**item) for item in data["deploy_targets"]]
    if "popup_templates" in data:
        data["popup_templates"] = [PopupTemplate(**item) for item in data["popup_templates"]]
    if "deploy_plan" in data:
        data["deploy_plan"] = [
            DeployStep(
                name=item["name"],
                point=_point(item["point"]),
                deploy_taps=int(item.get("deploy_taps", 1)),
                deploy_hold_seconds=float(item.get("deploy_hold_seconds", 0.0)),
                deploy_point_group=str(item.get("deploy_point_group", "default")),
                random_deploy_area=str(item.get("random_deploy_area", "")),
                random_taps_min=int(item.get("random_taps_min", 0)),
                random_taps_max=int(item.get("random_taps_max", 0)),
            )
            for item in data["deploy_plan"]
        ]
    for key in (
        "next_base_point",
        "primary_deploy_point",
        "troop_deploy_point",
        "end_battle_point",
        "confirm_end_point",
        "return_home_point",
        "okay_button_point",
        "account_settings_point",
        "account_change_point",
        "account_proxima_point",
        "account_yung_proxima_point",
        "account_old_proxima_point",
        "builder_deploy_point",
        "builder_return_home_point",
        "builder_hero_ability_point",
    ):
        if key in data:
            data[key] = _point(data[key])
    for key in ("fallback_deploy_points", "default_deploy_points", "troop_deploy_points", "hero_deploy_points"):
        if key in data:
            data[key] = [_point(item) for item in data[key]]
    for key in (
        "spell_deploy_area",
        "auto_deploy_boundary_area",
        "battle_template_area",
        "next_template_area",
        "attack_template_area",
        "star_bonus_template_area",
        "deploy_slot_detection_area",
        "troops_deployed_detection_area",
        "state_ocr_bottom_area",
        "state_ocr_battle_area",
        "state_ocr_village_area",
        "state_ocr_top_left_area",
        "okay_button_detection_area",
        "builder_attack_template_area",
        "builder_find_match_template_area",
        "builder_hero_present_template_area",
        "builder_battle_template_area",
        "builder_return_home_template_area",
        "builder_safe_tap_area",
    ):
        if key in data:
            data[key] = _area(data[key])
    if "builder_forbidden_tap_areas" in data:
        data["builder_forbidden_tap_areas"] = [_area(item) for item in data["builder_forbidden_tap_areas"]]
    return BotConfig(**data)


def validate_config(config: BotConfig) -> None:
    errors: list[str] = []

    def check_point(name: str, point: RelativePoint) -> None:
        if not 0 <= point.x <= 100 or not 0 <= point.y <= 100:
            errors.append(f"{name} out of range: {point}")

    def check_area(name: str, area: RelativeArea) -> None:
        if not 0 <= area.x_min <= area.x_max <= 100 or not 0 <= area.y_min <= area.y_max <= 100:
            errors.append(f"{name} out of range: {area}")

    for name in (
        "next_base_point",
        "primary_deploy_point",
        "troop_deploy_point",
        "end_battle_point",
        "confirm_end_point",
        "return_home_point",
        "okay_button_point",
        "account_settings_point",
        "account_change_point",
        "account_proxima_point",
        "account_yung_proxima_point",
        "account_old_proxima_point",
        "builder_deploy_point",
        "builder_return_home_point",
    ):
        check_point(name, getattr(config, name))
    for index, point in enumerate(config.base_attack_taps):
        check_point(f"base_attack_taps[{index}]", point)
    for index, point in enumerate(config.builder_attack_taps):
        check_point(f"builder_attack_taps[{index}]", point)
    for index, point in enumerate(config.builder_troop_slots):
        check_point(f"builder_troop_slots[{index}]", point)
    for index, point in enumerate(config.fallback_deploy_points):
        check_point(f"fallback_deploy_points[{index}]", point)
    for index, step in enumerate(config.deploy_plan):
        check_point(f"deploy_plan[{index}].point", step.point)
        if step.deploy_taps < 0:
            errors.append(f"deploy_plan[{index}].deploy_taps must be >= 0")
        if step.deploy_hold_seconds < 0:
            errors.append(f"deploy_plan[{index}].deploy_hold_seconds must be >= 0")
        if step.random_taps_min < 0 or step.random_taps_max < 0 or step.random_taps_min > step.random_taps_max:
            errors.append(f"deploy_plan[{index}] random tap range is invalid")

    deploy_step_names = {step.name for step in config.deploy_plan}
    for slot in config.hero_ability_slots:
        if slot not in deploy_step_names:
            errors.append(f"hero_ability_slots item not found in deploy_plan: {slot}")
    if config.hero_deploy_taps < 1:
        errors.append("hero_deploy_taps must be >= 1")
    if config.troop_deploy_verify_retries < 0:
        errors.append("troop_deploy_verify_retries must be >= 0")
    if config.deploy_neighbor_offset_percent < 0:
        errors.append("deploy_neighbor_offset_percent must be >= 0")
    if config.state_confirmations_required < 1:
        errors.append("state_confirmations_required must be >= 1")
    if config.health_state_attempts < 1:
        errors.append("health_state_attempts must be >= 1")
    if config.auto_deploy_boundary_points < 1:
        errors.append("auto_deploy_boundary_points must be >= 1")
    if config.auto_deploy_boundary_min_points < 1:
        errors.append("auto_deploy_boundary_min_points must be >= 1")
    if config.auto_deploy_scan_swipe_duration_ms < 0:
        errors.append("auto_deploy_scan_swipe_duration_ms must be >= 0")
    if config.battle_camera_zoom_out_attempts < 0:
        errors.append("battle_camera_zoom_out_attempts must be >= 0")
    if config.battle_camera_pan_repeats < 0:
        errors.append("battle_camera_pan_repeats must be >= 0")
    if config.battle_camera_pan_swipe_duration_ms < 0:
        errors.append("battle_camera_pan_swipe_duration_ms must be >= 0")
    if config.battle_camera_pan_mode not in ("separate", "diagonal"):
        errors.append(f"battle_camera_pan_mode must be separate or diagonal, got {config.battle_camera_pan_mode}")
    if config.calibration_overlay_grid_step_percent <= 0 or config.calibration_overlay_grid_step_percent > 100:
        errors.append("calibration_overlay_grid_step_percent must be > 0 and <= 100")

    for name in (
        "spell_deploy_area",
        "auto_deploy_boundary_area",
        "battle_template_area",
        "next_template_area",
        "attack_template_area",
        "star_bonus_template_area",
        "deploy_slot_detection_area",
        "troops_deployed_detection_area",
        "state_ocr_bottom_area",
        "state_ocr_battle_area",
        "state_ocr_village_area",
        "state_ocr_top_left_area",
        "okay_button_detection_area",
        "builder_attack_template_area",
        "builder_find_match_template_area",
        "builder_battle_template_area",
        "builder_return_home_template_area",
        "builder_safe_tap_area",
    ):
        check_area(name, getattr(config, name))
    for index, area in enumerate(config.builder_forbidden_tap_areas):
        check_area(f"builder_forbidden_tap_areas[{index}]", area)

    for name in (
        "cycle_delay_seconds",
        "next_search_delay_seconds",
        "restart_delay_seconds",
        "health_state_retry_delay_seconds",
        "wait_battle_seconds",
        "wait_attack_ready_seconds",
        "wait_after_deploy_seconds",
        "tap_delay_seconds",
        "deploy_step_delay_seconds",
        "rapid_deploy_tap_delay_seconds",
        "battle_camera_zoom_out_seconds",
        "battle_camera_pan_settle_seconds",
        "battle_camera_center_settle_seconds",
        "calibration_overlay_grid_step_percent",
        "auto_deploy_scan_settle_seconds",
        "deploy_neighbor_offset_percent",
        "fallback_deploy_hold_seconds",
        "hero_fallback_deploy_hold_seconds",
        "pre_spell_delay_seconds",
        "hero_ability_delay_seconds",
        "hero_ability_tap_delay_seconds",
        "base_search_tap_delay_seconds",
        "spell_tap_delay_seconds",
        "account_switch_tap_delay_seconds",
        "builder_first_slot_retap_interval_seconds",
        "builder_redeploy_slots_interval_seconds",
        "builder_hero_ability_interval_seconds",
        "builder_slot_state_check_delay_seconds",
        "builder_battle_timeout_seconds",
        "builder_state_poll_seconds",
        "builder_calibration_max_screen_drift_percent",
        "builder_slot_state_area_radius_x",
    ):
        if getattr(config, name) < 0:
            errors.append(f"{name} must be >= 0")
    if config.builder_slot_state_check_passes < 0:
        errors.append("builder_slot_state_check_passes must be >= 0")
    if config.builder_tap_overlay_max_per_cycle < 0:
        errors.append("builder_tap_overlay_max_per_cycle must be >= 0")

    for template_path in [config.battle_template_path, *(popup.template_path for popup in config.popup_templates)]:
        if template_path and not Path(template_path).exists():
            errors.append(f"template not found: {template_path}")
    optional_templates = [
        config.attack_template_path,
        config.next_template_path,
        config.troops_deployed_template_path,
        *config.attack_template_paths,
        *config.star_bonus_template_paths,
        *config.next_template_paths,
        *config.builder_attack_template_paths,
        *config.builder_find_match_template_paths,
        *config.builder_slot_not_deployed_template_paths,
        *config.builder_slot_deployed_template_paths,
        *config.builder_slot_ability_ready_template_paths,
        *config.builder_hero_present_template_paths,
        *config.builder_battle_template_paths,
        *config.builder_return_home_template_paths,
    ]
    for optional_template in optional_templates:
        if optional_template and not Path(optional_template).exists():
            errors.append(f"template not found: {optional_template}")

    if not config.fallback_deploy_points:
        errors.append("fallback_deploy_points should contain at least one G point")
    if config.deploy_mode not in ("coordinates", "templates", "g_key"):
        errors.append(f"deploy_mode must be coordinates, templates, or g_key, got {config.deploy_mode}")
    if config.bot_mode not in ("home", "builder"):
        errors.append(f"bot_mode must be home or builder, got {config.bot_mode}")
    if config.g_key_deploy_presses < 1:
        errors.append("g_key_deploy_presses must be >= 1")
    if config.g_key_deploy_press_delay_seconds < 0:
        errors.append("g_key_deploy_press_delay_seconds must be >= 0")
    if config.builder_redeploy_slots_interval_seconds <= 0:
        errors.append("builder_redeploy_slots_interval_seconds must be > 0")
    if config.emulator_type != "ldplayer":
        errors.append(f"emulator_type must be ldplayer, got {config.emulator_type}")

    if errors:
        raise ValueError("Invalid bot config:\n- " + "\n- ".join(errors))


def load_config(path: str | Path = "config.json") -> BotConfig:
    config_path = Path(path)
    if not config_path.exists():
        example_path = Path("config.example.json")
        if example_path.exists():
            raw = json.loads(example_path.read_text(encoding="utf-8-sig"))
            config = _config_from_dict(raw)
            validate_config(config)
            return config
        config = BotConfig()
        validate_config(config)
        return config

    raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    config = _config_from_dict(raw)
    validate_config(config)
    return config
