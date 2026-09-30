# Feature Specification: CI/CD and AWS Deployment

**Feature Branch**: `feature/007-cicd-aws`

**Status**: In progress

**Input**: Complete the repository's CI/CD and AWS deployment capabilities
documented in `CLAUDE.md` and the project constitution, while preserving the
current application behavior and the four existing CI checks.

## Roadmap Scope and Existing Baseline

The checked-in roadmap summary names GitHub Actions and AWS SQS, ECS, RDS,
Vercel, and CloudWatch. Its production path is GitHub, CI, tests/type checks/build,
container image, deployment, health checks, and logs/metrics/error monitoring.
The project rules require deployment from a known-good commit, environment-based
configuration, no committed cloud credentials, and no assumed AWS free-tier
pricing. SQS is described only as a future event path, when order events are
introduced.

At the Feature 007 baseline, GitHub Actions already has four CI jobs for backend
tests, backend security gates, frontend tests/build/lint/format, and Docker
Compose smoke validation. Backend and frontend Dockerfiles, Compose, Alembic
migrations, health/readiness endpoints, and Feature 006 observability are also
present. No AWS deployment workflow or AWS infrastructure configuration is
present. The source roadmap names services but does not define account IDs,
resource names, a provisioning tool, or environment topology.

For this feature, use the user-approved existing-infrastructure boundary: deploy
the backend container to a pre-provisioned ECS Fargate service using its existing
ECR repository, RDS PostgreSQL connection secret, and CloudWatch Logs
configuration; deploy the frontend to its existing Vercel project. Do not create
or modify cloud infrastructure in this implementation.

## User Scenarios and Testing

### User Story 1 - Keep Pull Requests Verifiable (Priority: P1)

As a contributor, I need every pull request to continue running the established
backend, security, frontend, and Compose checks so that broken or unsafe changes
cannot become the basis of a release.

**Independent Test**: Verify the four existing CI job names remain present and
their tests, security scans, builds, lint, formatting, migrations, and Compose
smoke behavior remain enabled.

### User Story 2 - Deploy an Approved Main Commit (Priority: P1)

As an operator, I need to start production deployment only for the latest
`main` commit after its four CI checks succeed and a human approves the release.

**Independent Test**: Preflight tests reject a non-main ref, stale commit, a
missing check, an in-progress check, or a failed latest attempt before any AWS
credentials are requested. Review the protected-environment and OIDC workflow
configuration without contacting AWS or Vercel.

### User Story 3 - Verify or Recover a Deployment (Priority: P1)

As an operator, I need migrations, ECS health, backend readiness, and frontend
health verified during release, with the previous service revision restored on
deployment failure.

**Independent Test**: Unit tests exercise ECS task-definition validation and
service rollback behavior using mocked AWS CLI responses; workflow review
confirms Vercel health failure invokes Vercel rollback and prevents a partial
release from being silently reported as successful.

## Functional Requirements

- **FR-001**: Preserve the four existing required CI checks and their check-run
  names: `Backend tests (pytest, PostgreSQL)`,
  `Backend security gates (Ruff, pip-audit)`,
  `Frontend tests (jest, lint, prettier)`, and `Docker Compose smoke test`.
  Do not remove, bypass, weaken, or rename a check.
- **FR-002**: Add a manually dispatched production workflow. It must reject
  dispatches not run from `main`, require the run SHA to equal the current
  `origin/main` SHA, and require the latest attempt of every FR-001 check on
  that exact SHA to have completed successfully. Recheck after the migration
  task and immediately before ECS service mutation, and again before Vercel
  production promotion.
- **FR-003**: Gate production actions behind a GitHub environment approval
  configured for trusted human reviewers. CI and preflight jobs must not receive
  AWS or Vercel deployment credentials.
- **FR-004**: Build the backend image from the verified commit, push it to the
  existing ECR repository, and deploy its immutable image digest to the
  pre-existing ECS Fargate service. Preserve the task definition's unrelated
  runtime settings, IAM roles, secret references, and logging configuration.
- **FR-005**: Run checked-in Alembic migrations as a one-off Fargate task before
  changing the ECS service. If migration fails, leave the service on its prior
  task definition. Do not attempt an automatic destructive database downgrade.
