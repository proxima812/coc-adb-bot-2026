from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import customtkinter as ctk
else:
    ctk = None  # type: ignore[assignment]


def _require_ctk() -> Any:
    global ctk
    if ctk is None:
        try:
            import customtkinter as _ctk
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "CustomTkinter не установлен. Запусти `pip install customtkinter`."
            ) from exc
        ctk = _ctk
    return ctk


class UiTheme:
    background = "#0f1210"
    panel = "#161c18"
    panel_alt = "#1c2420"
    panel_hi = "#222e26"
    border = "#2a3a2e"
    border_soft = "#223028"
    text = "#e8f0ea"
    text_strong = "#ffffff"
    muted = "#7a9082"
    subtle = "#4e6056"
    accent = "#2E5E3A"
    accent_hover = "#3a7848"
    accent_pressed = "#1e4027"
    success = "#4ade80"
    success_soft = "#122a1c"
    success_text = "#a7f3c5"
    warning = "#f59e0b"
    error = "#ef4444"
    error_soft = "#3a1c20"
    error_text = "#ffd5d5"
    info = "#6ee7b7"
    debug = "#a78bfa"
    ui = "#34d399"
    log_bg = "#0a0f0b"
    log_fg = "#c8d8cc"
    log_muted = "#4e6056"


class BotProcessController:
    """Управление дочерним процессом бота. API стабилен — покрыт тестами."""

    def __init__(self, process_factory: Callable[[int, bool, str], subprocess.Popen] | None = None) -> None:
        self._process_factory = process_factory or self._default_process_factory
        self._process: subprocess.Popen | None = None
        self._last_exit_code: int | None = None

    def start(self, max_attacks: int = 0, account_cycle: bool = False, bot_mode: str = "home") -> bool:
        if self.is_running():
            return False
        self._process = self._process_factory(max_attacks, account_cycle, bot_mode)
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

    def has_crashed(self) -> bool:
        if self._process is None:
            return False
        code = self._process.poll()
        if code is None:
            return False
        self._last_exit_code = code
        return True

    def collect_crashed(self) -> int | None:
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
    def _default_process_factory(max_attacks: int = 0, account_cycle: bool = False, bot_mode: str = "home") -> subprocess.Popen:
        root = Path(__file__).resolve().parent.parent
        command = [sys.executable, "-m", "coc_bot.main", "--bot-mode", bot_mode]
        if account_cycle:
            command.append("--account-cycle")
        if max_attacks:
            command.extend(["--max-attacks", str(max_attacks)])
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
                        self._last_size = 0
                    if size > self._last_size:
                        with self.log_path.open("r", encoding="utf-8", errors="replace") as handle:
                            handle.seek(self._last_size)
                            chunk = handle.read()
                            self._last_size = handle.tell()
                        if chunk:
                            self._queue.put(chunk)
            except OSError:
                pass
            self._stop_event.wait(self.poll_interval)


