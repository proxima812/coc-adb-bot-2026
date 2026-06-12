from __future__ import annotations

import dataclasses
import unittest

from coc_bot.battle_flow import BattleFlow
from coc_bot.config import BotConfig, apply_home_hotkey_strategy


class FakeDevice:
    def __init__(self) -> None:
        self.keys: list[tuple[str, int, float]] = []
        self.combos: list[tuple[str, str, int, float]] = []
        self.combo_holds: list[tuple[str, str, float]] = []
        self.taps: list[tuple[float, float]] = []

    def press_emulator_key(self, key: str, presses: int, delay_seconds: float) -> None:
        self.keys.append((key, presses, delay_seconds))

    def press_emulator_key_combo(self, modifier_key: str, key: str, presses: int, delay_seconds: float) -> None:
        self.combos.append((modifier_key, key, presses, delay_seconds))

    def hold_emulator_key_combo(self, modifier_key: str, key: str, hold_seconds: float) -> None:
        self.combo_holds.append((modifier_key, key, hold_seconds))

    def tap_percent(self, x: float, y: float) -> None:
        self.taps.append((x, y))


class FakeVision:
    pass


class HomeHotkeyStrategyTest(unittest.TestCase):
    def test_one_troop_slot_keeps_layout_but_holds_g9_for_troops(self) -> None:
        config = BotConfig(
            home_hotkey_troop_key="1",
            home_hotkey_troop_g_point_keys=["1", "2", "3"],
            home_hotkey_troop_g_point_hold_seconds=0.0,
            home_hotkey_g_point_keys=["1", "2", "3"],
            home_hotkey_all_point_keys=["2", "3", "4", "5", "6"],
            home_hotkey_hero_keys=["3", "4", "5", "6"],
            home_hotkey_spell_key="7",
        )

        updated = apply_home_hotkey_strategy(config, 1)

        self.assertEqual(updated.home_hotkey_troop_key, "1")
        self.assertEqual(updated.home_hotkey_troop_keys, ["1"])
        self.assertEqual(updated.home_hotkey_troop_g_point_keys, ["9"])
        self.assertEqual(updated.home_hotkey_troop_g_point_hold_seconds, 1.0)
        self.assertEqual(updated.home_hotkey_g_point_keys, ["1"])
        self.assertEqual(updated.home_hotkey_all_point_keys, ["2", "3", "4", "5", "6"])
        self.assertEqual(updated.home_hotkey_hero_keys, ["3", "4", "5", "6"])
        self.assertEqual(updated.home_hotkey_spell_key, "7")

    def test_two_troop_slots_shift_siege_heroes_and_spells(self) -> None:
        updated = apply_home_hotkey_strategy(BotConfig(), 2)

        self.assertEqual(updated.home_hotkey_troop_keys, ["1", "2"])
        self.assertEqual(updated.home_hotkey_g_point_keys, ["1"])
        self.assertEqual(updated.home_hotkey_siege_key, "3")
        self.assertEqual(updated.home_hotkey_all_point_keys, ["3", "4", "5", "6", "7"])
        self.assertEqual(updated.home_hotkey_hero_keys, ["4", "5", "6", "7"])
        self.assertEqual(updated.home_hotkey_spell_key, "8")

    def test_three_troop_slots_shift_siege_heroes_and_spells(self) -> None:
        updated = apply_home_hotkey_strategy(BotConfig(), 3)

        self.assertEqual(updated.home_hotkey_troop_keys, ["1", "2", "3"])
        self.assertEqual(updated.home_hotkey_g_point_keys, ["1"])
        self.assertEqual(updated.home_hotkey_siege_key, "4")
        self.assertEqual(updated.home_hotkey_all_point_keys, ["4", "5", "6", "7", "8"])
        self.assertEqual(updated.home_hotkey_hero_keys, ["5", "6", "7", "8"])
        self.assertEqual(updated.home_hotkey_spell_key, "9")

    def test_rejects_unsupported_troop_slot_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "home hotkey strategy troop slots must be 1, 2, or 3"):
            apply_home_hotkey_strategy(BotConfig(), 4)

    def test_hotkey_deploy_holds_g9_for_each_troop_slot(self) -> None:
        config = dataclasses.replace(
            apply_home_hotkey_strategy(BotConfig(), 3),
            home_hotkey_hero_ability_delay_seconds=0.0,
            spell_tap_delay_seconds=0.0,
            deploy_plan=[
                dataclasses.replace(
                    next(step for step in BotConfig().deploy_plan if step.name == "spells"),
                    random_taps_min=0,
                    random_taps_max=0,
                )
            ],
        )
        device = FakeDevice()
        flow = BattleFlow(device, FakeVision(), config)  # type: ignore[arg-type]

        flow._deploy_army_by_hotkeys()

        self.assertEqual(device.keys[:3], [("1", 1, 0.05), ("2", 1, 0.05), ("3", 1, 0.05)])
        self.assertEqual(device.combo_holds, [("G", "9", 1.0)] * 3)
        self.assertEqual(device.combos[:5], [("G", "1", 1, 0.05)] * 5)
        self.assertNotIn(("G", "2", 1, 0.05), device.combos[:5])
        self.assertNotIn(("G", "9", 1, 0.05), device.combos)


if __name__ == "__main__":
    unittest.main()
