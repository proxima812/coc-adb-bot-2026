from __future__ import annotations

import argparse
from collections.abc import Sequence

DEFAULT_ACCOUNT_SEQUENCE = ("proxima", "yung_proxima", "old_proxima")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument(
        "--home-troop-slots",
        type=int,
        choices=(1, 2, 3),
        default=1,
        help="Home hotkey strategy: number of troop slots before siege/heroes/spells.",
    )
    return parser.parse_args(argv)
