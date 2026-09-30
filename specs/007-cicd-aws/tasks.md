# Tasks: CI/CD and AWS Deployment

**Input**: Design documents from `/specs/007-cicd-aws/`

## Phase 1: Contract and Preflight

- [x] T001 Add deployment preflight validation for main SHA and latest required
      GitHub CI checks in `.github/scripts/deploy_preflight.py`.
- [x] T002 Add offline tests for stale/non-main refs, absent/incomplete/failed
      checks, and successful latest attempts in `.github/scripts/deploy_preflight.py`.

## Phase 2: Backend Release

- [x] T003 Add tested ECS deployment helper for immutable ECR image publishing,
      task-definition validation, one-off Alembic migration, service readiness,
      and rollback in `.github/scripts/deploy_ecs.py`.
- [x] T004 Add manual production workflow with exact-SHA preflight, human
      approval, isolated AWS OIDC permissions, Vercel deployment, and rollback
      jobs in `.github/workflows/deploy-production.yml`.

## Phase 3: Frontend Release and Operations

- [x] T005 Disable duplicate automatic Vercel Git deployments in
      `frontend/vercel.json` and ignore generated `.vercel/` files in `.gitignore`.
- [x] T006 Document required GitHub environments, IAM/OIDC trust and permissions,
      ECR/ECS/RDS/CloudWatch/Vercel configuration, release, failure, and rollback
      procedures in `AWS_DEPLOYMENT.md`.
- [x] T007 Add the helper self-tests and deployment configuration parsing to
      existing jobs without changing any of the four required check names in
      `.github/workflows/test.yml`.

## Phase 4: Verification

- [x] T008 Run focused script tests, backend and frontend suites, security,
      formatting, build, Compose/workflow validation, and diff/artifact/scope
      audits; record unavailable AWS/Docker/Vercel checks in
      `specs/007-cicd-aws/tasks.md`.
- [x] T009 Independently review the complete Feature 007 diff against
      `origin/main`, fix legitimate findings, rerun affected and full applicable
      checks, then finalize only the intended Feature 007 files.

## Verification Evidence (T008/T009)

- Offline helper self-tests: `deploy_preflight.py` (7 tests), `deploy_ecs.py`
  (13 tests, including CLI entry-point wiring, post-migration release
  recheck, and redirect-rejecting readiness probe), `deploy_workflow_tests.py`
  (8 contract tests) — all passing.
- Pinned Ruff (`ruff==0.1.8`) clean on all three new scripts, including the
  `--select S` security ruleset.
- Backend: `python -m pytest` — 154 passed, 5 skipped against this machine's
  correct local Postgres role; the single failure seen with a different local
  role name is a pre-existing local-environment credential mismatch, not a
  Feature 007 regression (confirmed by isolating and passing that same test).
- Frontend: `npm ci`, Jest (20 suites / 103 tests passed), ESLint (no
  warnings/errors), `next build` (compiled, typechecked, all routes
  generated), and Prettier scoped to Feature 007's own files
  (`deploy-production.yml`, `vercel.json`) — all passing. Prettier flags ~79
  pre-existing, untouched frontend files locally because this worktree has
  `core.autocrlf=true`; that is a pre-existing local checkout condition, not
  a change made by this feature, and those files were left untouched.
- Independent review (T009) found one blocking defect (CLI passed an
  unsupported `region` argument into the deploy helper) and several
  high/medium findings (redirect-tolerant health checks, cancellation not
  triggering rollback, no main/CI recheck immediately before ECS mutation).
  All were fixed, covered by new regression tests, and reverified.
- Not available in this environment: Docker (Compose smoke test), AWS CLI/
  credentials, Vercel CLI login, and `actionlint`. These remain CI-only or
  manual-runbook validations and were not executed locally.