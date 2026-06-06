# AI Hook: Deploy Tuning

Use before changing troop, hero, battle machine, spell, or G fallback deployment.

1. Keep deploy order explicit in `deploy_plan`.
2. Use `primary_deploy_point` plus `fallback_deploy_points` for near-salvo deployment.
3. If adding G points, parse `com.supercell.clashofclans.cfg` and mirror every `Key == "G"` point.
4. Keep spells delayed by `pre_spell_delay_seconds` unless the user changes the timing.
5. Keep rapid tap timing configurable through `deploy_step_delay_seconds` and `rapid_deploy_tap_delay_seconds`.
