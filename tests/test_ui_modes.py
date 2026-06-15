from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from coc_bot.ui import BotControlUi, mode_dependent_control_states


class UiModeTest(unittest.TestCase):
    def test_home_mode_keeps_home_only_controls_enabled(self) -> None:
        states = mode_dependent_control_states("home")

        self.assertEqual(states["strategy"], "normal")
        self.assertEqual(states["account_cycle"], "normal")

    def test_builder_mode_disables_home_only_controls(self) -> None:
        states = mode_dependent_control_states("builder")

        self.assertEqual(states["strategy"], "disabled")
        self.assertEqual(states["account_cycle"], "disabled")

    def test_ui_live_log_panel_is_disabled(self) -> None:
        self.assertFalse(BotControlUi.LOG_PANEL_ENABLED)

    def test_bot_process_keeps_child_output_out_of_ui(self) -> None:
        with mock.patch("coc_bot.ui.subprocess.Popen") as popen:
            BotControlUi.LOG_PANEL_ENABLED
            from coc_bot.ui import BotProcessController

            BotProcessController._default_process_factory(bot_mode="home", home_troop_slots=2)

        kwargs = popen.call_args.kwargs
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)


if __name__ == "__main__":
    unittest.main()
