# Branch Ruleset Readiness

This document prepares the human maintainer to configure GitHub branch rules. It does not configure or change GitHub settings. Do not apply rules until the repository owner approves the policy and verifies the required-check names in GitHub Actions.

## Existing CI Check Candidates

The current workflow is [`.github/workflows/test.yml`](../../.github/workflows/test.yml), named `CI`, and has these named jobs:

- `Backend tests (pytest, PostgreSQL)`
- `Backend security gates (Ruff, pip-audit)`
- `Frontend tests (jest, lint, prettier)`
- `Docker Compose smoke test`

These are candidates only, not confirmed GitHub required-check context strings. Run the workflow for a pull request targeting `main`, inspect the completed check list in GitHub, and record the exact stable names and their source before selecting required checks. Do not guess a workflow/job display prefix. Confirm that the checks are reported by the expected GitHub Actions workflow and are not skipped due to path filters or configuration.

## Proposed `main` Ruleset Review

After human approval and check-name verification, consider configuring:

- Require changes to enter `main` through a pull request; prohibit force-push and branch deletion.
- Require all verified CI checks that protect the repository's actual backend, security, frontend, and container validation paths.
- Require an approving human review and dismissal of stale approvals when new commits are pushed. Confirm reviewer availability first; a solo maintainer cannot approve their own PR.
- Require resolved review conversations where the repository's review process supports them.
- Keep bypass limited to explicitly named human administrators for documented emergencies. Do not grant bypass to agents or automation.
- Add CODEOWNERS only after reviewer identities and ownership boundaries are confirmed, especially for authentication/security, migrations, CI, agent configuration, `.harness/`, and `.claude/`.

The repository currently uses a workflow-level `contents: read` permission. Do not expand workflow token permissions as part of branch protection setup. Branch rules do not replace least-privilege workflow permissions or the requirement that agents have no merge/deployment authority.

## Human Configuration and Verification

1. Confirm the target repository and default branch are `main`; review existing protections to avoid replacing or weakening them.
2. Observe a complete pull-request CI run and record exact required check names, workflow identity, and whether each check is consistently reported.
3. Decide reviewer requirements that are enforceable for the available maintainer/team size.
4. Have a repository administrator configure the approved ruleset in GitHub settings. No agent should perform this action.
5. Verify behavior with a test PR: direct push/force-push is blocked as intended, required checks block merge when failing or missing, human review is required, and authorized maintainers retain only the intended emergency bypass.
6. Record the policy owner, review date, checks required, bypass principals, and any exception/rollback procedure in the repository's governance record.

Do not enable automated merge. Deployment/release approval remains a separate human-controlled process.