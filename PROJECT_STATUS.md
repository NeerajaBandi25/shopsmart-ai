# ShopSmart AI — Project Status

## Historical Phase

The Agent Harness Phase 1C work below is a completed historical increment. Current
portfolio-completion status is recorded later in this file and in
`.factory/status.md`.

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

The active portfolio-completion checkout is `feature/promotions-discount-engine`.
The current local application is a unified commerce and AI assistant product,
not the historical Phase 1C-only state above. Current verification and explicit
remaining readiness gates are recorded in `.factory/status.md` and
`docs/product-audit.md`.

Latest verified state (2026-10-03): `shopsmart_portfolio` is at Alembic revision
`017_order_delivery_images` with 1,200 products and repository-generated product
art. The full SQLite backend run passed 282 tests with 6 database-specific
skips; frontend TypeScript, 138 Jest tests, lint, and production build passed.
This is not a portfolio-ready claim: reliable responsive captures and the
accessibility, security, performance, journey, and independent-review gates are
still outstanding.

## Next Engineering Work

Close the remaining gates in `.factory/status.md`. Preserve the local-only
database restrictions and existing records. Do not deploy, merge, commit, or
push as part of this portfolio verification.

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
