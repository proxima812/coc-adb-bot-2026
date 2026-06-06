# AI Hook: Post-Edit

Use after changing code or config.

1. Run `.\tools\dev.ps1 ai-postedit`.
2. If deploy points changed, verify `len(load_config().fallback_deploy_points)` and compare with `G` points in `com.supercell.clashofclans.cfg`.
3. If OCR/state changed, ensure OCR is cropped to relevant areas where possible.
4. If ADB/recovery/launcher changed, keep LDPlayer startup, screenshot, reconnect, and app launch failures actionable in logs.
5. If UI changed, verify import/tests without auto-starting the bot unless the user requested a runtime test.
6. In the final answer, mention what was changed and whether validation passed.