- **FR-006**: Require the existing ECS task definition to reference `DATABASE_URL`
  and `SECRET_KEY` through ECS secret references and to send container logs to
  CloudWatch Logs. Do not place these secret values in images, workflow files,
  GitHub logs, or task-definition environment literals.
- **FR-007**: Authenticate GitHub Actions to AWS using short-lived OIDC
  credentials with repository/environment-scoped trust. Scope IAM permissions
  to the existing image repository, ECS service/task definition, and the task
  execution/task roles that must be passed. Do not configure long-lived AWS
  access keys or grant the workflow database/secret-value read access.
- **FR-008**: Build and deploy the frontend to the existing Vercel production
  project using an exact pinned Vercel CLI version and a GitHub Environment
  secret for its scoped token. Prevent duplicate Vercel Git-triggered production
  deployments. Read production frontend/backend URLs and settings from Vercel
  environment configuration rather than hard-coding endpoints.
- **FR-009**: Verify ECS service stability and the configured backend `/readiness`
  URL, and verify the Vercel deployment and configured production URL before
  reporting success. Restore the previous ECS task definition if its rollout or
  readiness check fails. Roll back the Vercel production pointer if its health
  check fails; restore ECS after a frontend failure only when Vercel rollback is
  confirmed. If Vercel recovery is uncertain after cancellation or failure,
  retain the matching backend release and fail for operator recovery rather than
  creating a frontend/backend version mismatch.
- **FR-010**: Keep local development on the existing Docker Compose workflow.
  Do not change authentication/session, commerce/catalog/cart/order, Redis,
  database, or observability application contracts for this feature.
- **FR-011**: Use only pre-provisioned resources. Do not deploy to a live account,
  create paid resources, add account IDs/private endpoints, or add infrastructure
  as code not specified by repository sources.

## Edge Cases

- If any required check is absent, pending, neutral, cancelled, timed out, or
  failed on the latest attempt, preflight fails closed.
- If `main` advances after the workflow dispatch, the old SHA is rejected and
  must not be deployed. The workflow rechecks after migrations and before ECS
  mutation, then before Vercel promotion. Release concurrency does not lock
  merges to `main`; operators should not merge or manually deploy during a
  production release.
- If ECS, ECR, a Fargate network configuration, task roles, secret references,
  or CloudWatch logging are not preconfigured, deployment fails before service
  update and reports the missing prerequisite without printing secret values.
- If a migration fails, the ECS service remains on its previous revision; the
  database is not automatically downgraded.
- If ECS rollout or readiness fails, restore the previous task definition and
  wait for it to become stable; report rollback failure for manual recovery.
- If Vercel deployment or post-deploy health validation fails, restore the
  previous Vercel production deployment and roll back the ECS service only
  after Vercel rollback is confirmed. If a cancellation or rollback failure
  leaves the Vercel state uncertain, fail the workflow and retain the matching
  ECS revision for manual recovery.
- If a workflow is cancelled after a production mutation, attempt compensation:
  Vercel rollback after promotion and ECS rollback when its recorded task
  revisions are available and frontend recovery is confirmed.
- Database schema changes must be backward-compatible with the prior
  application revision; this feature does not automate database rollback.

## Out of Scope

Provisioning or changing AWS accounts/resources; Terraform, CloudFormation,
Kubernetes, or another infrastructure-as-code system; adding an SQS consumer
before the order-event feature exists; creating staging environments or
production resources; running a production deployment during this work; changing
the four required CI checks; and unrelated application, dependency, auth,
commerce, Redis, or observability changes.

## Success Criteria

- **SC-001**: All four existing required check-run names remain unchanged and
  continue to execute their existing quality gates on pull requests.
- **SC-002**: Automated preflight tests prove that a non-main, stale, missing,
  incomplete, or unsuccessful required check blocks deployment before AWS
  authentication.
- **SC-003**: No AWS access key, Vercel token, database credential, account ID,
  or private service endpoint is committed; the AWS workflow uses OIDC and the
  Vercel token is referenced only as a protected environment secret.
- **SC-004**: The documented deployment flow builds an image identified by an
  immutable digest, applies migrations before service rollout, and validates
  both backend readiness and frontend availability.
- **SC-005**: Automated failure-path tests prove a failed ECS rollout restores
  the previous task definition; Vercel health failure invokes rollback and
  causes backend rollback rather than a successful release result.
- **SC-006**: The feature requires no new cloud resource, paid AWS operation,
  application API change, or local Compose workflow change.