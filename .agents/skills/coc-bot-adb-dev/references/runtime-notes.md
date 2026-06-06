# Runtime Notes

- LDPlayer is the only supported emulator runtime for this bot.
- ADB path defaults to `D:\LDPlayer\LDPlayer9\adb.exe`.
- LDPlayer player path defaults to `D:\LDPlayer\LDPlayer9\dnplayer.exe`.
- Device serial defaults to `127.0.0.1:5555`.
- Bot startup calls `EmulatorLauncher.start_and_connect()`, then launches `com.supercell.clashofclans` through ADB.
- Recovery starts LDPlayer, reconnects ADB, force-stops Clash, then starts Clash again.
- Keep LDPlayer open and avoid changing resolution while the bot runs.
- Empty screenshot failures should be handled through retries in `AdbDevice.screenshot`.
- If `config.json` does not exist, `load_config()` reads `config.example.json`.
- Current deploy strategy is sequential but fast: select one slot, then use G-key or configured fallback points.
- Calibration overlays are saved under `logs/calibration` when enabled.
- The operator UI is launched with `.\tools\dev.ps1 ui` or `start-ui.bat`.