class BotControlUi:
    SIDEBAR_WIDTH = 300
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
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("COC Bot")
        self.root.geometry("1100x680")
        self.root.minsize(900, 560)
        self.root.configure(fg_color=self.theme.background)

        self.controller = controller or BotProcessController()
        self.log_path = log_path or Path("logs/bot.log")
        self._tailer = _LogTailer(self.log_path)
        self._stop_in_progress = False
        self._was_running = False

        self.bot_mode = ctk.StringVar(value="home")
        self.slot_var = ctk.StringVar(value="1")

        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._tailer.start()
        self.refresh_status()
        self._poll_log()

    # ---------- layout ----------

    def _build_layout(self) -> None:
        shell = ctk.CTkFrame(self.root, fg_color=self.theme.background, corner_radius=0)
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        # Left sidebar
        sidebar = ctk.CTkFrame(
            shell,
            width=self.SIDEBAR_WIDTH,
            fg_color=self.theme.panel,
            border_color=self.theme.border,
            border_width=1,
            corner_radius=12,
        )
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_status(inner)
        self._build_controls(inner)
        self._build_settings(inner)

        # Right log panel
        log_panel = ctk.CTkFrame(
            shell,
            fg_color=self.theme.panel,
            border_color=self.theme.border,
            border_width=1,
            corner_radius=12,
        )
        log_panel.pack(side="right", fill="both", expand=True)

        log_inner = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_inner.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            log_inner,
            text="логирования",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.muted,
        ).pack(anchor="w", pady=(0, 8))

        self.log_view = ctk.CTkTextbox(
            log_inner,
            wrap="word",
            fg_color=self.theme.log_bg,
            text_color=self.theme.log_fg,
            border_color=self.theme.border_soft,
            border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.log_view.pack(fill="both", expand=True)
        self._configure_log_tags()
        self.log_view.configure(state="disabled")

    def _build_status(self, parent: ctk.CTkFrame) -> None:
        self._status_label = ctk.CTkLabel(
            parent,
            text="stopped",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.muted,
            anchor="center",
        )
        self._status_label.pack(fill="x", pady=(0, 14))

        self._pid_label = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=self.theme.subtle,
        )
        self._pid_label.pack(fill="x", pady=(0, 4))

    def _build_controls(self, parent: ctk.CTkFrame) -> None:
        # Row 1: 25×3 label + start button
        row1 = ctk.CTkFrame(parent, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row1,
            text="25×3",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.muted,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(2, 0))

        ctk.CTkButton(
            row1,
            text="start",
            command=self.start_25_attacks,
            height=32,
            corner_radius=8,
            fg_color=self.theme.accent,
            hover_color=self.theme.accent_hover,
            text_color="#ffffff",
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=1, sticky="ew")

        # Row 2: stop + restart
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 14))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        self._stop_button = ctk.CTkButton(
            row2,
            text="stop",
            command=self.stop_bot,
            height=32,
            corner_radius=8,
            fg_color=self.theme.error_soft,
            hover_color="#4a242c",
            text_color=self.theme.error_text,
            border_color="#5a2d35",
            border_width=1,
            font=ctk.CTkFont(size=12),
        )
        self._stop_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._restart_button = ctk.CTkButton(
            row2,
            text="restart",
            command=self.restart_bot,
            height=32,
            corner_radius=8,
            fg_color=self.theme.panel_hi,
            hover_color="#2a3a2e",
            text_color=self.theme.text,
            font=ctk.CTkFont(size=12),
        )
        self._restart_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_settings(self, parent: ctk.CTkFrame) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.panel_alt,
            border_color=self.theme.border_soft,
            border_width=1,
            corner_radius=10,
        )
        card.pack(fill="x", pady=(0, 12))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(
            inner,
            text="settings",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.muted,
        ).pack(anchor="w", pady=(0, 10))

        # Mode: main / builder
        self._mode_switch = ctk.CTkSegmentedButton(
            inner,
            values=["main", "builder"],
            command=self._on_mode_changed,
            fg_color=self.theme.panel_hi,
            selected_color=self.theme.accent,
            selected_hover_color=self.theme.accent_hover,
            unselected_color=self.theme.panel_hi,
            unselected_hover_color="#2a3a2e",
            text_color=self.theme.text,
            corner_radius=8,
            height=30,
        )
        self._mode_switch.set("main")
        self._mode_switch.pack(fill="x", pady=(0, 8))

        # Slot: 1 / 2 / 3
        self._slot_switch = ctk.CTkSegmentedButton(
            inner,
            values=["1 slot", "2", "3"],
            command=lambda v: self.slot_var.set(v.replace(" slot", "")),
            fg_color=self.theme.panel_hi,
            selected_color=self.theme.panel_hi,
            selected_hover_color="#2a3a2e",
            unselected_color=self.theme.panel_hi,
            unselected_hover_color="#2a3a2e",
            text_color=self.theme.muted,
            corner_radius=8,
            height=28,
        )
        self._slot_switch.set("1 slot")
        self._slot_switch.pack(fill="x", pady=(0, 12))

        # Accounts
        ctk.CTkLabel(
            inner,
            text="аккаунты",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.muted,
        ).pack(anchor="w", pady=(0, 6))

        acc_frame = ctk.CTkFrame(
            inner,
            fg_color=self.theme.panel_hi,
            corner_radius=8,
        )
        acc_frame.pack(fill="x")
        acc_inner = ctk.CTkFrame(acc_frame, fg_color="transparent")
        acc_inner.pack(fill="x", padx=8, pady=8)

        for name in self.accounts:
            ctk.CTkButton(
                acc_inner,
                text=name,
                command=lambda n=name: self.switch_account(n),
                height=30,
                corner_radius=6,
                fg_color=self.theme.panel_alt,
                hover_color=self.theme.border,
                text_color=self.theme.text,
                font=ctk.CTkFont(size=11),
            ).pack(fill="x", pady=(0, 4))

    # ---------- actions ----------

    def _on_mode_changed(self, value: str) -> None:
        self.bot_mode.set("home" if value == "main" else "builder")

    def start_bot(self) -> None:
        started = self.controller.start(bot_mode=self.bot_mode.get())
        self.append_ui_log("Bot started." if started else "Already running.")
        self.refresh_status()

    def start_25_attacks(self) -> None:
        started = self.controller.start(account_cycle=True, bot_mode="home")
        self.append_ui_log("Started: 25 attacks × 3 accounts." if started else "Already running.")
        self.refresh_status()

    def stop_bot(self) -> None:
        if not self.controller.is_running():
            self.append_ui_log("Not running.")
            self.refresh_status()
            return
        if self._stop_in_progress:
            return
        self._stop_in_progress = True
        self._stop_button.configure(state="disabled", text="…")
        self.append_ui_log("Stopping…")

        def runner() -> None:
            stopped = False
            try:
                stopped = self.controller.stop()
            finally:
                self.root.after(0, lambda: self._on_stop_finished(stopped))

        threading.Thread(target=runner, name="ui-stop", daemon=True).start()

    def _on_stop_finished(self, stopped: bool) -> None:
        self._stop_in_progress = False
        self._stop_button.configure(state="normal", text="stop")
        self.append_ui_log("Stopped." if stopped else "Not running.")
        self.refresh_status()

    def restart_bot(self) -> None:
        if self.controller.is_running():
            self._stop_button.configure(state="disabled")

            def runner() -> None:
                self.controller.stop()
                self.root.after(0, self._after_restart_stop)

            threading.Thread(target=runner, name="ui-restart", daemon=True).start()
        else:
            self._after_restart_stop()

    def _after_restart_stop(self) -> None:
        self._stop_button.configure(state="normal", text="stop")
        self.controller.start(bot_mode=self.bot_mode.get())
        self.append_ui_log("Restarted.")
        self.refresh_status()

    def switch_account(self, account_name: str) -> None:
        if self.controller.is_running():
            self.controller.stop()
            self.append_ui_log("Stopped before account switch.")
        self.controller.switch_account(account_name)
        self.append_ui_log(f"Account: {account_name}.")
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
        return self.log_view._textbox  # noqa: SLF001

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
        n = line.lower()
        if "[ui]" in n:
            return "ui"
        if any(m in n for m in ("error", "exception", "traceback", "failed", "runtimeerror")):
            return "error"
        if any(m in n for m in ("warning", "warn")):
            return "warning"
        if any(m in n for m in ("success", "ok", "done", "completed", "detected", "connected", "started", "ready")):
            return "success"
        if any(m in n for m in ("debug", "trace")):
            return "debug"
        if any(m in n for m in ("info", "waiting", "starting", "running", "search", "attack", "battle")):
            return "info"
        return "default"

    # ---------- status / polling ----------

    def refresh_status(self) -> None:
        if self._was_running and self.controller.has_crashed():
            code = self.controller.collect_crashed()
            self.append_ui_log(f"Crashed (code={code}).")
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
            if self._was_running:
                self._pid_label.configure(text="")
            if not self._stop_in_progress:
                self._set_status("stopped")
        self._was_running = is_running

    def _set_status(self, state: str) -> None:
        if state == "running":
            self._status_label.configure(text="running", text_color=self.theme.success)
        elif state == "crashed":
            self._status_label.configure(text="crashed", text_color=self.theme.error)
        else:
            self._status_label.configure(text="stopped", text_color=self.theme.muted)

    def _poll_log(self) -> None:
        chunks = self._tailer.drain()
        if chunks:
            self.log_view.configure(state="normal")
            for chunk in chunks:
                self._insert_log_text(chunk)
            self.log_view.see("end")
            self.log_view.configure(state="disabled")
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
