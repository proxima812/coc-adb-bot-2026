from __future__ import annotations

import unittest

from coc_bot.ui import BotProcessController


class FakeProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_timeout: float | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeout = timeout
        return self.returncode or 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class BotProcessControllerTest(unittest.TestCase):
    def test_start_uses_factory_once_when_stopped(self) -> None:
        created: list[FakeProcess] = []
        controller = BotProcessController(
            process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": created.append(FakeProcess())
            or created[-1]
        )

        self.assertTrue(controller.start())
        self.assertEqual(len(created), 1)
        self.assertTrue(controller.is_running())

    def test_start_passes_attack_limit_to_factory(self) -> None:
        limits: list[int] = []
        controller = BotProcessController(
            process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": limits.append(max_attacks)
            or FakeProcess()
        )

        self.assertTrue(controller.start(max_attacks=25))
        self.assertEqual(limits, [25])

    def test_start_passes_account_cycle_to_factory(self) -> None:
        account_cycles: list[bool] = []
        controller = BotProcessController(
            process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": account_cycles.append(account_cycle)
            or FakeProcess()
        )

        self.assertTrue(controller.start(account_cycle=True))
        self.assertEqual(account_cycles, [True])

    def test_start_passes_bot_mode_to_factory(self) -> None:
        bot_modes: list[str] = []
        controller = BotProcessController(
            process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": bot_modes.append(bot_mode)
            or FakeProcess()
        )

        self.assertTrue(controller.start(bot_mode="builder"))
        self.assertEqual(bot_modes, ["builder"])

    def test_stop_terminates_running_process(self) -> None:
        process = FakeProcess()
        controller = BotProcessController(process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": process)
        controller.start()

        self.assertTrue(controller.stop())
        self.assertTrue(process.terminated)
        self.assertFalse(controller.is_running())

    def test_restart_stops_existing_process_and_starts_new_one(self) -> None:
        created: list[FakeProcess] = []
        controller = BotProcessController(
            process_factory=lambda max_attacks=0, account_cycle=False, bot_mode="home": created.append(FakeProcess())
            or created[-1]
        )
        controller.start()
        first = created[0]

        self.assertTrue(controller.restart())
        self.assertTrue(first.terminated)
        self.assertEqual(len(created), 2)
        self.assertTrue(controller.is_running())


if __name__ == "__main__":
    unittest.main()
