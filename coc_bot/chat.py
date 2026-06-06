from __future__ import annotations

import time

from loguru import logger

from .adb_device import AdbDevice


class ClanChatModule:
    def __init__(self, device: AdbDevice) -> None:
        self.device = device

    def send_message(self, message: str) -> None:
        logger.info("Sending clan chat message")
        # Default 16:9 emulator coordinates. Tune after first real screenshot.
        self.device.tap(55, 365)
        time.sleep(0.8)
        self.device.tap(310, 705)
        time.sleep(0.3)
        self.device.text(message)
        time.sleep(0.3)
        self.device.keyevent(66)
