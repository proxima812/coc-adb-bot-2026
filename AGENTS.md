# COC-bot-adb Agent Guide

## Defaults

- Reply in Russian when the user writes in Russian.
- Inspect real files/logs before explaining behavior.
- Keep the bot ADB-first; avoid desktop mouse/keyboard fallbacks unless explicitly requested.
- `config.example.json` is active when `config.json` is missing.
- Current emulator is LDPlayer only. Do not use or restore BlueStacks paths, launchers, window lookup, or recovery logic.

## Validation

Use AI hook commands during agent work:

```powershell
.\tools\dev.ps1 ai-preflight
.\tools\dev.ps1 ai-postedit
.\tools\dev.ps1 ai-logscan -Tail 120
```

Useful operator commands:

```powershell
.\tools\dev.ps1 ui
.\tools\dev.ps1 run
.\tools\dev.ps1 calibration
```

Run before handing off code changes:

```powershell
.\tools\dev.ps1 check
```

Run for runtime/ADB diagnosis:

```powershell
.\tools\dev.ps1 doctor
.\tools\dev.ps1 logs -Tail 120
```

## Key Files

- `coc_bot\config.py`: dataclasses and defaults.
- `config.example.json`: current operator config fallback.
- `coc_bot\emulator.py`: LDPlayer startup before ADB/app launch.
- `coc_bot\ui.py`: simple local UI with start/stop/restart and log view.
- `coc_bot\calibration.py`: screenshot overlay with percent grid, slots, G points, and spell area.
- `coc_bot\battle_flow.py`: base search, deploy order, spells, return home.
- `coc_bot\vision.py`: OCR/templates/state detection.
- `coc_bot\adb_device.py`: ADB commands, screenshot retries.
- `coc_bot\recovery.py`: LDPlayer restart and ADB/app reconnect logic.
- `com.supercell.clashofclans.cfg`: emulator keymap source for G points.
- `start-ui.bat`: double-click launcher for the local UI.

## AI Hooks

- Before code edits: read `.agents\hooks\preflight.md` and run `.\tools\dev.ps1 ai-preflight`.
- After code edits: read `.agents\hooks\postedit.md` and run `.\tools\dev.ps1 ai-postedit`.
- For log/debug tasks: read `.agents\hooks\log-diagnosis.md` and run `.\tools\dev.ps1 ai-logscan -Tail 160`.
- For ADB/runtime tasks: read `.agents\hooks\runtime-adb.md` before changing LDPlayer, recovery, screenshot, or app launch behavior.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
