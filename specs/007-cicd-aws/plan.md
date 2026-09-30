# Implementation Plan: CI/CD and AWS Deployment

## Summary

Retain the existing pull-request quality gates and add a manually dispatched,
human-approved deployment path for a known-good `main` commit. Deploy the
backend to pre-provisioned ECS Fargate/ECR with existing RDS and CloudWatch Logs
configuration, then deploy the frontend to its existing Vercel project. Do not
provision infrastructure or change application behavior.

## Source and Baseline

- `CLAUDE.md` names GitHub Actions, Docker, ECS, RDS, Vercel, CloudWatch, and a
  future SQS event path. It requires known-good deployments, environment-based
  secrets, health checks, logs/metrics, and verification of current cloud costs.
- `.specify/memory/constitution.md` requires fail-fast PR gates for backend and
  frontend tests/build/lint/type/format and migration validation; secrets must
  not be committed; deployments must be traceable and verified.
- `PAPERCLIP_BACKLOG.md` T3/T4 calls for PR CI and security gates; T9's
  containerization/Compose and T12's observability foundation are already
  present in the Feature 007 base.
- `.github/workflows/test.yml` already defines the four required CI jobs and
  PostgreSQL/Alembic, security, frontend build, and Compose smoke validation.
  Keep all four job names and gates unchanged; only add tests for the new
  deployment helpers and YAML syntax validation within existing jobs.
- `backend/Dockerfile`, `frontend/Dockerfile`, Compose, `/health`, `/readiness`,
  and Feature 006 metrics/logging are already implemented. No AWS account or
  infrastructure identifiers are present.
- The original roadmap PDF and an AWS deployment target configuration are not
  present in this worktree. `CLAUDE.md` is the available checked-in roadmap
  summary; exact AWS settings are supplied through protected GitHub/Vercel
  environment configuration.

## Runtime and Release Architecture

### Pull Request CI

The four existing `CI` check-run names remain unchanged:

1. `Backend tests (pytest, PostgreSQL)`
2. `Backend security gates (Ruff, pip-audit)`
3. `Frontend tests (jest, lint, prettier)`
4. `Docker Compose smoke test`

The security job executes standard-library self-tests for deployment preflight
and ECS deployment helpers. The frontend job runs Prettier against the new
workflow and Vercel JSON configuration so malformed configuration fails within
an existing required check. No deployment credentials are used by CI.

### Production Dispatch

`.github/workflows/deploy-production.yml` runs only on `workflow_dispatch`.
Before any environment approval or cloud authentication, a read-only preflight
script verifies that the workflow ref is `main`, the SHA is still the current
remote `main` head, and the latest attempt for each exact required check name on
that SHA completed with `success`. A missing, pending, cancelled, neutral, or
failed check fails closed. The preflight job uses only read permissions.

After preflight, a `release-approval` GitHub Environment job pauses for an
explicit human reviewer. The `production` Environment holds deployment
variables/secrets and must be restricted to the `main` branch. AWS/Vercel jobs
depend on successful preflight and the approval job; PRs and forks cannot reach
them.

### Backend: ECR, ECS Fargate, RDS, CloudWatch

The AWS job has only `contents: read` and `id-token: write`. It assumes the
configured deployment role through GitHub OIDC, with trust scoped to
`repo:NeerajaBandi25/shopsmart-ai:environment:production` and audience
`sts.amazonaws.com`. It builds `backend/Dockerfile`, pushes a run-unique tag to
the existing ECR repository, resolves the image digest, and deploys by digest.

The deploy helper reads the existing service and task definition, then refuses
to proceed unless the target is Fargate/`awsvpc`, the requested container exists,
`DATABASE_URL` and `SECRET_KEY` use ECS secret references, and the container
already uses the `awslogs` driver. It changes only that container's image and
preserves the task's environment, secret references, roles, network settings,
and logging. The deployment role does not read secret values or call RDS APIs.

Before updating the service, the helper starts one Fargate task with the new image
and overrides its command with `alembic upgrade head`, using the service's
existing subnets and security groups. It waits for task completion and requires
exit code zero. It then updates the ECS service, waits for stability, and polls
the configured backend `/readiness` URL. After migrations complete, it rechecks
the dispatched SHA against current `main` and the latest required CI attempt
immediately before ECS service mutation. It then updates the ECS service, waits
for stability, and polls `/readiness` without following redirects. Any failure
after service update restores the old task definition and waits for it to
stabilize. A migration or release-gate failure does not update the service, and
no automatic database downgrade is attempted.

The task definition's existing execution role remains responsible for pulling
images, reading its configured runtime secret references, and sending logs to
CloudWatch. The deployment role requires only repository-scoped ECR push/read,
scoped ECS run/describe/update/register actions, and `iam:PassRole` limited to
the existing task roles and `ecs-tasks.amazonaws.com`. Exact ARNs and region are
environment configuration, not repository content.

### Frontend: Vercel

