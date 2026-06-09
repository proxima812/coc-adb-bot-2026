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

    def tap_percent(self, x: float, y: float) -> None:
        self.taps.append((round(x, 2), round(y, 2)))

    def tap_many_percent(self, points: list[tuple[float, float]]) -> None:
        self.tap_batches.append(points)

    def hold_percent(self, x: float, y: float, seconds: float) -> None:
        self.holds.append((x, y, seconds))


class FakeVision:
    def has_troops_deployed_marker(self) -> bool:
        return False


class BattleFlowDeployTest(unittest.TestCase):
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
