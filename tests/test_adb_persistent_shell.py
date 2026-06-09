from __future__ import annotations

import unittest
from unittest.mock import patch

from coc_bot.adb_device import AdbDevice, _PersistentAdbShell


class FakeShell:
    """Stand-in for _PersistentAdbShell — записывает все exec-вызовы."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self.disabled = False
        self.calls: list[str] = []
        self.started = False
        self.closed = False
        self._should_fail = should_fail

    def start(self) -> None:
        self.started = True

    def exec(self, command: str, timeout: float = 5.0) -> str:
        self.calls.append(command)
        if self._should_fail:
            from coc_bot.adb_device import AdbError

            raise AdbError("forced failure")
        return ""

    def close(self, reason: str = "shutdown") -> None:
        self.closed = True


class AdbPersistentShellRoutingTest(unittest.TestCase):
    def _device(self) -> AdbDevice:
        device = AdbDevice(adb_path="/nonexistent/adb", serial="127.0.0.1:5555", persistent_shell=True)
        # bypass _ensure_shell's path existence/start logic
        device._shell = FakeShell()
        device._ensure_shell = lambda: device._shell  # type: ignore[assignment]
        return device

    def test_tap_uses_persistent_shell(self) -> None:
        device = self._device()
        with patch.object(device, "run") as fallback:
            device.tap(100, 200)
        shell = device._shell
        assert isinstance(shell, FakeShell)
        self.assertEqual(shell.calls, ["input tap 100 200"])
        fallback.assert_not_called()

    def test_swipe_uses_persistent_shell(self) -> None:
        device = self._device()
        with patch.object(device, "run") as fallback:
            device.swipe(10, 20, 30, 40, duration_ms=250)
        shell = device._shell
        assert isinstance(shell, FakeShell)
        self.assertEqual(shell.calls, ["input swipe 10 20 30 40 250"])
        fallback.assert_not_called()

    def test_keyevent_uses_persistent_shell(self) -> None:
        device = self._device()
        with patch.object(device, "run") as fallback:
            device.keyevent(4)
        shell = device._shell
        assert isinstance(shell, FakeShell)
        self.assertEqual(shell.calls, ["input keyevent 4"])
        fallback.assert_not_called()

    def test_falls_back_to_subprocess_when_shell_returns_none(self) -> None:
        device = AdbDevice(adb_path="/nonexistent/adb", serial="x", persistent_shell=True)
        device._ensure_shell = lambda: None  # type: ignore[assignment]
        with patch.object(device, "run") as fallback:
            device.tap(1, 2)
        fallback.assert_called_once()

    def test_dry_run_skips_shell(self) -> None:
        device = AdbDevice(adb_path="/nonexistent/adb", serial="x", dry_run=True, persistent_shell=True)
        with patch.object(device, "run") as fallback:
            device.tap(1, 2)
        fallback.assert_not_called()
        self.assertIsNone(device._shell)

    def test_persistent_shell_disabled_when_flag_false(self) -> None:
        device = AdbDevice(adb_path="/nonexistent/adb", serial="x", persistent_shell=False)
        self.assertIsNone(device._ensure_shell())


class PersistentShellExecParsingTest(unittest.TestCase):
    def test_marker_constant_prefix(self) -> None:
        self.assertTrue(_PersistentAdbShell.SENTINEL_PREFIX.startswith("__"))


if __name__ == "__main__":
    unittest.main()
