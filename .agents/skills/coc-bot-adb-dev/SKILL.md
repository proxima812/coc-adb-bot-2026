---
name: coc-bot-adb-dev
description: Develop, debug, validate, and tune the local COC-bot-adb Clash of Clans bot. Use when working in C:\Users\proxima\Desktop\COC-bot-adb on ADB control, LDPlayer startup, battle flow, OCR state detection, deploy timing, G fallback points, calibration overlay, UI/log control, recovery, config.example.json, or launcher/runtime changes.
---

# COC Bot ADB Dev

## Workflow

1. Inspect the current files before advising. Start with `coc_bot/config.py`, `coc_bot/emulator.py`, `coc_bot/battle_flow.py`, `coc_bot/vision.py`, `coc_bot/adb_device.py`, `coc_bot/recovery.py`, and `config.example.json`.
2. Treat `config.example.json` as the active config when `config.json` is absent.
3. Keep control ADB-first and LDPlayer-only. Do not add desktop mouse/keyboard automation unless explicitly requested.
4. Prefer percent-based points through `RelativePoint` and `RelativeArea`; keep emulator keymap G points mirrored in config when changing deploy behavior.
5. For state detection, prefer templates or cropped OCR areas over full-screen OCR.
6. After edits, run `tools\dev.ps1 check`. If touching runtime/device code, also run `tools\dev.ps1 doctor`.
7. For log questions, inspect `logs\bot.log` directly and summarize the newest blocking error first.
8. Use `.agents\hooks\*.md` as project AI hooks before and after changes.

## Important Surfaces

- `BattleFlow._open_battle_from_base`: first three base/search taps.
- `BattleFlow._deploy_army`: slot selection, hero/battle machine/spell order.
- `BotConfig.fallback_deploy_points`: G fallback deployment points copied from `com.supercell.clashofclans.cfg`.
- `VisionModule.detect_state`: village/battle state detection.
- `EmulatorLauncher.start`: LDPlayer startup before ADB/app launch.
- `AdbDevice.screenshot`: ADB screenshot path; empty screenshots usually mean LDPlayer/ADB instability.
- `RecoveryModule.recover`: LDPlayer restart, ADB reconnect, and Clash app restart behavior.
- `CalibrationOverlay.save_overlay`: grid/coordinate overlay written under `logs/calibration`.
- `BotControlUi`: local UI with start, stop, restart, and live log.

## Commands

Use the bundled project tools from repo root:

```powershell
.\tools\dev.ps1 check
.\tools\dev.ps1 doctor
.\tools\dev.ps1 logs -Tail 120
.\tools\dev.ps1 run
.\tools\dev.ps1 ui
.\tools\dev.ps1 calibration
.\tools\dev.ps1 ai-preflight
.\tools\dev.ps1 ai-postedit
.\tools\dev.ps1 ai-logscan
```

Relevant AI hooks live in `.agents\hooks`.
