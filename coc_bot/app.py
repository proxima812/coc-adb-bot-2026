from __future__ import annotations

from pathlib import Path

from loguru import logger

from .adb_device import AdbDevice
from .battle_flow import BattleFlow
from .builder_flow import BuilderBattleFlow
from .cli import parse_args
from .config import apply_home_hotkey_strategy, load_config
from .emulator import EmulatorLauncher
from .health import HealthChecker
from .recovery import RecoveryModule
from .runner import run_account_cycle, run_builder_loop, run_home_loop
from .telegram_notify import load_dotenv
from .vision import VisionModule


def setup_logging(log_level: str) -> None:
    Path("logs").mkdir(exist_ok=True)
    logger.remove()
    logger.add("logs/bot.log", rotation="5 MB", retention=5, encoding="utf-8", level=log_level)
    logger.add(
        "logs/actions.log",
        rotation="5 MB",
        retention=10,
        encoding="utf-8",
        level="INFO",
        filter=lambda record: bool(record["extra"].get("action")),
    )
    logger.add(lambda message: print(message, end=""), level=log_level)


def main() -> None:
    load_dotenv()
    args = parse_args()
    if args.max_attacks < 0:
        raise SystemExit("--max-attacks must be >= 0")
    if args.attacks_per_account < 1:
        raise SystemExit("--attacks-per-account must be >= 1")

    config = apply_home_hotkey_strategy(load_config(), args.home_troop_slots)
    setup_logging(config.log_level)
    bot_mode = args.bot_mode or config.bot_mode

    device = AdbDevice(config.adb_path, config.device_serial, dry_run=config.dry_run)
    vision = VisionModule(device, config)
    battle_flow = BattleFlow(device, vision, config)
    builder_flow = BuilderBattleFlow(device, vision, config)
    recovery = RecoveryModule(device, config)
    health = HealthChecker(device, vision, config)
    emulator = EmulatorLauncher(config)

    emulator.start_and_connect(device)
    device.check()
    device.start_app(config.package_name)

    if bot_mode == "builder":
        run_builder_loop(builder_flow, health, recovery, vision, config, args.max_attacks)
        return

    if args.account_cycle:
        accounts = [account.strip() for account in args.accounts.split(",") if account.strip()]
        if not accounts:
            raise SystemExit("--accounts must contain at least one account")
        run_account_cycle(device, battle_flow, health, recovery, vision, config, accounts, args.attacks_per_account)
        return

    run_home_loop(battle_flow, health, recovery, vision, config, args.max_attacks)
