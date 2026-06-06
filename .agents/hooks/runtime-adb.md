# AI Hook: Runtime ADB

Use before changing launch, ADB, screenshot, recovery, or emulator behavior.

1. Keep LDPlayer as the only emulator runtime.
2. Default local paths are `D:\LDPlayer\LDPlayer9\adb.exe` and `D:\LDPlayer\LDPlayer9\dnplayer.exe`; verify local files before changing them.
3. Device serial defaults to `127.0.0.1:5555`.
4. Prefer retrying unstable ADB operations over crashing into OpenCV/PIL errors.
5. Do not add desktop mouse/keyboard control as a fallback unless the user explicitly asks.
6. Use percent coordinates, not fixed pixels, for gameplay taps.
7. Keep LDPlayer open and resolution stable during tests.
8. Run `.\tools\dev.ps1 doctor` only when runtime/device validation is needed.
