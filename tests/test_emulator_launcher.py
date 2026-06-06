from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from coc_bot.config import BotConfig
from coc_bot.emulator import EmulatorLauncher


class FakeDevice:
    def __init__(self) -> None:
        self.connected = 0

    def connect(self) -> None:
        self.connected += 1


class EmulatorLauncherTest(unittest.TestCase):
    def test_ldplayer_launch_command_uses_configured_player_path(self) -> None:
        commands: list[list[str]] = []
        sleeps: list[float] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            player = Path(tmp_dir) / "dnplayer.exe"
            player.write_text("", encoding="utf-8")
            config = BotConfig(emulator_type="ldplayer", ldplayer_player_path=str(player), ldplayer_instance="")
            launcher = EmulatorLauncher(config, popen=lambda cmd: commands.append(cmd), sleep=sleeps.append)

            launched = launcher.start()

        self.assertTrue(launched)
        self.assertEqual(commands, [[str(player)]])
        self.assertEqual(sleeps, [config.restart_delay_seconds])

    def test_start_and_connect_starts_emulator_then_connects_device(self) -> None:
        commands: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            player = Path(tmp_dir) / "dnplayer.exe"
            player.write_text("", encoding="utf-8")
            config = BotConfig(emulator_type="ldplayer", ldplayer_player_path=str(player), ldplayer_instance="")
            device = FakeDevice()
            launcher = EmulatorLauncher(config, popen=lambda cmd: commands.append(cmd), sleep=lambda _: None)

            launcher.start_and_connect(device)

        self.assertEqual(len(commands), 1)
        self.assertEqual(device.connected, 1)


if __name__ == "__main__":
    unittest.main()
