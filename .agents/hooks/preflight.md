# AI Hook: Preflight

Use before editing bot code.

1. Identify the target surface: home village flow, builder flow, vision/state, ADB/recovery/launcher, UI, calibration, or config.
2. Read the relevant files before editing:
   - Home village: `coc_bot/battle_flow.py`, `coc_bot/config.py`, `main-village.md`.
   - Builder village: `coc_bot/builder_flow.py`, `coc_bot/config.py`, `builder-village.md`.
   - Vision/state/OCR: `coc_bot/vision.py`, `coc_bot/config.py`.
   - ADB/recovery/launcher: `coc_bot/adb_device.py`, `coc_bot/emulator.py`, `coc_bot/recovery.py`, `coc_bot/main.py`.
   - UI/log control: `coc_bot/ui.py`, `tools/dev.ps1`, `start-ui.bat`, `start.bat`.
   - Calibration overlay: `coc_bot/calibration.py`, overlay flags in `BotConfig` (`calibration_overlay_*`, `builder_tap_overlay_*`).
3. `config.json` is the operator's gitignored config. If it's missing, `BotConfig` defaults run. Do not assume `config.example.json` exists.
4. Preserve ADB-first control and LDPlayer-only runtime. No BlueStacks. No desktop mouse/keyboard fallback.
5. If touching deploy: confirm whether `deploy_mode` is `hotkeys` (default operator flow) or `coordinates` before changing logic. They are different code paths.
6. If touching camera prep: confirm `battle_camera_direct_ctrl_scroll_enabled`; the pinch path is dead when direct scroll is on.
7. Run `.\tools\dev.ps1 check` from Windows after non-trivial edits.
