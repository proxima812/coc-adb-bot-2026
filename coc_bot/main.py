from __future__ import annotations

import argparse
import time
from pathlib import Path

from loguru import logger

from .adb_device import AdbDevice
from .battle_flow import BattleFlow
from .builder_flow import BuilderBattleFlow
from .config import BotConfig, load_config
from .emulator import EmulatorLauncher
from .health import HealthChecker
from .recovery import RecoveryModule
from .telegram_notify import TelegramNotifier, load_dotenv
from .vision import VisionModule

DEFAULT_ACCOUNT_SEQUENCE = ("proxima", "yung_proxima", "old_proxima")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run COC bot")
    parser.add_argument(
        "--max-attacks",
        type=int,
        default=0,
        help="Stop after this many completed attacks. 0 means unlimited.",
    )
    parser.add_argument(
        "--account-cycle",
        action="store_true",
        help="Run 25 attacks on each configured account, notify Telegram, then stop.",
    )
    parser.add_argument(
        "--attacks-per-account",
        type=int,
        default=25,
        help="Completed attacks per account in account-cycle mode.",
    )
    parser.add_argument(
        "--accounts",
        default=",".join(DEFAULT_ACCOUNT_SEQUENCE),
        help="Comma-separated account names for account-cycle mode.",
    )
    parser.add_argument(
        "--bot-mode",
        choices=("home", "builder"),
        default="",
        help="Bot flow to run. Empty uses bot_mode from config.",
    )
    return parser.parse_args()


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

    config = load_config()
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


def run_home_loop(
    battle_flow: BattleFlow,
    health: HealthChecker,
    recovery: RecoveryModule,
    vision: VisionModule,
    config: BotConfig,
    max_attacks: int,
) -> None:
    completed_attacks = 0
    while True:
        try:
            battle_flow.dismiss_popups()
            health.check_before_cycle()
            battle_flow.run_once()
            completed_attacks += 1
            if max_attacks:
                logger.info("Completed attacks: {}/{}", completed_attacks, max_attacks)
                if completed_attacks >= max_attacks:
                    logger.info("Attack limit reached; stopping bot")
                    return
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


def run_account_cycle(
    device: AdbDevice,
    battle_flow: BattleFlow,
    health: HealthChecker,
    recovery: RecoveryModule,
    vision: VisionModule,
    config: BotConfig,
    accounts: list[str],
    attacks_per_account: int,
) -> None:
    from .account import AccountSwitcher

    notifier = TelegramNotifier()
    switcher = AccountSwitcher(device, config)
    completed_by_account: dict[str, int] = {}

    for account_index, account in enumerate(accounts):
        logger.info("Account cycle: switching to {}", account)
        switcher.switch(account)

        completed = 0
        while completed < attacks_per_account:
            try:
                battle_flow.dismiss_popups()
                health.check_before_cycle()
                battle_flow.run_once()
                completed += 1
                completed_by_account[account] = completed
                logger.info("Account {} completed attacks: {}/{}", account, completed, attacks_per_account)
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

        next_account = accounts[account_index + 1] if account_index + 1 < len(accounts) else ""
        if next_account:
            notifier.send(
                f"Account {account}: {attacks_per_account} attacks completed. "
                f"Switching to next account: {next_account}."
            )
        else:
            notifier.send(f"Account {account}: {attacks_per_account} attacks completed.")

    total_attacks = sum(completed_by_account.values())
    account_lines = "\n".join(f"- {account}: {completed_by_account.get(account, 0)} attacks" for account in accounts)
    notifier.send(f"All attacks completed. Total: {total_attacks}.\nAccounts:\n{account_lines}")
    logger.info("All account-cycle attacks finished; stopping bot")


def run_builder_loop(
    builder_flow: BuilderBattleFlow,
    health: HealthChecker,
    recovery: RecoveryModule,
    vision: VisionModule,
    config: BotConfig,
    max_attacks: int,
) -> None:
    completed_attacks = 0
    while True:
        try:
            health.check_before_cycle()
            builder_flow.run_once()
            completed_attacks += 1
            if max_attacks:
                logger.info("Completed builder attacks: {}/{}", completed_attacks, max_attacks)
                if completed_attacks >= max_attacks:
                    logger.info("Builder attack limit reached; stopping bot")
                    return
            time.sleep(config.cycle_delay_seconds)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            return
        except Exception as exc:
            try:
                saved = vision.save_debug_screenshot("builder-cycle-error")
                if saved is not None:
                    logger.warning("Saved builder cycle error screenshot: {}", saved)
            except Exception as screenshot_exc:
                logger.warning("Unable to save builder cycle error screenshot: {}", screenshot_exc)
            recovery.recover(exc)


if __name__ == "__main__":
    main()
