from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tkinter import BOTH, END, LEFT, NORMAL, RIGHT, X, Y, StringVar, Tk
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Button, Frame, Label, Radiobutton, Style


class UiTheme:
    background = "#0b0d12"
    panel = "#151821"
    panel_alt = "#1c2030"
    panel_hi = "#222738"
    border = "#262c3d"
    border_soft = "#1f2433"
    text = "#eef2f8"
    text_strong = "#ffffff"
    muted = "#8b95a8"
    subtle = "#5f6877"
    accent = "#6366f1"
    accent_hover = "#7c7ff5"
    accent_soft = "#2a2750"
    success = "#22c55e"
    success_soft = "#13321e"
    warning = "#f59e0b"
    error = "#ef4444"
    error_soft = "#3a1c20"
    info = "#60a5fa"
    debug = "#a78bfa"
    ui = "#22d3ee"
    log_bg = "#080a0f"
    log_fg = "#d7dde8"
    log_muted = "#6b7383"


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
    SIDEBAR_WIDTH = 320

    def __init__(self, controller: BotProcessController | None = None, log_path: Path | None = None) -> None:
        self.theme = UiTheme()
        self.root = Tk()
        self.root.title("COC Bot ADB")
        self.root.geometry("1120x720")
        self.root.minsize(900, 560)
        self.root.configure(bg=self.theme.background)
        self._configure_styles()

        self.controller = controller or BotProcessController()
        self.log_path = log_path or Path("logs/bot.log")
        self._last_log_size = 0
        self.bot_mode = StringVar(value="home")

        shell = Frame(self.root, style="App.TFrame", padding=(20, 20))
        shell.pack(fill=BOTH, expand=True)

        sidebar = Frame(shell, style="Sidebar.TFrame", padding=(20, 22), width=self.SIDEBAR_WIDTH)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 16))
        sidebar.pack_propagate(False)

        self._build_brand(sidebar)
        self._build_status_pill(sidebar)
        self._build_controls_card(sidebar)
        self._build_mode_card(sidebar)
        self._build_accounts_card(sidebar)

        log_panel = Frame(shell, style="Panel.TFrame", padding=(18, 16))
        log_panel.pack(side=RIGHT, fill=BOTH, expand=True)
        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)

        log_header = Frame(log_panel, style="Panel.TFrame")
        log_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        log_header.columnconfigure(0, weight=1)
        Label(log_header, text="Activity log", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        Label(log_header, text="Live tail of logs/bot.log", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
        Button(log_header, text="Clear", command=self.clear_log_view, style="Ghost.TButton").grid(row=0, column=1, rowspan=2, sticky="e")

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
            padx=14,
            pady=14,
        )
        self.log_view.grid(row=1, column=0, sticky="nsew")
        self._configure_log_tags()
        self._insert_log_text("Log output will appear here after the bot starts.\n", "muted")
        self.log_view.configure(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def _build_brand(self, parent: Frame) -> None:
        brand = Frame(parent, style="Sidebar.TFrame")
        brand.pack(fill=X, pady=(0, 18))
        accent_bar = Frame(brand, style="AccentBar.TFrame", width=4, height=42)
        accent_bar.pack(side=LEFT, padx=(0, 12))
        accent_bar.pack_propagate(False)
        text_block = Frame(brand, style="Sidebar.TFrame")
        text_block.pack(side=LEFT, fill=X, expand=True)
        Label(text_block, text="COC Bot", style="Brand.TLabel").pack(anchor="w")
        Label(text_block, text="ADB Control Center", style="BrandSub.TLabel").pack(anchor="w", pady=(2, 0))

    def _build_status_pill(self, parent: Frame) -> None:
        wrapper = Frame(parent, style="Sidebar.TFrame")
        wrapper.pack(fill=X, pady=(0, 18))
        self._status_pill = Frame(wrapper, style="PillStopped.TFrame", padding=(14, 9))
        self._status_pill.pack(fill=X)
        self._status_dot = Label(self._status_pill, text="●", style="PillDotStopped.TLabel")
        self._status_dot.pack(side=LEFT)
        self.status = Label(self._status_pill, text="Stopped", style="PillTextStopped.TLabel")
        self.status.pack(side=LEFT, padx=(8, 0))

    def _build_controls_card(self, parent: Frame) -> None:
        card = self._card(parent, title="Controls", subtitle="Run, pause, or recycle the bot")
        Button(card, text="25 × 3 accounts", command=self.start_25_attacks, style="Accent.TButton").pack(fill=X, pady=(0, 8))
        Button(card, text="Start", command=self.start_bot, style="Accent.TButton").pack(fill=X, pady=(0, 8))
        row = Frame(card, style="Card.TFrame")
        row.pack(fill=X)
        row.columnconfigure(0, weight=1, uniform="ctl")
        row.columnconfigure(1, weight=1, uniform="ctl")
        Button(row, text="Stop", command=self.stop_bot, style="Danger.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 4))
        Button(row, text="Restart", command=self.restart_bot, style="Toolbar.TButton").grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_mode_card(self, parent: Frame) -> None:
        card = self._card(parent, title="Bot mode", subtitle="Pick a village")
        Radiobutton(card, text="Home village", variable=self.bot_mode, value="home", style="Mode.TRadiobutton").pack(anchor="w", pady=(0, 4))
        Radiobutton(card, text="Builder base", variable=self.bot_mode, value="builder", style="Mode.TRadiobutton").pack(anchor="w")

    def _build_accounts_card(self, parent: Frame) -> None:
        card = self._card(parent, title="Account", subtitle="Switch active profile", pady_outer=(0, 0))
        for name in ("proxima", "yung_proxima", "old_proxima"):
            Button(card, text=name, command=lambda n=name: self.switch_account(n), style="Toolbar.TButton").pack(fill=X, pady=(0, 6))

    def _card(self, parent: Frame, title: str, subtitle: str | None = None, pady_outer: tuple[int, int] = (0, 14)) -> Frame:
        outer = Frame(parent, style="Card.TFrame", padding=(14, 14))
        outer.pack(fill=X, pady=pady_outer)
        Label(outer, text=title, style="CardTitle.TLabel").pack(anchor="w")
        if subtitle:
            Label(outer, text=subtitle, style="CardSub.TLabel").pack(anchor="w", pady=(2, 10))
        else:
            Frame(outer, style="Card.TFrame", height=8).pack(fill=X)
        return outer

    def _configure_styles(self) -> None:
        style = Style(self.root)
        style.theme_use("clam")

        style.configure("App.TFrame", background=self.theme.background)
        style.configure("Sidebar.TFrame", background=self.theme.panel, relief="solid", borderwidth=1, bordercolor=self.theme.border)
        style.configure("Panel.TFrame", background=self.theme.panel, relief="solid", borderwidth=1, bordercolor=self.theme.border)
        style.configure("Card.TFrame", background=self.theme.panel_alt, relief="solid", borderwidth=1, bordercolor=self.theme.border_soft)
        style.configure("AccentBar.TFrame", background=self.theme.accent)

        style.configure("Brand.TLabel", background=self.theme.panel, foreground=self.theme.text_strong, font=("Segoe UI", 16, "bold"))
        style.configure("BrandSub.TLabel", background=self.theme.panel, foreground=self.theme.muted, font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=self.theme.panel_alt, foreground=self.theme.text, font=("Segoe UI", 10, "bold"))
        style.configure("CardSub.TLabel", background=self.theme.panel_alt, foreground=self.theme.muted, font=("Segoe UI", 9))
        style.configure("Muted.TLabel", background=self.theme.panel, foreground=self.theme.muted, font=("Segoe UI", 9))

        style.configure("PillStopped.TFrame", background=self.theme.panel_hi, relief="solid", borderwidth=1, bordercolor=self.theme.border)
        style.configure("PillRunning.TFrame", background=self.theme.success_soft, relief="solid", borderwidth=1, bordercolor="#1f5a36")
        style.configure("PillDotStopped.TLabel", background=self.theme.panel_hi, foreground=self.theme.muted, font=("Segoe UI", 11))
        style.configure("PillTextStopped.TLabel", background=self.theme.panel_hi, foreground=self.theme.text, font=("Segoe UI", 10, "bold"))
        style.configure("PillDotRunning.TLabel", background=self.theme.success_soft, foreground=self.theme.success, font=("Segoe UI", 11))
        style.configure("PillTextRunning.TLabel", background=self.theme.success_soft, foreground="#a7f3c5", font=("Segoe UI", 10, "bold"))

        style.configure(
            "Mode.TRadiobutton",
            background=self.theme.panel_alt,
            foreground=self.theme.text,
            font=("Segoe UI", 10),
            indicatorcolor=self.theme.panel_hi,
            indicatorbackground=self.theme.panel_hi,
        )
        style.map(
            "Mode.TRadiobutton",
            background=[("active", self.theme.panel_alt)],
            foreground=[("disabled", self.theme.subtle)],
            indicatorcolor=[("selected", self.theme.accent), ("!selected", self.theme.panel_hi)],
        )

        for name, bg, fg, hover in (
            ("Toolbar.TButton", self.theme.panel_hi, self.theme.text, "#2a3045"),
            ("Ghost.TButton", self.theme.panel, self.theme.muted, self.theme.panel_hi),
        ):
            style.configure(
                name,
                background=bg,
                foreground=fg,
                bordercolor=self.theme.border,
                darkcolor=bg,
                lightcolor=bg,
                focuscolor=bg,
                padding=(14, 9),
                font=("Segoe UI", 10),
                relief="flat",
            )
            style.map(name, background=[("active", hover)], foreground=[("disabled", self.theme.subtle)])

        style.configure(
            "Accent.TButton",
            background=self.theme.accent,
            foreground="#ffffff",
            bordercolor=self.theme.accent,
            darkcolor=self.theme.accent,
            lightcolor=self.theme.accent,
            focuscolor=self.theme.accent,
            padding=(14, 11),
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Accent.TButton", background=[("active", self.theme.accent_hover)])

        style.configure(
            "Danger.TButton",
            background=self.theme.error_soft,
            foreground="#ffd5d5",
            bordercolor="#5a2d35",
            darkcolor=self.theme.error_soft,
            lightcolor=self.theme.error_soft,
            focuscolor=self.theme.error_soft,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Danger.TButton", background=[("active", "#4a242c")])

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
        if is_running:
            self._status_pill.configure(style="PillRunning.TFrame")
            self._status_dot.configure(style="PillDotRunning.TLabel")
            self.status.configure(style="PillTextRunning.TLabel", text="Running")
        else:
            self._status_pill.configure(style="PillStopped.TFrame")
            self._status_dot.configure(style="PillDotStopped.TLabel")
            self.status.configure(style="PillTextStopped.TLabel", text="Stopped")

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
