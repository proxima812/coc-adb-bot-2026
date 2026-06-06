# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[###-feature-name]`

**Created**: [DATE]

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [Brief Title] (Priority: P1)

[Describe the operator journey in plain language]

**Why this priority**: [Explain operator value and priority]

**Independent Test**: [Describe how this can be tested independently with files, logs, UI, calibration output, or bot behavior]

**Acceptance Scenarios**:

1. **Given** [initial bot/emulator/config state], **When** [operator action or bot step], **Then** [expected observable outcome]
2. **Given** [initial bot/emulator/config state], **When** [operator action or bot step], **Then** [expected observable outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)

[Describe this operator journey in plain language]

**Why this priority**: [Explain operator value and priority]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial bot/emulator/config state], **When** [operator action or bot step], **Then** [expected observable outcome]

---

### User Story 3 - [Brief Title] (Priority: P3)

[Describe this operator journey in plain language]

**Why this priority**: [Explain operator value and priority]

**Independent Test**: [Describe how this can be tested independently]

**Acceptance Scenarios**:

1. **Given** [initial bot/emulator/config state], **When** [operator action or bot step], **Then** [expected observable outcome]

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- What happens when LDPlayer is closed, frozen, or not reachable through ADB?
- What happens when screenshot capture is empty, stale, or OCR/template detection fails?
- What happens when `config.json` is absent and `config.example.json` is the active config?
- What happens when the current Clash of Clans screen is not the expected village/battle state?
- What happens when logs are missing, rotated, or do not contain the expected evidence?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST [specific observable bot/operator capability]
- **FR-002**: System MUST [specific config/log/calibration/runtime behavior]
- **FR-003**: Operator MUST be able to [key local UI or command workflow]
- **FR-COC-001**: System MUST preserve ADB-first control unless the operator explicitly requests a desktop fallback.
- **FR-COC-002**: System MUST target LDPlayer only and MUST NOT restore BlueStacks logic.
- **FR-COC-003**: System MUST keep `config.example.json` valid as the active fallback config.
- **FR-COC-004**: System MUST expose enough logs or validation output for operator diagnosis.

### Key Entities *(include if feature involves data/config/state)*

- **[Entity 1]**: [What it represents, key attributes without implementation]
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: [Operator can complete the workflow or verify behavior through a concrete command/log/UI outcome]
- **SC-002**: [Bot behavior meets a concrete timing, reliability, or detection threshold]
- **SC-003**: [Validation command succeeds or produces expected diagnostic output]

## Assumptions

- The operator is running on Windows with LDPlayer and ADB available.
- `config.example.json` is active when `config.json` is missing.
- Clash of Clans UI/state detection may require real screenshots or log evidence.