The frontend job has no AWS OIDC permission. It installs the exact Vercel CLI
version `61.1.0`, writes the configured organization/project IDs to ignored
`.vercel/project.json`, pulls production settings, and builds with the Vercel
Build Output API. `frontend/vercel.json` disables Vercel's automatic Git
deployments to prevent a second production deployment. The CLI deploys the
prebuilt output with `--prod --skip-domain`, checks its immutable deployment URL,
promotes it, and requires HTTP 200 from the configured production URL without
following redirects. A failed or cancelled promotion attempts to restore the
previous Vercel production pointer and verifies HTTP 200. The Vercel token is a
project-scoped GitHub Environment secret; frontend/API URLs and other production
settings remain in Vercel's production environment.

If the backend job is cancelled after recording its task revisions, a separate
OIDC-only compensation job restores the previous task definition. If the
frontend fails before promotion, or its Vercel rollback is confirmed, the same
job restores ECS. If Vercel rollback is uncertain, ECS remains on the matching
release revision and the workflow fails for operator recovery rather than
creating a version mismatch. Any rollback failure requires operator recovery.
Database migrations are not downgraded; future migrations must be
backward-compatible with the previous application revision.

The release concurrency group serializes this workflow but does not prevent
merges to `main` or unrelated manual deployments. The helper performs a final
main/CI check after migration, and the frontend repeats it before promotion; do
not merge or deploy another release while this workflow is in progress.

## Environment and Secret Configuration

Configure a GitHub Environment named `release-approval` with required human
reviewers and `main` as its allowed deployment branch. Configure a GitHub
Environment named `production`, restricted to `main`, with these non-secret
variables:

- `AWS_REGION`, `AWS_ROLE_ARN`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`,
  `ECS_CONTAINER_NAME`, `BACKEND_READINESS_URL`
- `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_PRODUCTION_URL`

Store only `VERCEL_TOKEN` as a GitHub Environment secret. Configure the Vercel
project's production `API_INTERNAL_URL` and `NEXT_PUBLIC_API_URL` there. Existing
ECS task-definition secret references supply `DATABASE_URL` and `SECRET_KEY` to
the application. Never put those values in GitHub Actions variables, image
build arguments, the Docker image, or workflow output.

The AWS role's trust policy must use the repository/environment OIDC subject and
the `sts.amazonaws.com` audience. Limit `iam:PassRole` to the existing ECS task
execution/task roles; do not grant AWS user keys, broad administrator access,
RDS modification, or Secrets Manager value-read to the GitHub deployment role.

## Observability, Failure, and Rollback

- The deployment script writes only commit, image digest, task definition ARN,
  and outcome metadata to workflow output. It never prints secret values or
  runtime environment values.
- ECS task logs continue to use the existing CloudWatch Logs configuration;
  the existing Feature 006 request IDs and metrics are not changed.
- A migration task failure prevents ECS service update. An ECS rollout/readiness
  failure restores the previous task definition. A frontend failure restores
  Vercel and triggers ECS rollback. Any rollback failure is surfaced as failure.
- RDS data/schema is never reverted automatically. Operators must use
  backward-compatible expand/contract migrations and follow the runbook for
  manual recovery.
- Local development remains Docker Compose plus the existing environment files;
  deployment credentials are not needed locally.

## Cost and Environment Separation

Local/test and production remain separate: CI uses ephemeral PostgreSQL and
non-production dummy test values; production values are held in GitHub/Vercel
environments and ECS secret references. No staging environment is invented.
This change creates no AWS resources, but a real release uses existing Fargate,
ECR, CloudWatch Logs, GitHub Actions, and Vercel capacity. Review current AWS and
Vercel pricing and account quotas before configuring or dispatching production;
do not rely on a fixed free-tier assumption.

## Testing and Validation

- Self-test latest-check selection, exact SHA/ref checks, and fail-closed CI
  status handling without GitHub network access.
- Self-test task-definition secret/log/Fargate validation, image-only mutation,
  migration override, CLI entry-point wiring, the post-migration release gate,
  redirect rejection, and ECS rollback ordering with mocked AWS CLI responses.
- Contract-test HTTP 200 requirements and failure/cancellation compensation in
  the production workflow.
- Parse and format the deployment workflow and Vercel JSON in an existing CI
  job; run actionlint if available locally/CI without changing required check
  names.
- Run backend pytest, Ruff, pip-audit; frontend Jest, TypeScript/build, lint,
  Prettier; Compose smoke; workflow/static checks; and final diff/security/
  generated-file audits.
- Do not call AWS/Vercel or create cloud resources during tests. Local Docker,
  AWS credentials/account configuration, Vercel credentials, and actionlint may
  be unavailable; record blocked validation separately from passed checks.

## Scope Guardrails

No changes to application route/service/schema behavior, auth/session flows,
catalog/cart/order logic, migrations, Redis behavior, Feature 006 behavior, or
CI check identities. No SQS consumer until an order-event feature requires it.
No infrastructure provisioning, Terraform/Kubernetes, hard-coded cloud IDs,
secrets, or production endpoint values.