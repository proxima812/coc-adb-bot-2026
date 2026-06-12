from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — только для type hints
    import customtkinter as ctk
else:  # рантайм-импорт делается лениво в BotControlUi.__init__, чтобы
    # модуль (и BotProcessController) импортировались без GUI-зависимости.
    ctk = None  # type: ignore[assignment]


def _require_ctk() -> Any:
    """Ленивый импорт CustomTkinter с понятным сообщением об ошибке."""
    global ctk
    if ctk is None:
        try:
            import customtkinter as _ctk
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "CustomTkinter не установлен. Запусти `pip install customtkinter` или "
                "переустанови зависимости: `pip install -r requirements.txt`."
            ) from exc
        ctk = _ctk
    return ctk


class UiTheme:
    """Палитра приложения.

    Оставлена как простой namespace: пользовательский CustomTkinter-стиль
    использует те же ключевые цвета, плюс легко подменяется в тестах/snippets.
    """

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
    accent_pressed = "#4f52d6"
    success = "#22c55e"
    success_soft = "#13321e"
    success_text = "#a7f3c5"
    warning = "#f59e0b"
    error = "#ef4444"
    error_soft = "#3a1c20"
    error_text = "#ffd5d5"
    info = "#60a5fa"
    debug = "#a78bfa"
    ui = "#22d3ee"
    log_bg = "#080a0f"
    log_fg = "#d7dde8"
    log_muted = "#6b7383"


class BotProcessController:
    """Управление дочерним процессом бота. API стабилен — покрыт тестами."""

    def __init__(self, process_factory: Callable[[int, bool, str, int], subprocess.Popen] | None = None) -> None:
        self._process_factory = process_factory or self._default_process_factory
        self._process: subprocess.Popen | None = None
        self._last_exit_code: int | None = None

    def start(
        self,
        max_attacks: int = 0,
        account_cycle: bool = False,
        bot_mode: str = "home",
        home_troop_slots: int = 1,
    ) -> bool:
        if self.is_running():
            return False
        self._process = self._process_factory(max_attacks, account_cycle, bot_mode, home_troop_slots)
        self._last_exit_code = None
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
        self._last_exit_code = process.returncode
        self._process = None
        return True

    def restart(
        self,
        max_attacks: int = 0,
        account_cycle: bool = False,
        bot_mode: str = "home",
        home_troop_slots: int = 1,
    ) -> bool:
        self.stop()
        return self.start(max_attacks, account_cycle, bot_mode, home_troop_slots)

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

    def has_crashed(self) -> bool:
        """True, если процесс был запущен, но завершился сам (не через stop())."""
        if self._process is None:
            return False
        code = self._process.poll()
        if code is None:
            return False
        # Процесс завершён без вызова stop(), оставшийся handle указывает на крэш.
        self._last_exit_code = code
        return True

    def collect_crashed(self) -> int | None:
        """Сброс хэндла процесса после регистрации крэша."""
        if self._process is None or self._process.poll() is None:
            return None
        code = self._process.returncode
        self._last_exit_code = code
        self._process = None
        return code

    def pid(self) -> int | None:
        if self._process is None:
            return None
        return self._process.pid

    @property
    def last_exit_code(self) -> int | None:
        return self._last_exit_code

    @staticmethod
    def _default_process_factory(
        max_attacks: int = 0,
        account_cycle: bool = False,
        bot_mode: str = "home",
        home_troop_slots: int = 1,
    ) -> subprocess.Popen:
        root = Path(__file__).resolve().parent.parent
        command = [sys.executable, "-m", "coc_bot.main", "--bot-mode", bot_mode]
        if bot_mode == "home":
            command.extend(["--home-troop-slots", str(home_troop_slots)])
        if account_cycle:
            command.append("--account-cycle")
        if max_attacks:
            command.extend(["--max-attacks", str(max_attacks)])
        # Stdout/stderr дублируют loguru → logs/bot.log; локальный лог-файл больше не нужен.
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=creationflags,
        )


