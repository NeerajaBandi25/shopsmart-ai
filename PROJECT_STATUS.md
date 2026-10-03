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
AI/RAG, provider gateway, and AI governance/security work through PR #43.

The commerce-assistant and structured-category increment is in
`feature/ai-provider-governance-hardening` and is not yet part of `main`. Its
current product contract is in `specs/008-ai-rag/spec.md`; the root
`plan.md` is a historical authentication assessment, not the current plan.

## Next Engineering Work

Review and validate the unmerged commerce-assistant increment against the
current `origin/main` before creating its pull request. Preserve the existing
authentication, BFF, provider-governance, and harness boundaries. Do not treat
the assistant branch as merged until its pull request is reviewed and merged.

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
