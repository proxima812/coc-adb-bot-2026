# COC Bot ADB

ADB-first Clash of Clans automation for LDPlayer.

## Runtime

- Emulator: LDPlayer only.
- Active config fallback: `config.example.json` when `config.json` is missing.
- Main bot command: `.\tools\dev.ps1 run`.
- Local UI command: `.\tools\dev.ps1 ui`.
- Calibration command: `.\tools\dev.ps1 calibration`.

## Logs

- Main runtime log: `logs/bot.log`.
- Detailed action log: `logs/actions.log`.
- Debug screenshots: `logs/screenshots`.
- Calibration overlays: `logs/calibration`.

`actions.log` records taps, holds, swipes, emulator key presses, screenshots, app launches, ADB reconnects, LDPlayer starts, and recovery attempts.

## Validation

Run these before handing off changes:

```powershell
.\tools\dev.ps1 ai-preflight
.\tools\dev.ps1 ai-postedit
.\tools\dev.ps1 check
```

For runtime diagnosis:

```powershell
.\tools\dev.ps1 doctor
.\tools\dev.ps1 logs -Tail 120
```
