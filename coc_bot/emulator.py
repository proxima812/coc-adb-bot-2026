from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from .adb_device import AdbDevice
from .config import BotConfig


class EmulatorLauncher:
    def __init__(
        self,
        config: BotConfig,
        popen: Callable[[list[str]], object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._popen = popen or self._default_popen
        self._sleep = sleep

    def start(self) -> bool:
        player_path = Path(self.config.ldplayer_player_path)
        if not player_path.exists():
            logger.warning("LDPlayer not found: {}", player_path)
            return False

        command = [str(player_path)]
        if self.config.ldplayer_instance:
            command.extend(["--index", self.config.ldplayer_instance])

        logger.info("Starting LDPlayer: {}", " ".join(command))
        self._popen(command)
        self._sleep(self.config.restart_delay_seconds)
        return True

    def start_and_connect(self, device: AdbDevice) -> None:
        self.start()
        device.connect()

    @staticmethod
    def _default_popen(command: list[str]) -> subprocess.Popen:
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
