from __future__ import annotations

import unittest

from coc_bot.config import BotConfig
from coc_bot.main import run_builder_loop


class FakeBuilderFlow:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_once(self) -> None:
        self.calls.append("run_once")


class FakeHealth:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def check_before_cycle(self) -> None:
        self.calls.append("check_before_cycle")


class FakeRecovery:
    def recover(self, exc: Exception) -> None:
        raise AssertionError(f"unexpected recovery: {exc}")


class FakeVision:
    def save_debug_screenshot(self, label: str) -> None:
        raise AssertionError(f"unexpected screenshot: {label}")


class MainLoopTest(unittest.TestCase):
    def test_builder_loop_checks_health_before_attack(self) -> None:
        flow = FakeBuilderFlow()
        health = FakeHealth()
        config = BotConfig(cycle_delay_seconds=0.0)

        run_builder_loop(flow, health, FakeRecovery(), FakeVision(), config, max_attacks=1)

        self.assertEqual(health.calls, ["check_before_cycle"])
        self.assertEqual(flow.calls, ["run_once"])


if __name__ == "__main__":
    unittest.main()
