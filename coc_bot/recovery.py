from __future__ import annotations

import time

from loguru import logger

from .adb_device import AdbDevice
from .config import BotConfig
from .emulator import EmulatorLauncher


class RecoveryModule:
    def __init__(self, device: AdbDevice, config: BotConfig) -> None:
        self.device = device
        self.config = config
        self.emulator = EmulatorLauncher(config)

    def recover(self, reason: Exception) -> None:
        logger.exception("Bot cycle failed: {}", reason)
        logger.bind(action=True).info("Recovery started: reason={}", reason)
        for attempt in range(1, self.config.max_recovery_attempts + 1):
            try:
                logger.info("Recovery attempt {}/{}", attempt, self.config.max_recovery_attempts)
                logger.bind(action=True).info(
                    "Recovery attempt {}/{}",
                    attempt,
                    self.config.max_recovery_attempts,
                )
                self.emulator.start()
                self._connect_with_retries()
                self.device.force_stop_app(self.config.package_name)
                time.sleep(self.config.restart_delay_seconds)
                self.device.start_app(self.config.package_name)
                time.sleep(self.config.restart_delay_seconds)
                self.device.check()
                logger.bind(action=True).info("Recovery completed on attempt {}", attempt)
                return
            except Exception as exc:
                logger.warning("Recovery attempt failed: {}", exc)
                logger.bind(action=True).info("Recovery attempt failed: attempt={} error={}", attempt, exc)
                self.device.kill_server()
                time.sleep(self.config.restart_delay_seconds)
        raise RuntimeError("Recovery failed after max attempts") from reason

    def _connect_with_retries(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                self._log_adb_devices()
                self.device.connect()
                return
            except Exception as exc:
                last_error = exc
                logger.warning("ADB reconnect attempt {}/5 failed: {}", attempt, exc)
                time.sleep(self.config.restart_delay_seconds)
        raise RuntimeError(f"ADB reconnect failed after retries: {last_error}")

    def _log_adb_devices(self) -> None:
        try:
            result = self.device.host_run("devices", timeout=10)
            logger.info("ADB devices:\n{}", result.stdout.strip())
        except Exception as exc:
            logger.warning("Unable to list ADB devices: {}", exc)
