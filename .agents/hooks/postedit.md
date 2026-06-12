# AI Hook: Post-Edit

Use after changing code or config.

1. If on Windows, run `.\tools\dev.ps1 check`. If on macOS, run `python -m compileall coc_bot && python -c "from coc_bot.config import load_config, validate_config; c=load_config(); validate_config(c); print('config ok')"` — same intent, no PowerShell required.
2. Touched deploy logic (`battle_flow._deploy_army*`, `builder_flow._deploy_slots*`, hotkey keys, neighbor offsets, deploy_plan)? Confirm `deploy_mode` you targeted is the actual active mode; the two paths do not share code.
3. Touched vision (templates, OCR, state detection)? Keep template thresholds (`*_template_threshold`) and crop areas (`*_template_area`, `state_ocr_*`) in sync with config.
4. Touched ADB/recovery/launcher? Keep LDPlayer startup, screenshot retries, reconnect, and app launch failures actionable in `logs/bot.log` (one ERROR line per blocking failure).
5. Touched UI? Verify imports without auto-launching the bot. UI is `customtkinter`-based.
6. Touched the active flow described in `main-village.md` or `builder-village.md`? Update the doc in the same change.
7. Run the two surviving pytest targets if you touched config schema or builder guard zones: `python -m pytest tests/test_config.py tests/test_builder_flow_guard.py`. Everything else is hand-tested on the Windows runtime — there is no broader pytest net.
8. In the final answer, state what was changed and what was validated (or what could not be validated on the current OS).
