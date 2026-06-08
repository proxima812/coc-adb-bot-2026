from __future__ import annotations

import ctypes
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger


class AdbError(RuntimeError):
    pass


class AdbDevice:
    def __init__(self, adb_path: str, serial: str, dry_run: bool = False) -> None:
        self.adb_path = adb_path
        self.serial = serial
        self.dry_run = dry_run
        self._screen_size: tuple[int, int] | None = None

    def _action_log(self, message: str, *args: object) -> None:
        logger.bind(action=True).info(message, *args)

    def _base_cmd(self) -> list[str]:
        path = Path(self.adb_path)
        if not path.exists():
            raise AdbError(f"ADB not found: {self.adb_path}")
        return [str(path), "-s", self.serial]

    def host_run(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
        adb = Path(self.adb_path)
        if not adb.exists():
            raise AdbError(f"ADB not found: {self.adb_path}")
        cmd = [str(adb), *args]
        logger.debug("ADB host: {}", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise AdbError(result.stderr.strip() or result.stdout.strip() or "ADB host command failed")
        return result

    def run(self, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
        cmd = [*self._base_cmd(), *args]
        logger.debug("ADB: {}", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise AdbError(result.stderr.strip() or result.stdout.strip() or "ADB command failed")
        return result

    def run_bytes(self, *args: str, timeout: int = 20) -> bytes:
        cmd = [*self._base_cmd(), *args]
        logger.debug("ADB: {}", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            raise AdbError(stderr or stdout or "ADB command failed")
        return result.stdout

    def connect(self) -> None:
        self._action_log("ADB connect requested: serial={}", self.serial)
        adb = Path(self.adb_path)
        if not adb.exists():
            raise AdbError(f"ADB not found: {self.adb_path}")
        result = subprocess.run(
            [str(adb), "connect", self.serial],
            capture_output=True,
            text=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0 or "unable" in output.lower() or "failed" in output.lower():
            raise AdbError(output or "Unable to connect ADB device")
        self._screen_size = None
        logger.info("ADB connected: {}", output)
        self._action_log("ADB connected: {}", output)

    def kill_server(self) -> None:
        adb = Path(self.adb_path)
        if not adb.exists():
            return
        self._action_log("ADB kill-server requested")
        subprocess.run([str(adb), "kill-server"], capture_output=True, timeout=10)
        self._screen_size = None

    def check(self) -> None:
        self._action_log("ADB device check requested: serial={}", self.serial)
        self.run("shell", "getprop", "ro.product.model", timeout=10)
        logger.info("ADB device check passed: {}", self.serial)

    def start_app(self, package_name: str) -> None:
        self._action_log("Start app requested: package={}", package_name)
        self.run("shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1")

    def force_stop_app(self, package_name: str) -> None:
        self._action_log("Force-stop app requested: package={}", package_name)
        self.run("shell", "am", "force-stop", package_name)

    def tap(self, x: int, y: int) -> None:
        self._action_log("ADB tap: x={} y={} dry_run={}", x, y, self.dry_run)
        if self.dry_run:
            logger.info("DRY-RUN tap {},{}", x, y)
            return
        self.run("shell", "input", "tap", str(x), str(y), timeout=10)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self._action_log(
            "ADB swipe: x1={} y1={} x2={} y2={} duration_ms={} dry_run={}",
            x1,
            y1,
            x2,
            y2,
            duration_ms,
            self.dry_run,
        )
        if self.dry_run:
            logger.info("DRY-RUN swipe {},{} -> {},{} {}ms", x1, y1, x2, y2, duration_ms)
            return
        self.run(
            "shell",
            "input",
            "swipe",
            str(x1),
            str(y1),
            str(x2),
            str(y2),
            str(duration_ms),
            timeout=10,
        )

    def swipe_percent(
        self,
        x1_percent: float,
        y1_percent: float,
        x2_percent: float,
        y2_percent: float,
        duration_ms: int,
    ) -> None:
        width, height = self.screen_size()
        x1 = round(width * x1_percent / 100)
        y1 = round(height * y1_percent / 100)
        x2 = round(width * x2_percent / 100)
        y2 = round(height * y2_percent / 100)
        logger.debug(
            "Swipe {}%,{}% -> {}%,{}% as {},{} -> {},{} {}ms",
            x1_percent,
            y1_percent,
            x2_percent,
            y2_percent,
            x1,
            y1,
            x2,
            y2,
            duration_ms,
        )
        self._action_log(
            "ADB swipe percent: {}%,{}% -> {}%,{}% pixels={},{}->{},{} duration_ms={}",
            x1_percent,
            y1_percent,
            x2_percent,
            y2_percent,
            x1,
            y1,
            x2,
            y2,
            duration_ms,
        )
        self.swipe(x1, y1, x2, y2, duration_ms)

    def pinch_zoom_out_percent(self, seconds: float = 0.35) -> None:
        width, height = self.screen_size()
        duration_ms = round(seconds * 1000)
        gestures = [
            (
                round(width * 28 / 100),
                round(height * 50 / 100),
                round(width * 48 / 100),
                round(height * 50 / 100),
            ),
            (
                round(width * 72 / 100),
                round(height * 50 / 100),
                round(width * 52 / 100),
                round(height * 50 / 100),
            ),
        ]
        if self.dry_run:
            logger.info("DRY-RUN pinch zoom out {} for {}ms", gestures, duration_ms)
            return
        logger.debug("Pinch zoom out: {} for {}ms", gestures, duration_ms)
        self._action_log("ADB pinch zoom out: gestures={} duration_ms={}", gestures, duration_ms)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self.swipe, x1, y1, x2, y2, duration_ms)
                for x1, y1, x2, y2 in gestures
            ]
            for future in as_completed(futures):
                future.result()

    def ctrl_mouse_wheel_zoom_out(self, wheel_ticks: int = 1) -> None:
        if self.dry_run:
            logger.info("DRY-RUN Ctrl+mouse wheel down zoom out ticks={}", wheel_ticks)
            return
        if wheel_ticks <= 0:
            return

        self._activate_emulator_window()

        logger.debug("Ctrl+mouse wheel down zoom out ticks={}", wheel_ticks)
        self._action_log("LDPlayer Ctrl+mouse wheel zoom out: ticks={}", wheel_ticks)
        user32 = ctypes.windll.user32
        vk_control = 0x11
        keyeventf_keyup = 0x0002
        mouseeventf_wheel = 0x0800
        wheel_delta_down = -120
        user32.keybd_event(vk_control, 0, 0, 0)
        try:
            for _ in range(wheel_ticks):
                user32.mouse_event(mouseeventf_wheel, 0, 0, wheel_delta_down, 0)
                time.sleep(0.05)
        finally:
            user32.keybd_event(vk_control, 0, keyeventf_keyup, 0)

    def press_emulator_key(self, key: str, presses: int = 1, delay_seconds: float = 0.05) -> None:
        if self.dry_run:
            logger.info("DRY-RUN emulator key {} presses={}", key, presses)
            return
        if presses <= 0:
            return

        self._activate_emulator_window()
        vk_code = self._virtual_key_code(key)
        logger.debug("Pressing emulator key {} presses={}", key, presses)
        self._action_log("LDPlayer key press: key={} presses={} delay_seconds={}", key, presses, delay_seconds)
        user32 = ctypes.windll.user32
        keyeventf_keyup = 0x0002
        for _ in range(presses):
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(vk_code, 0, keyeventf_keyup, 0)
            time.sleep(delay_seconds)

    @staticmethod
    def _find_emulator_window() -> int:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        process_query_limited_information = 0x1000
        buffer_size = 260
        found: list[int] = []

        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process = kernel32.OpenProcess(process_query_limited_information, False, pid.value)
            if not process:
                return True
            try:
                path_buffer = ctypes.create_unicode_buffer(buffer_size)
                size = ctypes.c_ulong(buffer_size)
                if not kernel32.QueryFullProcessImageNameW(process, 0, path_buffer, ctypes.byref(size)):
                    return True
                if Path(path_buffer.value).name.lower() == "dnplayer.exe":
                    found.append(hwnd)
                    return False
            finally:
                kernel32.CloseHandle(process)
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        return found[0] if found else 0

    @staticmethod
    def _virtual_key_code(key: str) -> int:
        normalized = key.strip().upper()
        if len(normalized) == 1 and "A" <= normalized <= "Z":
            return ord(normalized)
        if len(normalized) == 1 and "0" <= normalized <= "9":
            return ord(normalized)
        raise ValueError(f"Unsupported keyboard key: {key}")

    @staticmethod
    def _activate_emulator_window() -> None:
        hwnd = AdbDevice._find_emulator_window()
        if hwnd:
            logger.debug("Activating emulator window handle {}", hwnd)
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.15)
        else:
            logger.warning("LDPlayer window not found; sending keyboard input to current foreground window")

    def tap_percent(self, x_percent: float, y_percent: float) -> None:
        width, height = self.screen_size()
        x = round(width * x_percent / 100)
        y = round(height * y_percent / 100)
        logger.debug("Tap {}%,{}% -> {},{}", x_percent, y_percent, x, y)
        self._action_log("ADB tap percent: {}%,{}% -> x={} y={} screen={}x{}", x_percent, y_percent, x, y, width, height)
        self.tap(x, y)

    def tap_many_percent(self, points: list[tuple[float, float]]) -> None:
        if not points:
            return
        width, height = self.screen_size()
        pixel_points = [
            (round(width * x_percent / 100), round(height * y_percent / 100))
            for x_percent, y_percent in points
        ]
        if self.dry_run:
            logger.info("DRY-RUN parallel taps {}", pixel_points)
            return
        logger.debug("Parallel taps: {}", pixel_points)
        self._action_log("ADB parallel taps: count={} pixels={} screen={}x{}", len(pixel_points), pixel_points, width, height)
        with ThreadPoolExecutor(max_workers=len(pixel_points)) as executor:
            futures = [executor.submit(self.tap, x, y) for x, y in pixel_points]
            for future in as_completed(futures):
                future.result()

    def hold_many_percent(self, points: list[tuple[float, float]], seconds: float) -> None:
        if not points:
            return
        width, height = self.screen_size()
        duration_ms = round(seconds * 1000)
        pixel_points = [
            (round(width * x_percent / 100), round(height * y_percent / 100))
            for x_percent, y_percent in points
        ]
        if self.dry_run:
            logger.info("DRY-RUN parallel holds {} for {}ms", pixel_points, duration_ms)
            return
        logger.debug("Parallel holds: {} for {}ms", pixel_points, duration_ms)
        self._action_log(
            "ADB parallel holds: count={} pixels={} duration_ms={} screen={}x{}",
            len(pixel_points),
            pixel_points,
            duration_ms,
            width,
            height,
        )
        with ThreadPoolExecutor(max_workers=len(pixel_points)) as executor:
            futures = [executor.submit(self.swipe, x, y, x, y, duration_ms) for x, y in pixel_points]
            for future in as_completed(futures):
                future.result()

    def hold_percent(self, x_percent: float, y_percent: float, seconds: float) -> None:
        width, height = self.screen_size()
        x = round(width * x_percent / 100)
        y = round(height * y_percent / 100)
        duration_ms = round(seconds * 1000)
        logger.debug("Hold {}%,{}% -> {},{} for {}ms", x_percent, y_percent, x, y, duration_ms)
        self._action_log(
            "ADB hold percent: {}%,{}% -> x={} y={} duration_ms={} screen={}x{}",
            x_percent,
            y_percent,
            x,
            y,
            duration_ms,
            width,
            height,
        )
        self.swipe(x, y, x, y, duration_ms)

    def text(self, value: str) -> None:
        self._action_log("ADB text input requested: length={} dry_run={}", len(value), self.dry_run)
        if self.dry_run:
            logger.info("DRY-RUN text {}", value)
            return
        escaped = value.replace(" ", "%s")
        self.run("shell", "input", "text", escaped, timeout=10)

    def keyevent(self, keycode: int) -> None:
        self._action_log("ADB keyevent: keycode={} dry_run={}", keycode, self.dry_run)
        if self.dry_run:
            logger.info("DRY-RUN keyevent {}", keycode)
            return
        self.run("shell", "input", "keyevent", str(keycode), timeout=10)

    def screenshot(self) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                self._action_log("ADB screenshot attempt {}/3", attempt)
                raw = self.run_bytes("exec-out", "screencap", "-p", timeout=20)
                if raw:
                    self._action_log("ADB screenshot captured: attempt={} bytes={}", attempt, len(raw))
                    return raw
                last_error = AdbError("ADB returned an empty screenshot")
            except Exception as exc:
                last_error = exc
            logger.warning("Screenshot attempt {}/3 failed: {}", attempt, last_error)
            time.sleep(0.5)
        raise AdbError(f"Unable to capture screenshot after retries: {last_error}")

    def screen_size(self) -> tuple[int, int]:
        if self._screen_size is not None:
            return self._screen_size
        result = self.run("shell", "wm", "size", timeout=10)
        output = result.stdout.strip()
        marker = "Physical size:"
        if marker in output:
            output = output.split(marker, 1)[1].strip()
        width_text, height_text = output.split("x", 1)
        self._screen_size = (int(width_text), int(height_text))
        logger.info("Detected screen size: {}x{}", self._screen_size[0], self._screen_size[1])
        return self._screen_size
