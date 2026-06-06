from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tkinter import BOTH, END, LEFT, NORMAL, RIGHT, X, Button, Frame, Label, Tk
from tkinter.scrolledtext import ScrolledText


class BotProcessController:
    def __init__(self, process_factory: Callable[[], subprocess.Popen] | None = None) -> None:
        self._process_factory = process_factory or self._default_process_factory
        self._process: subprocess.Popen | None = None

    def start(self) -> bool:
        if self.is_running():
            return False
        self._process = self._process_factory()
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

    def restart(self) -> bool:
        self.stop()
        return self.start()

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
    def _default_process_factory() -> subprocess.Popen:
        root = Path(__file__).resolve().parent.parent
        log_dir = root / "logs"
        log_dir.mkdir(exist_ok=True)
        output = (log_dir / "ui-process.log").open("a", encoding="utf-8")
        return subprocess.Popen(
            [sys.executable, "-m", "coc_bot.main"],
            cwd=root,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )


class BotControlUi:
    def __init__(self, controller: BotProcessController | None = None, log_path: Path | None = None) -> None:
        self.root = Tk()
        self.root.title("COC Bot ADB")
        self.root.geometry("980x620")
        self.root.minsize(760, 420)
        self.controller = controller or BotProcessController()
        self.log_path = log_path or Path("logs/bot.log")
        self._last_log_size = 0

        self.status = Label(self.root, text="Статус: остановлен", anchor="w")
        self.status.pack(fill=X, padx=10, pady=(10, 4))

        buttons = Frame(self.root)
        buttons.pack(fill=X, padx=10, pady=6)
        Button(buttons, text="Старт", width=16, command=self.start_bot).pack(side=LEFT, padx=(0, 8))
        Button(buttons, text="Стоп", width=16, command=self.stop_bot).pack(side=LEFT, padx=(0, 8))
        Button(buttons, text="Перезагрузить", width=18, command=self.restart_bot).pack(side=LEFT)
        Button(buttons, text="Очистить лог", width=16, command=self.clear_log_view).pack(side=RIGHT)

        accounts = Frame(self.root)
        accounts.pack(fill=X, padx=10, pady=(0, 6))
        Label(accounts, text="Аккаунт:", anchor="w").pack(side=LEFT, padx=(0, 8))
        Button(accounts, text="proxima", width=16, command=lambda: self.switch_account("proxima")).pack(side=LEFT, padx=(0, 8))
        Button(accounts, text="yung_proxima", width=16, command=lambda: self.switch_account("yung_proxima")).pack(side=LEFT, padx=(0, 8))
        Button(accounts, text="old_proxima", width=16, command=lambda: self.switch_account("old_proxima")).pack(side=LEFT)

        self.log_view = ScrolledText(self.root, wrap="word", state=NORMAL, font=("Consolas", 10))
        self.log_view.pack(fill=BOTH, expand=True, padx=10, pady=(4, 10))
        self.log_view.insert(END, "Лог появится здесь после запуска бота.\n")
        self.log_view.configure(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def start_bot(self) -> None:
        started = self.controller.start()
        self.append_ui_log("Бот запущен." if started else "Бот уже запущен.")
        self.update_status()

    def stop_bot(self) -> None:
        stopped = self.controller.stop()
        self.append_ui_log("Бот остановлен." if stopped else "Бот не был запущен.")
        self.update_status()

    def restart_bot(self) -> None:
        self.controller.restart()
        self.append_ui_log("Бот перезагружен.")
        self.update_status()

    def switch_account(self, account_name: str) -> None:
        if self.controller.is_running():
            self.controller.stop()
            self.append_ui_log("Бот остановлен перед сменой аккаунта.")
        self.controller.switch_account(account_name)
        self.append_ui_log(f"Запрошена смена аккаунта: {account_name}.")
        self.update_status()

    def clear_log_view(self) -> None:
        self.log_view.configure(state=NORMAL)
        self.log_view.delete("1.0", END)
        self.log_view.configure(state="disabled")
        self._last_log_size = self.log_path.stat().st_size if self.log_path.exists() else 0

    def append_ui_log(self, text: str) -> None:
        self.log_view.configure(state=NORMAL)
        self.log_view.insert(END, f"[UI] {text}\n")
        self.log_view.see(END)
        self.log_view.configure(state="disabled")

    def update_status(self) -> None:
        status = "работает" if self.controller.is_running() else "остановлен"
        self.status.configure(text=f"Статус: {status}")

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
        self.log_view.insert(END, chunk)
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
