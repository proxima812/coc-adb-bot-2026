from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from .adb_device import AdbDevice
from .battle_flow import BattleFlow
from .config import load_config
from .emulator import EmulatorLauncher
from .health import HealthChecker
from .recovery import RecoveryModule
from .vision import VisionModule


def setup_logging(log_level: str) -> None:
    Path("logs").mkdir(exist_ok=True)
    logger.remove()
    logger.add("logs/bot.log", rotation="5 MB", retention=5, encoding="utf-8", level=log_level)
    logger.add(lambda message: print(message, end=""), level=log_level)


def main() -> None:
    config = load_config()
    setup_logging(config.log_level)
    device = AdbDevice(config.adb_path, config.device_serial, dry_run=config.dry_run)
    vision = VisionModule(device, config)
    battle_flow = BattleFlow(device, vision, config)
    recovery = RecoveryModule(device, config)
    health = HealthChecker(device, vision, config)
    emulator = EmulatorLauncher(config)

    emulator.start_and_connect(device)
    device.check()
    device.start_app(config.package_name)

    while True:
        try:
            battle_flow.dismiss_popups()
            health.check_before_cycle()
            battle_flow.run_once()
            time.sleep(config.cycle_delay_seconds)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            return
        except Exception as exc:
            try:
                saved = vision.save_debug_screenshot("cycle-error")
                if saved is not None:
                    logger.warning("Saved cycle error screenshot: {}", saved)
            except Exception as screenshot_exc:
                logger.warning("Unable to save cycle error screenshot: {}", screenshot_exc)
            recovery.recover(exc)


if __name__ == "__main__":
    main()
