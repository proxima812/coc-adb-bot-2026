# AI Hook: Runtime ADB

Use before changing launch, ADB, screenshot, recovery, or emulator behavior.

1. LDPlayer is the only supported emulator. Do not reintroduce BlueStacks/MEmu/NoxPlayer paths.
2. Default runtime paths are Windows: `D:\LDPlayer\LDPlayer9\adb.exe`, `D:\LDPlayer\LDPlayer9\dnplayer.exe`. macOS dev machines have no LDPlayer — runtime tests must be done on Windows.
3. Device serial defaults to `127.0.0.1:5555`.
4. ADB calls run through `AdbDevice` and may use a persistent shell. Prefer extending `AdbDevice` over shelling out to `subprocess` from flow code.
5. Retry unstable ADB ops (screenshot, connect) instead of crashing into OpenCV `!buf.empty()` / PIL errors.
6. Do not add desktop mouse/keyboard control as a fallback unless the user explicitly requests it. `ctrl_mouse_wheel_zoom_out` and `press_emulator_key*` are LDPlayer keymap calls, not OS-level input.
7. Use percent coordinates (`tap_percent`, `tap_many_percent`). Never write fixed pixel coords into flow code.
8. Keep LDPlayer open and resolution stable during runtime tests. The builder calibration guard (`builder_calibration_max_screen_drift_percent`) raises hard on resolution drift.
9. For runtime validation on Windows: `.\tools\dev.ps1 doctor`. On macOS: cannot verify; document that fact in the answer.
