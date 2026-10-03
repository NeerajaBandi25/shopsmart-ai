# ShopSmart AI — Project Status

## Current Phase

ShopSmart AI — Agent Harness Phase 1C completed.

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

As of 2026-10-03, `origin/main` contains the authentication, catalog, shopping,
commerce BFF, Redis cache, frontend state, observability, CI/CD foundation,
AI/RAG, provider gateway, AI governance/security, and commerce-assistant work.

PR #44, `feat: add production commerce assistant and structured search`, is
merged into `main` at `24c82e984f6d6658fc0676eb1223948a03d9eb46`. The merged
increment includes structured category search and migration 012, production-like
seed/evaluator data, cart/order assistant behavior, backend-owned policy RAG,
and bounded assistant/search logging. Post-merge CI run [37112240926](https://github.com/NeerajaBandi25/shopsmart-ai/actions/runs/37112240926)
passed all four required checks: backend tests, backend security gates, frontend
tests/lint/Prettier, and Docker Compose smoke test.

The current product contract is in `specs/008-ai-rag/spec.md`; the root
`plan.md` is a historical authentication assessment, not the current plan.

## Next Engineering Work

Specify the next product increment before implementation. Promotions/discounts,
richer category hierarchy, and brand/variant modeling remain product gaps;
live external-provider quality/cost validation also remains outstanding.
Preserve the existing authentication, BFF, provider-governance, and harness
boundaries.

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
