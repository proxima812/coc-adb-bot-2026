from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tkinter import BOTH, END, NORMAL, X, StringVar, Tk
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Button, Frame, Label, Radiobutton, Style


class UiTheme:
    background = "#111318"
    panel = "#171a21"
    panel_alt = "#1d212b"
    border = "#2c3340"
    text = "#e8edf2"
    muted = "#9aa4b2"
    accent = "#3f8cff"
    accent_hover = "#5b9dff"
    success = "#4fbf83"
    warning = "#f0b75e"
    error = "#ff6b6b"
    info = "#69a7ff"
    debug = "#9b8cff"
    ui = "#7dd3fc"
    log_bg = "#0d0f14"
    log_fg = "#d7dde5"
    log_muted = "#87909f"


class BotProcessController:
    def __init__(self, process_factory: Callable[[int, bool, str], subprocess.Popen] | None = None) -> None:
        self._process_factory = process_factory or self._default_process_factory
        self._process: subprocess.Popen | None = None

    def start(self, max_attacks: int = 0, account_cycle: bool = False, bot_mode: str = "home") -> bool:
        if self.is_running():
            return False
        self._process = self._process_factory(max_attacks, account_cycle, bot_mode)
        return True

    def stop(self) -> bool:
        if not self.is_running() or self._process is None:
            self._process = None
            return False
        process = self._process
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        self._process = None
        return True

    def restart(self, max_attacks: int = 0, account_cycle: bool = False, bot_mode: str = "home") -> bool:
        self.stop()
        return self.start(max_attacks, account_cycle, bot_mode)

    def switch_account(self, account_name: str) -> subprocess.Popen:
        root = Path(__file__).resolve().parent.parent
        return subprocess.Popen(
            [sys.executable, "-m", "coc_bot.account", account_name],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @staticmethod
    def _default_process_factory(max_attacks: int = 0, account_cycle: bool = False, bot_mode: str = "home") -> subprocess.Popen:
        root = Path(__file__).resolve().parent.parent
        log_dir = root / "logs"
        log_dir.mkdir(exist_ok=True)
        output = (log_dir / "ui-process.log").open("a", encoding="utf-8")
        command = [sys.executable, "-m", "coc_bot.main", "--bot-mode", bot_mode]
        if account_cycle:
            command.append("--account-cycle")
        if max_attacks:
            command.extend(["--max-attacks", str(max_attacks)])
        return subprocess.Popen(
            command,
            cwd=root,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )


class BotControlUi:
    def __init__(self, controller: BotProcessController | None = None, log_path: Path | None = None) -> None:
        self.theme = UiTheme()
        self.root = Tk()
        self.root.title("COC Bot ADB")
        self.root.geometry("1040x680")
        self.root.minsize(820, 500)
        self.root.configure(bg=self.theme.background)
        self._configure_styles()

        self.controller = controller or BotProcessController()
        self.log_path = log_path or Path("logs/bot.log")
        self._last_log_size = 0
        self.bot_mode = StringVar(value="home")

        shell = Frame(self.root, style="App.TFrame", padding=18)
        shell.pack(fill=BOTH, expand=True)

        header = Frame(shell, style="Panel.TFrame", padding=(18, 14))
        header.pack(fill=X, pady=(0, 12))
        header.columnconfigure(0, weight=1)

        title_row = Frame(header, style="Panel.TFrame")
        title_row.grid(row=0, column=0, sticky="ew")
        title_row.columnconfigure(0, weight=1)
        Label(title_row, text="COC Bot ADB", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.status = Label(title_row, text="", style="Status.TLabel")
        self.status.grid(row=0, column=1, sticky="e")

        Label(
            header,
            text="Local bot, account, and live log controls.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        controls = Frame(shell, style="Panel.TFrame", padding=(18, 16))
        controls.pack(fill=X, pady=(0, 12))
        for column in range(5):
            controls.columnconfigure(column, weight=1, uniform="controls")
        Button(controls, text="25x3 accounts", command=self.start_25_attacks, style="Accent.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        Button(controls, text="Start", command=self.start_bot, style="Accent.TButton").grid(
            row=0, column=1, sticky="ew", padx=8
        )
        Button(controls, text="Stop", command=self.stop_bot, style="Danger.TButton").grid(
            row=0, column=2, sticky="ew", padx=8
        )
        Button(controls, text="Restart", command=self.restart_bot, style="Toolbar.TButton").grid(
            row=0, column=3, sticky="ew", padx=8
        )
        Button(controls, text="Clear log", command=self.clear_log_view, style="Toolbar.TButton").grid(
            row=0, column=4, sticky="ew", padx=(8, 0)
        )

        modes = Frame(shell, style="Panel.TFrame", padding=(18, 12))
        modes.pack(fill=X, pady=(0, 12))
        modes.columnconfigure(0, weight=0)
        modes.columnconfigure(1, weight=1)
        modes.columnconfigure(2, weight=1)
        Label(modes, text="Bot mode", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        Radiobutton(modes, text="Home village", variable=self.bot_mode, value="home", style="Mode.TRadiobutton").grid(
            row=0, column=1, sticky="w", padx=(0, 12)
        )
        Radiobutton(modes, text="Builder base", variable=self.bot_mode, value="builder", style="Mode.TRadiobutton").grid(
            row=0, column=2, sticky="w"
        )

        accounts = Frame(shell, style="Panel.TFrame", padding=(18, 16))
        accounts.pack(fill=X, pady=(0, 12))
        accounts.columnconfigure(0, weight=0)
        for column in range(1, 4):
            accounts.columnconfigure(column, weight=1, uniform="accounts")
        Label(accounts, text="Account", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 14))
        Button(accounts, text="proxima", command=lambda: self.switch_account("proxima"), style="Toolbar.TButton").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        Button(
            accounts,
            text="yung_proxima",
            command=lambda: self.switch_account("yung_proxima"),
            style="Toolbar.TButton",
        ).grid(row=0, column=2, sticky="ew", padx=8)
        Button(
            accounts,
            text="old_proxima",
            command=lambda: self.switch_account("old_proxima"),
            style="Toolbar.TButton",
        ).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        log_panel = Frame(shell, style="Panel.TFrame", padding=(12, 12))
        log_panel.pack(fill=BOTH, expand=True)
        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)
        Label(log_panel, text="Log", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=(0, 8))
        self.log_view = ScrolledText(
            log_panel,
            wrap="word",
            state=NORMAL,
            font=("Consolas", 10),
            bg=self.theme.log_bg,
            fg=self.theme.log_fg,
            insertbackground=self.theme.text,
            selectbackground=self.theme.accent,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.log_view.grid(row=1, column=0, sticky="nsew")
        self._configure_log_tags()
        self._insert_log_text("Log output will appear here after the bot starts.\n", "muted")
        self.log_view.configure(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def _configure_styles(self) -> None:
        style = Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=self.theme.background)
        style.configure("Panel.TFrame", background=self.theme.panel, relief="solid", borderwidth=1)
        style.configure("Title.TLabel", background=self.theme.panel, foreground=self.theme.text, font=("Segoe UI", 15, "bold"))
        style.configure("Section.TLabel", background=self.theme.panel, foreground=self.theme.text, font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background=self.theme.panel, foreground=self.theme.muted, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=self.theme.panel, foreground=self.theme.muted, font=("Segoe UI", 10, "bold"))
        style.configure("Mode.TRadiobutton", background=self.theme.panel, foreground=self.theme.text, font=("Segoe UI", 10))
        style.map("Mode.TRadiobutton", background=[("active", self.theme.panel)], foreground=[("disabled", "#6e7683")])
        style.configure(
            "Toolbar.TButton",
            background=self.theme.panel_alt,
            foreground=self.theme.text,
            bordercolor=self.theme.border,
            darkcolor=self.theme.panel_alt,
            lightcolor=self.theme.panel_alt,
            focuscolor=self.theme.panel_alt,
            padding=(14, 9),
            font=("Segoe UI", 10),
        )
        style.map("Toolbar.TButton", background=[("active", "#252b36")], foreground=[("disabled", "#6e7683")])
        style.configure(
            "Accent.TButton",
            background=self.theme.accent,
            foreground="#ffffff",
            bordercolor=self.theme.accent,
            darkcolor=self.theme.accent,
            lightcolor=self.theme.accent,
            focuscolor=self.theme.accent,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", self.theme.accent_hover)])
        style.configure(
            "Danger.TButton",
            background="#2a1d22",
            foreground="#ffd8d8",
            bordercolor="#5a2d35",
            darkcolor="#2a1d22",
            lightcolor="#2a1d22",
            focuscolor="#2a1d22",
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Danger.TButton", background=[("active", "#3a252b")])

    def start_bot(self) -> None:
        started = self.controller.start(bot_mode=self.bot_mode.get())
        self.append_ui_log("Bot started." if started else "Bot is already running.")
        self.update_status()

    def start_25_attacks(self) -> None:
        started = self.controller.start(account_cycle=True, bot_mode="home")
        self.append_ui_log("Bot started for 25 attacks on 3 accounts." if started else "Bot is already running.")
        self.update_status()

    def stop_bot(self) -> None:
        stopped = self.controller.stop()
        self.append_ui_log("Bot stopped." if stopped else "Bot was not running.")
        self.update_status()

    def restart_bot(self) -> None:
        self.controller.restart(bot_mode=self.bot_mode.get())
        self.append_ui_log("Bot restarted.")
        self.update_status()

    def switch_account(self, account_name: str) -> None:
        if self.controller.is_running():
            self.controller.stop()
            self.append_ui_log("Bot stopped before account switch.")
        self.controller.switch_account(account_name)
        self.append_ui_log(f"Account switch requested: {account_name}.")
        self.update_status()

    def clear_log_view(self) -> None:
        self.log_view.configure(state=NORMAL)
        self.log_view.delete("1.0", END)
        self.log_view.configure(state="disabled")
        self._last_log_size = self.log_path.stat().st_size if self.log_path.exists() else 0

    def append_ui_log(self, text: str) -> None:
        self.log_view.configure(state=NORMAL)
        self._insert_log_text(f"[UI] {text}\n", "ui")
        self.log_view.see(END)
        self.log_view.configure(state="disabled")

    def _configure_log_tags(self) -> None:
        self.log_view.tag_configure("error", foreground=self.theme.error)
        self.log_view.tag_configure("success", foreground=self.theme.success)
        self.log_view.tag_configure("warning", foreground=self.theme.warning)
        self.log_view.tag_configure("info", foreground=self.theme.info)
        self.log_view.tag_configure("debug", foreground=self.theme.debug)
        self.log_view.tag_configure("ui", foreground=self.theme.ui)
        self.log_view.tag_configure("muted", foreground=self.theme.log_muted)
        self.log_view.tag_configure("default", foreground=self.theme.log_fg)

    def _insert_log_text(self, text: str, tag: str | None = None) -> None:
        for line in text.splitlines(keepends=True):
            self.log_view.insert(END, line, tag or self._log_tag_for_line(line))

    def _log_tag_for_line(self, line: str) -> str:
        normalized = line.lower()
        if "[ui]" in normalized:
            return "ui"
        if any(marker in normalized for marker in ("error", "exception", "traceback", "failed", "runtimeerror")):
            return "error"
        if any(marker in normalized for marker in ("warning", "warn")):
            return "warning"
        if any(marker in normalized for marker in ("success", "ok", "done", "completed", "detected", "connected", "started", "ready")):
            return "success"
        if any(marker in normalized for marker in ("debug", "trace")):
            return "debug"
        if any(marker in normalized for marker in ("info", "waiting", "starting", "running", "search", "attack", "battle")):
            return "info"
        return "default"

    def update_status(self) -> None:
        is_running = self.controller.is_running()
        status = "Running" if is_running else "Stopped"
        color = self.theme.success if is_running else self.theme.muted
        self.status.configure(text=status, foreground=color)

    def refresh(self) -> None:
        self.update_status()
        self.read_new_log()
        self.root.after(1000, self.refresh)

    def read_new_log(self) -> None:
        if not self.log_path.exists():
            return
        size = self.log_path.stat().st_size
        if size < self._last_log_size:
            self._last_log_size = 0
        if size == self._last_log_size:
            return
        with self.log_path.open("r", encoding="utf-8", errors="replace") as log_file:
            log_file.seek(self._last_log_size)
            chunk = log_file.read()
            self._last_log_size = log_file.tell()
        if not chunk:
            return
        self.log_view.configure(state=NORMAL)
        self._insert_log_text(chunk)
        self.log_view.see(END)
        self.log_view.configure(state="disabled")

    def close(self) -> None:
        self.controller.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    BotControlUi().run()


if __name__ == "__main__":
    main()
