# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `$speckit-plan` skill.

## Summary

[Extract from feature spec: primary operator requirement + technical approach]

## Technical Context

**Language/Version**: Python [version from active environment or NEEDS CLARIFICATION]

**Primary Dependencies**: OpenCV, Pillow, EasyOCR, NumPy, Loguru, ADB/LDPlayer tools

**Storage**: JSON config, local logs, screenshot/calibration artifacts

**Testing**: `.\tools\dev.ps1 ai-preflight`, `.\tools\dev.ps1 ai-postedit`, `.\tools\dev.ps1 check`, plus `doctor` for runtime/ADB changes

**Target Platform**: Windows + LDPlayer + ADB

**Project Type**: Local Python automation bot with simple operator UI

**Performance Goals**: [bot timing, deploy speed, screenshot/OCR latency, or NEEDS CLARIFICATION]

**Constraints**: ADB-first control, LDPlayer-only runtime, `config.example.json` fallback, no BlueStacks restoration

**Scale/Scope**: Single local operator, one LDPlayer emulator, current Clash of Clans workflow

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- ADB-first: Does the plan avoid desktop mouse/keyboard fallbacks unless explicitly requested?
- LDPlayer-only: Does the plan avoid BlueStacks paths, launchers, window lookup, and recovery logic?
- Config truth: Does the plan keep `coc_bot\config.py` and `config.example.json` consistent?
- Evidence first: Has the plan identified the real files/logs to inspect before changes?
- Hook-gated delivery: Does the plan include `ai-preflight`, `ai-postedit`, and `check`?
- Runtime diagnosis: If ADB, screenshot, emulator startup, or recovery changes are involved, does the plan include `doctor`?

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
  plan.md
  research.md
  data-model.md
  quickstart.md
  contracts/
  tasks.md
```

### Source Code (repository root)

```text
coc_bot/
  config.py
  emulator.py
  ui.py
  calibration.py
  battle_flow.py
  vision.py
  adb_device.py
  recovery.py
tests/
tools/
  dev.ps1
logs/
config.example.json
com.supercell.clashofclans_1600x900.kmp
```

**Structure Decision**: [Document the selected files/directories and why]

## Complexity Tracking

> Fill only if Constitution Check has violations that must be justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., desktop fallback] | [current need] | [why ADB-first is insufficient] |
