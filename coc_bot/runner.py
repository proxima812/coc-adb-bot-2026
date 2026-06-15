from __future__ import annotations

import time

from loguru import logger

from .adb_device import AdbDevice
from .battle_flow import BattleFlow
from .builder_flow import BuilderBattleFlow
from .config import BotConfig
from .health import HealthChecker
from .recovery import RecoveryModule
from .telegram_notify import TelegramNotifier
from .vision import VisionModule

ATTACK_MILESTONE_COUNT = 60


def run_home_loop(
    battle_flow: BattleFlow,
    health: HealthChecker,
    recovery: RecoveryModule,
    vision: VisionModule,
    config: BotConfig,
    max_attacks: int,
) -> None:
    completed_attacks = 0
    milestone_sent = False
    notifier = TelegramNotifier()
    while True:
        try:
            battle_flow.dismiss_popups()
            health.check_before_cycle()
            _send_pre_attack_screenshot(notifier, battle_flow.device, completed_attacks + 1)
            battle_flow.run_once()
            completed_attacks += 1
            milestone_sent = _send_attack_milestone_once(notifier, completed_attacks, milestone_sent)
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
    milestone_sent = False

    for account_index, account in enumerate(accounts):
        logger.info("Account cycle: switching to {}", account)
        switcher.switch(account)

        completed = 0
        while completed < attacks_per_account:
            try:
                battle_flow.dismiss_popups()
                health.check_before_cycle()
                total_before_attack = sum(completed_by_account.values())
                _send_pre_attack_screenshot(notifier, device, total_before_attack + 1)
                battle_flow.run_once()
                completed += 1
                completed_by_account[account] = completed
                total_completed = sum(completed_by_account.values())
                milestone_sent = _send_attack_milestone_once(notifier, total_completed, milestone_sent)
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
    milestone_sent = False
    notifier = TelegramNotifier()
    while True:
        try:
            health.check_before_cycle()
            _send_pre_attack_screenshot(notifier, builder_flow.device, completed_attacks + 1)
            builder_flow.run_once()
            completed_attacks += 1
            milestone_sent = _send_attack_milestone_once(notifier, completed_attacks, milestone_sent)
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


def _send_pre_attack_screenshot(notifier: TelegramNotifier, device: AdbDevice, attack_number: int) -> None:
    if not notifier.token:
        return
    try:
        photo = device.screenshot()
    except Exception as exc:
        logger.warning("Pre-attack screenshot capture failed: {}", exc)
        return
    notifier.send_photo(photo, caption=f"Before attack {attack_number}")


def _send_attack_milestone_once(notifier: TelegramNotifier, completed_attacks: int, already_sent: bool) -> bool:
    if already_sent or completed_attacks < ATTACK_MILESTONE_COUNT:
        return already_sent
    notifier.send(f"{ATTACK_MILESTONE_COUNT} attacks completed.")
    return True
