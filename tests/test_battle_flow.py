from __future__ import annotations

import random
import unittest

from coc_bot.battle_flow import BattleFlow
from coc_bot.config import BotConfig, DeployStep, RelativeArea, RelativePoint


class FakeDevice:
    def __init__(self) -> None:
        self.taps: list[tuple[float, float]] = []
        self.tap_batches: list[list[tuple[float, float]]] = []
        self.holds: list[tuple[float, float, float]] = []
        self.keys: list[tuple[str, int]] = []
        self.key_combos: list[tuple[str, str, int]] = []
        self.ctrl_wheel_ticks: list[int] = []

    def tap_percent(self, x: float, y: float) -> None:
        self.taps.append((round(x, 2), round(y, 2)))

    def tap_many_percent(self, points: list[tuple[float, float]]) -> None:
        self.tap_batches.append(points)

    def hold_percent(self, x: float, y: float, seconds: float) -> None:
        self.holds.append((x, y, seconds))

    def press_emulator_key(self, key: str, presses: int = 1, delay_seconds: float = 0.05) -> None:
        self.keys.append((key, presses))

    def press_emulator_key_combo(
        self,
        first_key: str,
        second_key: str,
        presses: int = 1,
        delay_seconds: float = 0.05,
    ) -> None:
        self.key_combos.append((first_key, second_key, presses))

    def ctrl_mouse_wheel_zoom_out(self, wheel_ticks: int = 1) -> None:
        self.ctrl_wheel_ticks.append(wheel_ticks)


class FakeVision:
    def __init__(self) -> None:
        self.free_results: list[bool] = []

    def has_troops_deployed_marker(self) -> bool:
        return False

    def has_free_button(self) -> bool:
        return self.free_results.pop(0) if self.free_results else False


class BattleFlowDeployTest(unittest.TestCase):
    def test_open_battle_collects_free_before_attack_start(self) -> None:
        device = FakeDevice()
        vision = FakeVision()
        vision.free_results = [True]
        config = BotConfig(
            base_search_tap_delay_seconds=0.0,
            base_attack_taps=[
                RelativePoint(x=1.0, y=10.0),
                RelativePoint(x=2.0, y=20.0),
                RelativePoint(x=3.0, y=30.0),
            ],
            home_free_first_tap_index=1,
            home_free_open_point=RelativePoint(x=4.0, y=40.0),
            home_free_collect_point=RelativePoint(x=5.0, y=50.0),
            home_free_close_point=RelativePoint(x=6.0, y=60.0),
            home_attack_start_point=RelativePoint(x=7.0, y=70.0),
        )
        flow = BattleFlow(device, vision, config)  # type: ignore[arg-type]

        flow._open_battle_from_base()

        self.assertEqual(
            device.taps,
            [
                (1.0, 10.0),
                (2.0, 20.0),
                (4.0, 40.0),
                (5.0, 50.0),
                (6.0, 60.0),
                (7.0, 70.0),
            ],
        )

    def test_hotkey_deploy_uses_troop_siege_heroes_and_middle_spells(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            deploy_mode="hotkeys",
            spell_tap_delay_seconds=0.0,
            home_hotkey_key_delay_seconds=0.0,
            g_key_deploy_press_delay_seconds=0.0,
            home_hotkey_troop_key="1",
            home_hotkey_troop_g_presses=8,
            home_hotkey_g_point_keys=["1", "2", "3", "4", "5", "6", "7", "8"],
            home_hotkey_troop_g_point_passes=3,
            home_hotkey_siege_key="2",
            home_hotkey_siege_g_presses=4,
            home_hotkey_all_point_keys=["2", "3", "4", "5", "6"],
            home_hotkey_all_point_passes=1,
            home_hotkey_hero_keys=["3", "4", "5", "6"],
            home_hotkey_hero_g_presses=4,
            home_hotkey_hero_ability_delay_seconds=0.0,
            home_hotkey_spell_key="7",
            spell_deploy_area=RelativeArea(x_min=50.0, x_max=50.0, y_min=50.0, y_max=50.0),
            deploy_plan=[
                DeployStep(
                    name="spells",
                    point=RelativePoint(x=54.0, y=86.0),
                    random_deploy_area="spells",
                    random_taps_min=2,
                    random_taps_max=2,
                )
            ],
        )
        flow = BattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        random.seed(1)
        flow._deploy_army()

        self.assertEqual(
            device.keys,
            [
                ("1", 1),
                ("2", 1),
                ("3", 1),
                ("4", 1),
                ("5", 1),
                ("6", 1),
                ("7", 1),
                ("3", 1),
                ("4", 1),
                ("5", 1),
                ("6", 1),
            ],
        )
        expected_dragon_combos = [("G", point, 1) for _ in range(3) for point in ["1", "2", "3", "4", "5", "6", "7", "8"]]
        expected_support_combos = [
            ("G", point, 1)
            for _slot in ["2", "3", "4", "5", "6"]
            for point in ["1", "2", "3", "4", "5", "6", "7", "8"]
        ]
        self.assertEqual(device.key_combos, [*expected_dragon_combos, *expected_support_combos])
        self.assertEqual(device.taps, [(50.0, 50.0), (50.0, 50.0)])

    def test_camera_can_use_direct_ctrl_mouse_wheel(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            battle_camera_direct_ctrl_scroll_enabled=True,
            battle_camera_direct_ctrl_scroll_ticks=3,
            calibration_overlay_enabled=False,
            battle_camera_center_settle_seconds=0.0,
        )
        flow = BattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        flow._prepare_battle_camera()

        self.assertEqual(device.ctrl_wheel_ticks, [3])

    def test_deploy_army_activates_hero_ability_before_spell_taps(self) -> None:
        device = FakeDevice()
        config = BotConfig(
            deploy_neighbor_taps_enabled=False,
            deploy_step_delay_seconds=0.0,
            rapid_deploy_tap_delay_seconds=0.0,
            pre_spell_delay_seconds=0.0,
            hero_ability_delay_seconds=0.0,
            hero_ability_tap_delay_seconds=0.0,
            spell_tap_delay_seconds=0.0,
            hero_ability_slots=["hero_3"],
            spell_deploy_area=RelativeArea(x_min=40.0, x_max=40.0, y_min=60.0, y_max=60.0),
            deploy_plan=[
                DeployStep(
                    name="hero_3",
                    point=RelativePoint(x=20.0, y=90.0),
                    deploy_taps=1,
                    deploy_point_group="heroes",
                ),
                DeployStep(
                    name="spells",
                    point=RelativePoint(x=30.0, y=90.0),
                    random_deploy_area="spells",
                    random_taps_min=2,
                    random_taps_max=2,
                ),
            ],
        )
        flow = BattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        random.seed(1)
        flow._deploy_army()

        self.assertEqual(
            device.taps,
            [
                (20.0, 90.0),
                (28.56, 32.11),
                (20.0, 90.0),
                (30.0, 90.0),
                (40.0, 60.0),
                (40.0, 60.0),
            ],
        )
        self.assertEqual(len(device.tap_batches), 1)


if __name__ == "__main__":
    unittest.main()
