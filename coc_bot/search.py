from __future__ import annotations

import time

from loguru import logger

from .adb_device import AdbDevice
from .config import BotConfig
from .vision import GameState, VisionModule


class SearchModule:
    def __init__(self, device: AdbDevice, vision: VisionModule, config: BotConfig) -> None:
        self.device = device
        self.vision = vision
        self.config = config

    def run_until_target_found(self) -> None:
        while True:
            state = self.vision.detect_state()
            logger.info("Game state: {}", state)

            if state == GameState.VILLAGE:
                self._start_attack_search()
                time.sleep(self.config.cycle_delay_seconds)
                continue

            if state == GameState.BATTLE:
                loot = self.vision.read_battle_loot()
                logger.info("Loot found: gold={}, elixir={}", loot.gold, loot.elixir)
                if loot.gold >= self.config.loot_min_gold and loot.elixir >= self.config.loot_min_elixir:
                    logger.info("Target accepted")
                    return
                self._next_base()
                time.sleep(self.config.next_search_delay_seconds)
                continue

            logger.warning("Unknown game state, waiting before retry")
            time.sleep(self.config.cycle_delay_seconds)

    def _start_attack_search(self) -> None:
        # Default 16:9 emulator coordinates. Tune later from screenshots/keymap.
        logger.info("Opening attack search")
        self.device.tap(90, 650)
        time.sleep(0.8)
        self.device.tap(1380, 520)

    def _next_base(self) -> None:
        logger.info("Skipping base")
        self.device.tap(1470, 640)
