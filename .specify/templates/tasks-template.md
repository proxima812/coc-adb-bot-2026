---

description: "Task list template for COC-bot-adb feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include project validation tasks for every code change. Additional unit/integration tests are optional unless explicitly requested or required by risk.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **COC-bot-adb**: `coc_bot/`, `tests/`, `tools/dev.ps1`, `config.example.json`
- **Logs/artifacts**: `logs/`, `logs/calibration/`
- **Agent guidance**: `AGENTS.md`, `.agents/hooks/*.md`, `.specify/memory/constitution.md`

## Phase 1: Preflight (Shared Infrastructure)

**Purpose**: Confirm current project state before edits.

- [ ] T001 Read `.agents/hooks/preflight.md`
- [ ] T002 Run `.\tools\dev.ps1 ai-preflight`
- [ ] T003 Inspect the concrete files/logs named by the feature plan
- [ ] T004 Confirm active config behavior: `config.example.json` when `config.json` is absent

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared behavior that must be settled before user story work.

- [ ] T005 Confirm the change preserves ADB-first control
- [ ] T006 Confirm the change preserves LDPlayer-only runtime and does not restore BlueStacks logic
- [ ] T007 For runtime/ADB changes, read `.agents/hooks/runtime-adb.md`
- [ ] T008 For log/debug work, read `.agents/hooks/log-diagnosis.md` and inspect `logs/bot.log`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - [Title] (Priority: P1)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1

- [ ] T009 [P] [US1] Add or update focused tests in `tests/` if risk warrants it

### Implementation for User Story 1

- [ ] T010 [US1] Update [exact file path]
- [ ] T011 [US1] Update config/defaults/docs if behavior changes
- [ ] T012 [US1] Verify story behavior through [command/log/UI/calibration output]

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

- [ ] T013 [US2] Update [exact file path]
- [ ] T014 [US2] Verify story behavior through [command/log/UI/calibration output]

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

- [ ] T015 [US3] Update [exact file path]
- [ ] T016 [US3] Verify story behavior through [command/log/UI/calibration output]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and validation.

- [ ] T900 Read `.agents/hooks/postedit.md`
- [ ] T901 Run `.\tools\dev.ps1 ai-postedit`
- [ ] T902 Run `.\tools\dev.ps1 check`
- [ ] T903 For runtime/ADB changes, run `.\tools\dev.ps1 doctor` or document the concrete blocker
- [ ] T904 Summarize changed files and validation results

---

## Dependencies & Execution Order

- **Preflight**: Must run before edits.
- **Foundational**: Blocks user story work when runtime/config/log scope is involved.
- **User Stories**: Implement in priority order unless tasks touch disjoint files.
- **Polish**: Runs after implementation and before handoff.

## Notes

- Do not add desktop input fallback unless the operator explicitly requested it.
- Do not add or restore BlueStacks code paths.
- Keep `config.example.json` and `coc_bot/config.py` consistent when defaults change.
- Report skipped validation with the exact reason.
