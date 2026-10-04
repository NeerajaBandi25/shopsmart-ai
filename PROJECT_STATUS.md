# ShopSmart AI — Project Status

## Historical Phase

The Agent Harness Phase 1C work below is a completed historical increment.
Current application verification is tracked in `.factory/status.md`.

## Project Rule

The repository is the source of truth.
Do not rely on previous conversation history.
Do not restart completed work.

## Completed

### Phase 1A — Trusted Policy

Completed.

### Phase 1B — Authorization Engine

Completed and committed.

Commit:
e3cd368 feat(harness): implement phase 1 authorization engine

Verified:
42 Phase 1B tests passed.

### Phase 1C — Claude Code PreToolUse Enforcement

Completed.

Implemented:

- .harness/lib/tool_adapter.py
- .harness/hooks/pre_tool_use.py
- .harness/tests/hooks/test_pre_tool_use.py
- .harness/policies/trusted/tool-registry.yaml
- .claude/settings.json

## Verification

Automated:

- Phase 1B + Phase 1C tests: 70 passed, 0 failed.

Direct hook verification:

- application READ → ALLOW
- harness implementation READ → ALLOW
- .claude/settings.json READ → ALLOW
- .git/config READ → DENY
- trusted policy READ → DENY
- application WRITE → ASK
- harness WRITE → DENY
- path traversal → DENY
- unknown tool → DENY
- malformed JSON → DENY
- Bash → DENY

Real Claude Code / FCC runtime:

- application READ executed successfully
- .git/config was blocked before file contents were exposed

## Security Model

Read access to harness implementation and tests is allowed.

Write access to harness implementation remains denied.

Trusted policy and state locations remain protected.

Unsupported command execution remains denied.

No generic shell executor has been added.

## Launcher Independence

The same project is usable through:

- omniroute.cmd launch
- fcc-claude

Both use the same:

- CLAUDE.md
- PROJECT_STATUS.md
- .claude/settings.json
- .harness/

The launcher/provider does not define project state.

## Current Application Work

The active application checkout is `feature/promotions-discount-engine`; the current
local product combines the storefront, commerce services, and AI assistant. Current
production-completion status is **VERIFYING**, not ready for production. Use
`.factory/status.md` as the active workstream checkpoint for verified product claims,
validation evidence, and remaining gates. Do not use the dated baseline in
`docs/product-audit.md` as a current blocker list.

## Historical Verification Snapshot (2026-10-03)

The previously recorded database revision, product count, and backend/frontend test
counts are a historical snapshot only. They do not establish the current state or
satisfy current production-completion gates; consult `.factory/status.md` for the
latest recorded verification.

## Next Engineering Work

Continue the active work from `.factory/status.md` and the user's current task. Keep
changes on the existing branch and Draft PR. Do not merge or deploy unless explicitly
requested.

## Important Constraints

Do NOT:

- redo Phase 1A/1B/1C
- create duplicate ToolAdapter tests
- add Agent SDK
- add generic shell executor
- add workspace hashing yet
- add multi-agent architecture
- change OmniRoute/FCC provider routing unless specifically required
- modify unrelated application files during harness maintenance
