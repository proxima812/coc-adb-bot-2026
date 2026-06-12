# COC-bot-adb Agent Guide

## Defaults

- Reply in Russian when the user writes in Russian.
- Inspect real files/logs before explaining behavior.
- Keep the bot ADB-first; avoid desktop mouse/keyboard fallbacks unless explicitly requested.
- LDPlayer is the only emulator. Do not reintroduce BlueStacks/MEmu/Nox.
- Code is edited from both macOS and Windows. **Runtime is Windows only** (LDPlayer + `tools/dev.ps1`). macOS edits cannot validate ADB/screenshot/recovery — say so in the answer instead of pretending.
- `config.json` is the operator's gitignored config. If it's absent, `BotConfig` defaults run.

## Validation

### macOS

```bash
python -m compileall coc_bot
python -c "from coc_bot.config import load_config, validate_config; c=load_config(); validate_config(c); print('config ok')"
python -m pytest tests/test_config.py tests/test_builder_flow_guard.py
```

Только два теста сохранены как страховка: `test_config` (схема конфига) и `test_builder_flow_guard` (safe-area / forbidden-area builder'a). Тапы, шаблоны, OCR и ADB-стабильность проверяются вручную на Windows-рантайме.

### Windows

```powershell
.\tools\dev.ps1 check         # compile + config validation
.\tools\dev.ps1 doctor        # ADB + screenshot + state detect
.\tools\dev.ps1 logs -Tail 120
.\tools\dev.ps1 ui            # local UI
.\tools\dev.ps1 run           # python -m coc_bot.main
.\tools\dev.ps1 calibration   # one calibration overlay
```

## Key Files

- `coc_bot/config.py` — dataclass `BotConfig` with all defaults.
- `coc_bot/main.py` — entrypoint, picks `home` or `builder` loop.
- `coc_bot/battle_flow.py` — home village flow (`hotkeys` deploy + `ctrl+scroll` camera).
- `coc_bot/builder_flow.py` — builder village flow (rapid deploy + slot-state checks + guarded taps).
- `coc_bot/vision.py` — templates, OCR, state detection, `frame()` reuse.
- `coc_bot/adb_device.py` — ADB commands, persistent shell, screenshot retries, emulator key combos.
- `coc_bot/emulator.py` — LDPlayer startup.
- `coc_bot/recovery.py` — LDPlayer restart, ADB reconnect, app restart.
- `coc_bot/calibration.py` — percent-grid overlays under `logs/calibration`.
- `coc_bot/ui.py` — CustomTkinter UI.
- `main-village.md` / `builder-village.md` — narrative description of the current flows. Update when behavior changes.

## AI Hooks

- Before code edits: `.agents/hooks/preflight.md`.
- After code edits: `.agents/hooks/postedit.md`.
- ADB/runtime changes: `.agents/hooks/runtime-adb.md`.
- Deploy tuning: `.agents/hooks/deploy-tuning.md`.
- Log/debug: `.agents/hooks/log-diagnosis.md`.
