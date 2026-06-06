from __future__ import annotations

import argparse
import time

from loguru import logger

from .adb_device import AdbDevice
from .config import BotConfig, RelativePoint, load_config
from .emulator import EmulatorLauncher
from .main import setup_logging


ACCOUNT_POINTS = {
    "proxima": "account_proxima_point",
    "yung_proxima": "account_yung_proxima_point",
    "old_proxima": "account_old_proxima_point",
}


class AccountSwitcher:
    def __init__(self, device: AdbDevice, config: BotConfig) -> None:
        self.device = device
        self.config = config

    def switch(self, account_name: str) -> None:
        point_attr = ACCOUNT_POINTS.get(account_name)
        if point_attr is None:
            raise ValueError(f"Unknown account: {account_name}")

        logger.info("Switching account: {}", account_name)
        self.device.connect()
        self.device.check()
        self._tap(self.config.account_settings_point)
        time.sleep(self.config.account_switch_tap_delay_seconds)
        self._tap(self.config.account_change_point)
        time.sleep(self.config.account_switch_tap_delay_seconds)
        self._tap(getattr(self.config, point_attr))
        time.sleep(self.config.account_switch_tap_delay_seconds)

    def _tap(self, point: RelativePoint) -> None:
        self.device.tap_percent(point.x, point.y)


def main() -> None:
    parser = argparse.ArgumentParser(description="Switch Clash of Clans account")
    parser.add_argument("account", choices=sorted(ACCOUNT_POINTS))
    args = parser.parse_args()

    config = load_config()
    setup_logging(config.log_level)
    device = AdbDevice(config.adb_path, config.device_serial, dry_run=config.dry_run)
    EmulatorLauncher(config).start_and_connect(device)
    device.start_app(config.package_name)
    time.sleep(config.restart_delay_seconds)
    AccountSwitcher(device, config).switch(args.account)


if __name__ == "__main__":
    main()
