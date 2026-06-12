# AI Hook: Log Diagnosis

Use when the user asks to inspect logs, errors, crashes, or runtime behavior.

1. Read newest entries in `logs/bot.log` first. `logs/actions.log` contains the higher-level cycle steps; cross-check it for the cycle context of a failure.
2. Lead with the newest blocking error. Separate it from older resolved warnings.
3. Common signatures and where to look:
   - `cv2.error ... !buf.empty()`: empty ADB screenshot. Inspect `AdbDevice.screenshot` retries, LDPlayer responsiveness, and `RecoveryModule.recover`.
   - `Connection refused` / `127.0.0.1:5555`: LDPlayer ADB not up yet. Inspect `EmulatorLauncher.start_and_connect` wait windows and `RecoveryModule` reconnect delay.
   - `Battle screen was not detected`: home `_wait_until_battle` timed out. Inspect templates under `assets/templates/state`, thresholds (`battle_template_threshold`, `attack_template_threshold`), and `wait_battle_seconds`.
   - `Builder battle screen was not detected`: builder `_wait_until_builder_battle` timed out. Inspect `builder_battle_template_paths` / thresholds.
   - `UnsafeBuilderTapError`: a builder tap fell outside `builder_safe_tap_area` or inside a forbidden area. Print the point and the offending area.
   - `Builder screen calibration failed`: resolution drifted past `builder_calibration_max_screen_drift_percent`. LDPlayer resolution changed.
4. On Windows: `.\tools\dev.ps1 logs -Tail 160` shows tail + grepped warnings/errors. On macOS: `tail -n 160 logs/bot.log` then grep for `ERROR|WARNING|Traceback|RuntimeError|failed|Unable|not detected|cv2.error|ADB`.
5. Calibration overlays under `logs/calibration/` (and `logs/calibration/builder/`) help debug tap placement. Don't suggest deleting them unless the user asks.
6. Debug screenshots under `logs/screenshots/` are written on cycle errors (`cycle-error` for home, `builder-cycle-error` for builder).