class _LogTailer:
    """Фоновый поток, читающий файл-хвост и складывающий чанки в очередь.

    UI забирает чанки с помощью `drain()` без блокировок основного цикла.
    """

    def __init__(self, log_path: Path, poll_interval: float = 0.5) -> None:
        self.log_path = log_path
        self.poll_interval = poll_interval
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_size = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._last_size = self.log_path.stat().st_size if self.log_path.exists() else 0
        self._thread = threading.Thread(target=self._run, name="ui-log-tail", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def reset(self) -> None:
        self._last_size = self.log_path.stat().st_size if self.log_path.exists() else 0

    def drain(self) -> list[str]:
        chunks: list[str] = []
        while True:
            try:
                chunks.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return chunks

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.log_path.exists():
                    size = self.log_path.stat().st_size
                    if size < self._last_size:
                        # Ротация / пересоздание файла.
                        self._last_size = 0
                    if size > self._last_size:
                        with self.log_path.open("r", encoding="utf-8", errors="replace") as handle:
                            handle.seek(self._last_size)
                            chunk = handle.read()
                            self._last_size = handle.tell()
                        if chunk:
                            self._queue.put(chunk)
            except OSError:
                # Файл занят/удалён — попробуем на следующей итерации.
                pass
            self._stop_event.wait(self.poll_interval)


class BotControlUi:
    """Главное окно панели управления ботом, построенное на CustomTkinter."""

    SIDEBAR_WIDTH = 320
    LOG_POLL_MS = 250
    STATUS_POLL_MS = 1000

    def __init__(
        self,
        controller: BotProcessController | None = None,
        log_path: Path | None = None,
        accounts: tuple[str, ...] = ("proxima", "yung_proxima", "old_proxima"),
    ) -> None:
        self.theme = UiTheme()
        self.accounts = accounts

        _require_ctk()
        ctk.set_appearance_mode("dark")
        # Палитра приложения — используем «dark-blue» как базу, накладываем поверх свои цвета.
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("COC Bot ADB")
        self.root.geometry("1180x740")
        self.root.minsize(960, 600)
        self.root.configure(fg_color=self.theme.background)

        self.controller = controller or BotProcessController()
        self.log_path = log_path or Path("logs/bot.log")
        self._tailer = _LogTailer(self.log_path)
        self._stop_in_progress = False
        self._was_running = False

        self.bot_mode = ctk.StringVar(value="home")
        self.home_troop_slots = ctk.IntVar(value=1)

        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._insert_log_text("Log output will appear here after the bot starts.\n", "muted")
        self._tailer.start()
        self.refresh_status()
        self._poll_log()

    # ---------- layout ----------

    def _build_layout(self) -> None:
        shell = ctk.CTkFrame(self.root, fg_color=self.theme.background, corner_radius=0)
        shell.pack(fill="both", expand=True, padx=20, pady=20)

        sidebar = ctk.CTkFrame(
            shell,
            width=self.SIDEBAR_WIDTH,
            fg_color=self.theme.panel,
            border_color=self.theme.border,
            border_width=1,
            corner_radius=14,
        )
        sidebar.pack(side="left", fill="y", padx=(0, 16))
        sidebar.pack_propagate(False)
        sidebar_inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_inner.pack(fill="both", expand=True, padx=18, pady=20)

        self._build_brand(sidebar_inner)
        self._build_status_pill(sidebar_inner)
        self._build_controls_card(sidebar_inner)
        self._build_mode_card(sidebar_inner)
        self._build_strategy_card(sidebar_inner)
        self._build_accounts_card(sidebar_inner)
        self._build_footer(sidebar_inner)

        log_panel = ctk.CTkFrame(
            shell,
            fg_color=self.theme.panel,
            border_color=self.theme.border,
            border_width=1,
            corner_radius=14,
        )
        log_panel.pack(side="right", fill="both", expand=True)
        log_inner = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_inner.pack(fill="both", expand=True, padx=18, pady=16)

        log_header = ctk.CTkFrame(log_inner, fg_color="transparent")
        log_header.pack(fill="x", pady=(0, 12))
        log_header.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header,
            text="Activity log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.text,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            log_header,
            text=f"Live tail of {self.log_path.as_posix()}",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.muted,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkButton(
            log_header,
            text="Clear",
            width=88,
            height=30,
            corner_radius=10,
            fg_color=self.theme.panel_hi,
            hover_color="#2a3045",
            text_color=self.theme.muted,
            command=self.clear_log_view,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        self.log_view = ctk.CTkTextbox(
            log_inner,
            wrap="word",
            fg_color=self.theme.log_bg,
            text_color=self.theme.log_fg,
            border_color=self.theme.border_soft,
            border_width=1,
            corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.log_view.pack(fill="both", expand=True)
        self._configure_log_tags()
        self.log_view.configure(state="disabled")

    def _build_brand(self, parent: ctk.CTkFrame) -> None:
        brand = ctk.CTkFrame(parent, fg_color="transparent")
        brand.pack(fill="x", pady=(0, 18))

        accent_bar = ctk.CTkFrame(brand, width=4, height=42, fg_color=self.theme.accent, corner_radius=2)
        accent_bar.pack(side="left", padx=(0, 12))
        accent_bar.pack_propagate(False)

        text_block = ctk.CTkFrame(brand, fg_color="transparent")
        text_block.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            text_block,
            text="COC Bot",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme.text_strong,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_block,
            text="ADB Control Center",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.muted,
        ).pack(anchor="w", pady=(2, 0))

    def _build_status_pill(self, parent: ctk.CTkFrame) -> None:
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", pady=(0, 18))

        self._status_pill = ctk.CTkFrame(
            wrapper,
            fg_color=self.theme.panel_hi,
            corner_radius=999,
            border_color=self.theme.border,
            border_width=1,
        )
        self._status_pill.pack(fill="x")
        pill_inner = ctk.CTkFrame(self._status_pill, fg_color="transparent")
        pill_inner.pack(padx=14, pady=8)

        self._status_dot = ctk.CTkLabel(
            pill_inner,
            text="●",
            text_color=self.theme.muted,
            font=ctk.CTkFont(size=14),
        )
        self._status_dot.pack(side="left")

        self._status_label = ctk.CTkLabel(
            pill_inner,
            text="Stopped",
            text_color=self.theme.text,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._status_label.pack(side="left", padx=(8, 0))

        self._pid_label = ctk.CTkLabel(
            pill_inner,
            text="",
            text_color=self.theme.muted,
            font=ctk.CTkFont(size=11),
        )
        self._pid_label.pack(side="left", padx=(10, 0))

    def _build_controls_card(self, parent: ctk.CTkFrame) -> None:
        card = self._card(parent, title="Controls", subtitle="Run, pause, or recycle the bot")

        self._cycle_button = self._accent_button(card, text="25 × 3 accounts", command=self.start_25_attacks)
        self._cycle_button.pack(fill="x", pady=(0, 8))

        self._start_button = self._accent_button(card, text="Start", command=self.start_bot)
        self._start_button.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1, uniform="ctl")
        row.columnconfigure(1, weight=1, uniform="ctl")

        self._stop_button = ctk.CTkButton(
            row,
            text="Stop",
            command=self.stop_bot,
            height=36,
            corner_radius=10,
            fg_color=self.theme.error_soft,
            hover_color="#4a242c",
            text_color=self.theme.error_text,
            border_color="#5a2d35",
            border_width=1,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._stop_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._restart_button = ctk.CTkButton(
            row,
            text="Restart",
            command=self.restart_bot,
            height=36,
            corner_radius=10,
            fg_color=self.theme.panel_hi,
            hover_color="#2a3045",
            text_color=self.theme.text,
            font=ctk.CTkFont(size=12),
        )
        self._restart_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_mode_card(self, parent: ctk.CTkFrame) -> None:
        card = self._card(parent, title="Bot mode", subtitle="Pick a village")

        # CTkSegmentedButton — современный аналог пары RadioButton.
        self._mode_switch = ctk.CTkSegmentedButton(
            card,
            values=["Home village", "Builder base"],
            command=self._on_mode_changed,
            fg_color=self.theme.panel_hi,
            selected_color=self.theme.accent,
            selected_hover_color=self.theme.accent_hover,
            unselected_color=self.theme.panel_hi,
            unselected_hover_color="#2a3045",
            text_color=self.theme.text,
            corner_radius=10,
            height=34,
        )
        self._mode_switch.set("Home village")
        self._mode_switch.pack(fill="x")

    def _build_strategy_card(self, parent: ctk.CTkFrame) -> None:
        card = self._card(parent, title="Strategy", subtitle="Home troop slot layout")

        self._strategy_switch = ctk.CTkSegmentedButton(
            card,
            values=["1 slot", "2 slots", "3 slots"],
            command=self._on_strategy_changed,
            fg_color=self.theme.panel_hi,
            selected_color=self.theme.accent,
            selected_hover_color=self.theme.accent_hover,
            unselected_color=self.theme.panel_hi,
            unselected_hover_color="#2a3045",
            text_color=self.theme.text,
            corner_radius=10,
            height=34,
        )
        self._strategy_switch.set("1 slot")
        self._strategy_switch.pack(fill="x")

    def _build_accounts_card(self, parent: ctk.CTkFrame) -> None:
        card = self._card(parent, title="Account", subtitle="Switch active profile")
        for name in self.accounts:
            button = ctk.CTkButton(
                card,
                text=name,
                command=lambda n=name: self.switch_account(n),
                height=34,
                corner_radius=10,
                fg_color=self.theme.panel_hi,
                hover_color="#2a3045",
                text_color=self.theme.text,
                font=ctk.CTkFont(size=12),
            )
            button.pack(fill="x", pady=(0, 6))

    def _build_footer(self, parent: ctk.CTkFrame) -> None:
        spacer = ctk.CTkFrame(parent, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkLabel(
            parent,
            text=f"log: {self.log_path.as_posix()}",
            text_color=self.theme.subtle,
            font=ctk.CTkFont(size=10),
        ).pack(anchor="w")

    def _card(
        self,
        parent: ctk.CTkFrame,
        title: str,
        subtitle: str | None = None,
    ) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(
            parent,
            fg_color=self.theme.panel_alt,
            border_color=self.theme.border_soft,
            border_width=1,
            corner_radius=12,
        )
        outer.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=14)

        ctk.CTkLabel(
            inner,
            text=title,
            text_color=self.theme.text,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(
                inner,
                text=subtitle,
                text_color=self.theme.muted,
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", pady=(2, 10))
        return inner

    def _accent_button(self, parent: ctk.CTkFrame, text: str, command: Callable[[], None]) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=40,
            corner_radius=10,
            fg_color=self.theme.accent,
            hover_color=self.theme.accent_hover,
            text_color="#ffffff",
            font=ctk.CTkFont(size=13, weight="bold"),
        )

    # ---------- actions ----------

    def _on_mode_changed(self, value: str) -> None:
        self.bot_mode.set("home" if value == "Home village" else "builder")

    def _on_strategy_changed(self, value: str) -> None:
        self.home_troop_slots.set(int(value.split()[0]))

    def start_bot(self) -> None:
        started = self.controller.start(bot_mode=self.bot_mode.get(), home_troop_slots=self.home_troop_slots.get())
        self.append_ui_log("Bot started." if started else "Bot is already running.")
        self.refresh_status()

    def start_25_attacks(self) -> None:
        started = self.controller.start(
            account_cycle=True,
            bot_mode="home",
            home_troop_slots=self.home_troop_slots.get(),
        )
        self.append_ui_log(
            "Bot started for 25 attacks on 3 accounts." if started else "Bot is already running."
        )
        self.refresh_status()

    def stop_bot(self) -> None:
        if not self.controller.is_running():
            self.append_ui_log("Bot was not running.")
            self.refresh_status()
            return
        if self._stop_in_progress:
            self.append_ui_log("Stop already in progress…")
            return
        self._stop_in_progress = True
        self._stop_button.configure(state="disabled", text="Stopping…")
        self.append_ui_log("Stopping bot…")

        def runner() -> None:
            stopped = False
            try:
                stopped = self.controller.stop()
            finally:
                self.root.after(0, lambda: self._on_stop_finished(stopped))

        threading.Thread(target=runner, name="ui-stop", daemon=True).start()

    def _on_stop_finished(self, stopped: bool) -> None:
        self._stop_in_progress = False
        self._stop_button.configure(state="normal", text="Stop")
        self.append_ui_log("Bot stopped." if stopped else "Bot was not running.")
        self.refresh_status()

    def restart_bot(self) -> None:
        # Сначала останавливаем синхронно через стандартный stop, затем стартуем.
        if self.controller.is_running():
            self._stop_button.configure(state="disabled")

            def runner() -> None:
                self.controller.stop()
                self.root.after(0, self._after_restart_stop)

            threading.Thread(target=runner, name="ui-restart", daemon=True).start()
        else:
            self._after_restart_stop()

    def _after_restart_stop(self) -> None:
        self._stop_button.configure(state="normal", text="Stop")
        self.controller.start(bot_mode=self.bot_mode.get(), home_troop_slots=self.home_troop_slots.get())
        self.append_ui_log("Bot restarted.")
        self.refresh_status()

    def switch_account(self, account_name: str) -> None:
        if self.controller.is_running():
            self.controller.stop()
            self.append_ui_log("Bot stopped before account switch.")
        self.controller.switch_account(account_name)
        self.append_ui_log(f"Account switch requested: {account_name}.")
        self.refresh_status()

    def clear_log_view(self) -> None:
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.configure(state="disabled")
        self._tailer.reset()

    def append_ui_log(self, text: str) -> None:
        self.log_view.configure(state="normal")
        self._insert_log_text(f"[UI] {text}\n", "ui")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")

    # ---------- log rendering ----------

    def _underlying_text_widget(self):
        # CTkTextbox держит внутри tk.Text — без него нельзя ставить tag_configure.
        return self.log_view._textbox  # noqa: SLF001 — стабильный публично используемый атрибут

    def _configure_log_tags(self) -> None:
        text = self._underlying_text_widget()
        text.tag_configure("error", foreground=self.theme.error)
        text.tag_configure("success", foreground=self.theme.success)
        text.tag_configure("warning", foreground=self.theme.warning)
        text.tag_configure("info", foreground=self.theme.info)
        text.tag_configure("debug", foreground=self.theme.debug)
        text.tag_configure("ui", foreground=self.theme.ui)
        text.tag_configure("muted", foreground=self.theme.log_muted)
        text.tag_configure("default", foreground=self.theme.log_fg)

    def _insert_log_text(self, text: str, tag: str | None = None) -> None:
        for line in text.splitlines(keepends=True):
            self.log_view.insert("end", line, tag or self._log_tag_for_line(line))

    @staticmethod
    def _log_tag_for_line(line: str) -> str:
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

    # ---------- status / polling ----------

    def refresh_status(self) -> None:
        # Детекция самопроизвольного крэша процесса.
        if self._was_running and self.controller.has_crashed():
            code = self.controller.collect_crashed()
            self.append_ui_log(f"Bot process exited unexpectedly (code={code}).")
            self._set_status("crashed")
            self._pid_label.configure(text="")
            self._was_running = False
            return

        is_running = self.controller.is_running()
        if is_running:
            self._set_status("running")
            pid = self.controller.pid()
            self._pid_label.configure(text=f"pid {pid}" if pid else "")
        else:
            # «Просто остановлен», без крэша.
            if self._was_running:
                self._pid_label.configure(text="")
            if not self._stop_in_progress:
                self._set_status("stopped")
        self._was_running = is_running

    def _set_status(self, state: str) -> None:
        if state == "running":
            self._status_pill.configure(fg_color=self.theme.success_soft, border_color="#1f5a36")
            self._status_dot.configure(text_color=self.theme.success)
            self._status_label.configure(text="Running", text_color=self.theme.success_text)
        elif state == "crashed":
            self._status_pill.configure(fg_color=self.theme.error_soft, border_color="#5a2d35")
            self._status_dot.configure(text_color=self.theme.error)
            self._status_label.configure(text="Crashed", text_color=self.theme.error_text)
        else:
            self._status_pill.configure(fg_color=self.theme.panel_hi, border_color=self.theme.border)
            self._status_dot.configure(text_color=self.theme.muted)
            self._status_label.configure(text="Stopped", text_color=self.theme.text)

    def _poll_log(self) -> None:
        chunks = self._tailer.drain()
        if chunks:
            self.log_view.configure(state="normal")
            for chunk in chunks:
                self._insert_log_text(chunk)
            self.log_view.see("end")
            self.log_view.configure(state="disabled")
        # Регулярно обновляем статус (раз в STATUS_POLL_MS), а лог — чаще.
        now = time.monotonic()
        last = getattr(self, "_last_status_at", 0.0)
        if (now - last) * 1000 >= self.STATUS_POLL_MS:
            self.refresh_status()
            self._last_status_at = now
        self.root.after(self.LOG_POLL_MS, self._poll_log)

    # ---------- lifecycle ----------

    def close(self) -> None:
        try:
            self.controller.stop()
        finally:
            self._tailer.stop()
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    BotControlUi().run()


if __name__ == "__main__":
    main()
