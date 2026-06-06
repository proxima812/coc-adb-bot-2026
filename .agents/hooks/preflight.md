# AI Hook: Preflight

Use before changing bot code.

1. Confirm the task target: deploy flow, OCR/state detection, ADB/recovery, config, launcher, or logs.
2. Read the relevant files before editing:
   - Deploy: `coc_bot\battle_flow.py`, `coc_bot\config.py`, `config.example.json`.
   - OCR/state: `coc_bot\vision.py`, `coc_bot\config.py`.
   - ADB/recovery/launcher: `coc_bot\adb_device.py`, `coc_bot\emulator.py`, `coc_bot\recovery.py`, `coc_bot\main.py`.
   - UI/log control: `coc_bot\ui.py`, `tools\dev.ps1`, `start-ui.bat`.
   - Calibration overlay: `coc_bot\calibration.py`, `coc_bot\battle_flow.py`, `config.example.json`.
   - Keymap/G points: `com.supercell.clashofclans.cfg`.
3. Treat `config.example.json` as active if `config.json` is missing.
4. Preserve ADB-first control and LDPlayer-only runtime. Do not reintroduce BlueStacks.
5. Run `.\tools\dev.ps1 ai-preflight` unless the request is read-only.
