<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles: template placeholders -> ADB-First Control, LDPlayer-Only Runtime, Config Truth, Evidence-First Changes, Hook-Gated Delivery
Added sections: Project Constraints, Development Workflow, Governance
Removed sections: none
Templates requiring updates: .specify/templates/plan-template.md updated, .specify/templates/spec-template.md updated, .specify/templates/tasks-template.md updated
Follow-up TODOs: none
-->
# COC-bot-adb Constitution

## Core Principles

### I. ADB-First Control
All bot behavior MUST use ADB as the default control path. Desktop mouse and
keyboard automation is out of scope unless the operator explicitly requests it
for a specific task. Any feature that changes taps, screenshots, app launch, or
runtime recovery MUST preserve the ADB control surface first.

### II. LDPlayer-Only Runtime
The current emulator target is LDPlayer only. Specs, plans, tasks, and code MUST
NOT introduce or restore BlueStacks paths, launchers, window lookup, keymap
logic, or recovery behavior. Emulator startup and reconnect work belongs in
`coc_bot\emulator.py`, `coc_bot\recovery.py`, and `coc_bot\adb_device.py`.

### III. Config Truth
`config.example.json` is the active operator config when `config.json` is
absent. Bot defaults in `coc_bot\config.py`, runtime behavior, calibration
overlays, and documentation MUST stay consistent with that fallback. Changes to
deploy points MUST preserve percent-based `RelativePoint`/`RelativeArea`
semantics and keep fallback G points aligned with the emulator keymap source.

### IV. Evidence-First Changes
Agents MUST inspect real files or logs before explaining or changing behavior.
Log/debug tasks MUST read `logs\bot.log` or `.\tools\dev.ps1 logs -Tail N` and
report the newest blocking evidence first. Runtime and ADB diagnosis MUST read
`.agents\hooks\runtime-adb.md` before changing LDPlayer, recovery, screenshot,
or app launch behavior.

### V. Hook-Gated Delivery
Before code edits, agents MUST read `.agents\hooks\preflight.md` and run
`.\tools\dev.ps1 ai-preflight`. After code edits, agents MUST read
`.agents\hooks\postedit.md` and run `.\tools\dev.ps1 ai-postedit`. Before
handing off code changes, agents MUST run `.\tools\dev.ps1 check`. Runtime/ADB
changes SHOULD also run `.\tools\dev.ps1 doctor` unless the device state makes
that impossible, in which case the blocker must be reported.

## Project Constraints

The implementation language is Python. The main package lives in `coc_bot\`,
with tests in `tests\`, local operator tools in `tools\dev.ps1`, logs in
`logs\`, and runtime launchers in `start.bat` and `start-ui.bat`.

Feature specs MUST treat the operator as the primary user. Requirements should
describe observable bot behavior, recovery behavior, calibration output, logs,
or UI controls rather than generic web/API abstractions.

The key files for planning are:

- `coc_bot\config.py`: dataclasses and defaults.
- `config.example.json`: current operator config fallback.
- `coc_bot\emulator.py`: LDPlayer startup before ADB/app launch.
- `coc_bot\ui.py`: local UI with start, stop, restart, and log view.
- `coc_bot\calibration.py`: screenshot overlay with grid and deploy areas.
- `coc_bot\battle_flow.py`: base search, deploy order, spells, return home.
- `coc_bot\vision.py`: OCR/templates/state detection.
- `coc_bot\adb_device.py`: ADB commands and screenshot retries.
- `coc_bot\recovery.py`: LDPlayer restart and ADB/app reconnect logic.
- `com.supercell.clashofclans_1600x900.kmp`: emulator keymap source.

## Development Workflow

Spec Kit is used for larger or ambiguous changes through:

1. `$speckit-specify`
2. `$speckit-clarify` when requirements are ambiguous
3. `$speckit-plan`
4. `$speckit-tasks`
5. `$speckit-analyze` before implementation when plan/tasks are non-trivial
6. `$speckit-implement`

Small direct fixes may skip the full Spec Kit flow, but they MUST still follow
the AI hooks and validation gates from this constitution and `AGENTS.md`.

Plans MUST name the concrete files being touched and the validation commands
that will be run. Tasks MUST include AI hook steps and final project checks.
Runtime tasks MUST include the relevant ADB/LDPlayer diagnostic command.

## Governance

This constitution supersedes generic Spec Kit templates for this repository.
`AGENTS.md` and `.agents\hooks\*.md` remain authoritative operational guidance;
when there is a conflict, follow the stricter rule and update the stale
document in the same change.

Amendments require updating this file, reviewing dependent Spec Kit templates,
and recording the version change in the Sync Impact Report. Versioning follows
semantic versioning: MAJOR for incompatible governance changes, MINOR for new
principles or workflow sections, PATCH for clarifications.

Every generated spec, plan, and task list MUST pass the constitution check
before implementation starts. Every code handoff MUST report which validation
commands ran and any skipped checks with a concrete reason.

**Version**: 1.0.0 | **Ratified**: 2026-06-06 | **Last Amended**: 2026-06-06
