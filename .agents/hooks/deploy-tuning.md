# AI Hook: Deploy Tuning

Use before changing troop / hero / siege / spell / G-fallback deployment in either flow.

## Home village

1. `deploy_mode` controls the path. Operator default: `hotkeys`. Other paths (`coordinates`, `templates`, `g_key`) exist but are not the active flow.
2. `hotkeys` order is fixed in `_deploy_army_by_hotkeys`:
   - troop key (`home_hotkey_troop_key`) + `home_hotkey_troop_g_point_passes` over `home_hotkey_g_point_keys`,
   - each key in `home_hotkey_all_point_keys` + `home_hotkey_all_point_passes` over `home_hotkey_g_point_keys`,
   - spell key (`home_hotkey_spell_key`) + random spells via `deploy_plan` "spells" step,
   - `_activate_hotkey_hero_abilities` over `home_hotkey_hero_keys` (after spells, not before).
3. Random spell taps come from the `spells` step in `deploy_plan` (`spell_deploy_area`, `random_taps_min/max`).
4. `pre_spell_delay_seconds` and `_activate_hero_abilities` belong to the `coordinates` path only. Do not insert them into the hotkey path.
5. If editing G-point keys, also update LDPlayer keymap in the operator's `com.supercell.clashofclans.cfg` (lives on the Windows runtime, not in this repo).
6. Camera prep is `ctrl_mouse_wheel_zoom_out` when `battle_camera_direct_ctrl_scroll_enabled`. Do not touch pinch / pan settings unless you intend to use the legacy path.

## Builder village

1. Single deploy point (`builder_deploy_point`) with neighbor expansion (`deploy_neighbor_offset_percent`, expanded into 5 points).
2. Initial pass: `_rapid_deploy_slots_through_g` taps slot then neighbor-expanded deploy point for each of 8 `builder_troop_slots`.
3. Slot state pass: `_check_builder_slot_states` runs `builder_slot_state_check_passes` times; per-slot actions are fixed (see SKILL.md / `builder-village.md`).
4. During wait: redeploy every `builder_redeploy_slots_interval_seconds`, hero ability every `builder_hero_ability_interval_seconds`. Disable by zeroing intervals only if you also disable the matching `_enabled` flag.
5. Every builder tap is guarded by safe-area + forbidden-areas. New deploy points must stay inside `builder_safe_tap_area` and outside every `builder_forbidden_tap_areas` rectangle, or recovery will trip on `UnsafeBuilderTapError`.
