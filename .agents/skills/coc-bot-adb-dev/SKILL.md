---
name: coc-bot-adb-dev
description: Develop, debug, validate, and tune the COC bot (Clash of Clans, LDPlayer + ADB). Use for ADB control, LDPlayer startup, home village battle flow (hotkeys deploy + ctrl+scroll camera), builder village flow, OCR/state detection, deploy timing, calibration overlays, UI, recovery, config tuning.
---

# COC Bot ADB Dev

## Project Shape

- Runtime is **Windows + LDPlayer** (paths default to `D:\LDPlayer\LDPlayer9\adb.exe`).
- Repo can be edited from macOS but is run from Windows. PowerShell tooling lives in `tools/dev.ps1`.
- Two flows: home village (`coc_bot/battle_flow.py`) and builder village (`coc_bot/builder_flow.py`). Mode picked by `bot_mode` or `--bot-mode`.
- Current home village deploy mode: `hotkeys` (slot keys `1` and `2..6` with `G+1..G+8` passes, then spell key `7`, then hero abilities `3..6`).
- Camera prep: direct `Ctrl+mouse wheel down` (`battle_camera_direct_ctrl_scroll_enabled`); legacy ADB pinch path only runs if direct scroll is disabled.

## Workflow

1. Read before editing. Start with `coc_bot/main.py`, `coc_bot/battle_flow.py`, `coc_bot/builder_flow.py`, `coc_bot/vision.py`, `coc_bot/adb_device.py`, `coc_bot/config.py`.
2. If `config.json` is missing, defaults from `BotConfig` are active (no `config.example.json` is shipped). The operator's `config.json` is gitignored.
3. Stay ADB-first and LDPlayer-only. No desktop mouse/keyboard fallbacks unless explicitly requested.
4. Use percent-based `RelativePoint` / `RelativeArea`. Never hard-code pixel coords.
5. Prefer template matches (`vision.find_template` / `has_*_button`) over full-screen OCR. OCR areas must be cropped via `state_ocr_*` rectangles.
6. After code edits, run `tools/dev.ps1 check`. If touching runtime/device/emulator code, also run `tools/dev.ps1 doctor`.
7. For log triage, read `logs/bot.log` directly; lead with the newest blocking error.
8. Update `main-village.md` and `builder-village.md` when the flow they describe changes.

## Important Surfaces

### Home village (`coc_bot/battle_flow.py`)
- `BattleFlow.run_once`: cycle order — dismiss_popups → open_battle_from_base → wait_for_battle → prepare_battle_camera → deploy_army → sleep `wait_after_deploy_seconds` → finish_and_return_home → dismiss_popups.
- `_open_battle_from_base`: home FREE check between first taps when `home_free_check_enabled`.
- `_prepare_battle_camera`: early-returns when `battle_camera_direct_ctrl_scroll_enabled = true`.
- `_deploy_army_by_hotkeys`: troop key `1` + 3 passes of `G+1..G+8`; then each of `home_hotkey_all_point_keys = 2..6` with one G-pass; then spell key `7` + random spells; then `_activate_hotkey_hero_abilities` (`3..6`).
- `_deploy_army` (coordinate fallback): only used if `deploy_mode = coordinates`. Spell delay `pre_spell_delay_seconds` and `_activate_hero_abilities` belong to this path.

### Builder village (`coc_bot/builder_flow.py`)
- `BuilderBattleFlow.run_once`: dismiss_popups → wait_for_base → open_attack → wait_for_battle → deploy_slots → wait_and_return_home → dismiss_popups.
- `_rapid_deploy_slots_through_g`: 8 builder slots, each followed by neighbor-expanded `builder_deploy_point`.
- `_check_builder_slot_states`: per-slot template check; actions per state (`ability_ready` → tap slot, `not_deployed` → tap slot + deploy point, `deployed`/`unknown` → noop).
- `_wait_and_return_home`: periodic redeploy every `builder_redeploy_slots_interval_seconds`, hero ability every `builder_hero_ability_interval_seconds`, hard timeout `builder_battle_timeout_seconds`.
- Tap guards: every builder tap goes through `_calibrate_builder_tap` + `_guard_builder_point` (safe + forbidden areas). Raises `UnsafeBuilderTapError`, which recovery handles.

### Shared
- `VisionModule.detect_state`, `has_okay_button`, `has_configured_popup`, `has_free_button`, `has_builder_*`.
- `AdbDevice.tap_many_percent` / `hold_many_percent` / `ctrl_mouse_wheel_zoom_out` / `press_emulator_key` / `press_emulator_key_combo`.
- `EmulatorLauncher.start_and_connect`: LDPlayer startup before ADB/app launch.
- `RecoveryModule.recover`: LDPlayer restart, ADB reconnect, app restart.
- `CalibrationOverlay`: grid/coordinate overlays under `logs/calibration` and `logs/calibration/builder`.
- `BotControlUi` (`coc_bot/ui.py`): CustomTkinter UI with start/stop/restart and live log.

## Commands (Windows / PowerShell)

```powershell
.\tools\dev.ps1 check        # compile + load_config + validate_config
.\tools\dev.ps1 doctor       # ADB devices + screenshot + state detect
.\tools\dev.ps1 logs -Tail 120
.\tools\dev.ps1 run          # python -m coc_bot.main
.\tools\dev.ps1 ui           # python -m coc_bot.ui
.\tools\dev.ps1 calibration  # save one calibration overlay
```

## Tests

Only two pytest files are kept as a cheap regression net:

- `tests/test_config.py` — `BotConfig` schema / `validate_config` / `_config_from_dict`.
- `tests/test_builder_flow_guard.py` — builder safe-area / forbidden-area guard and slot-state actions.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_builder_flow_guard.py
```

Tap accuracy, vision thresholds, OCR, and ADB stability are not covered by tests. Validate them on the Windows runtime via `dev.ps1 doctor` / `dev.ps1 run` and overlay logs.

## AI Hooks

Read `.agents/hooks/*.md` before/after edits. They cover preflight, post-edit validation, runtime/ADB safety, deploy tuning, and log diagnosis.
