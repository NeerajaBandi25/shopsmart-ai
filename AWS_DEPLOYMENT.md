# Production Deployment Runbook

This repository provides a manually dispatched release workflow for an already
configured ShopSmart production stack. It does not create AWS or Vercel
resources, and no production release was performed as part of Feature 007.

The release uses the exact current `main` commit only. It checks all four
required CI jobs, waits for a protected human approval, runs an Alembic Fargate
task, updates the existing ECS service by immutable ECR digest, verifies backend
readiness, then validates and promotes a prebuilt Vercel deployment. A failed
frontend release triggers backend rollback after Vercel recovery is confirmed.
If Vercel recovery is uncertain after cancellation or failure, the workflow
retains the matching backend revision and fails for operator recovery. Database
migrations are never rolled back automatically.

## GitHub Environments

Configure these environments in repository settings before enabling a
production release:

- `release-approval`: restrict deployments to `main`; require named, trusted
  human reviewers; enable prevention of self-review where available. Do not
  store deployment secrets in this environment.
- `production`: restrict deployments to `main`. Store the variables and secret
  below here so they are unavailable to pull-request CI and the approval job.

Required `production` variables:

| Variable | Required value |
| --- | --- |
| `AWS_REGION` | Region containing the existing ECR repository and ECS service |
| `AWS_ROLE_ARN` | ARN of the narrowly scoped GitHub OIDC deployment role |
| `ECR_REPOSITORY` | Name of the existing backend ECR repository |
| `ECS_CLUSTER` | Name or ARN of the existing ECS cluster |
| `ECS_SERVICE` | Name or ARN of the existing backend ECS service |
| `ECS_CONTAINER_NAME` | Backend container name in the active task definition |
| `BACKEND_READINESS_URL` | HTTPS URL ending in `/readiness`, reachable by the GitHub-hosted runner without URL credentials |
| `VERCEL_ORG_ID` | Existing Vercel team or organization ID |
| `VERCEL_PROJECT_ID` | Existing Vercel project ID |
| `VERCEL_PRODUCTION_URL` | HTTPS production origin, without a path, used for post-promotion health checks |

Required `production` secret:

- `VERCEL_TOKEN`: token authorized to deploy and promote this Vercel project.
  Limit its scope and lifetime as supported by the Vercel account, rotate it
  regularly, and never pass it as a command-line argument.

Configure `API_INTERNAL_URL` and `NEXT_PUBLIC_API_URL` in the Vercel project's
Production environment. The workflow retrieves those values using
`vercel pull --environment=production` before its production build. The
server-only `API_INTERNAL_URL` must be reachable from Vercel's server runtime;
`NEXT_PUBLIC_API_URL` is embedded in browser code and must be an HTTPS URL that
browsers can reach. Do not put database credentials or signing secrets in
frontend build variables.

The Vercel project must not have another Git integration or deploy hook that
bypasses the versioned `frontend/vercel.json` setting. That setting disables
automatic Git deployments so this workflow is the single production publisher.

## Existing AWS Resources

The deployment assumes all of the following already exist and are operational:

- An ECR repository in `AWS_REGION`, with repository policy permitting the
  deployment role to push images. Run tags include the commit SHA and GitHub
  run/attempt IDs; deployments use the digest returned by ECR.
- An active ECS Fargate service in the named cluster. Its task definition uses
  `awsvpc`, supports Fargate, has the backend container name configured above,
  and has its existing task execution role and task role.
- The backend container has exactly one ECS secret reference named
  `DATABASE_URL` and one named `SECRET_KEY`. Neither may be set as a plaintext
  container environment variable. The existing task execution role, not the
  GitHub deployment role, must be able to retrieve those configured secret
  references. Grant KMS decrypt only where the configured secret requires it.
- The backend container uses the `awslogs` driver and an existing CloudWatch
  Logs group. Retention, encryption, and access controls for that group are
  managed outside this repository.
- The ECS service has Fargate subnets, security groups, and either the `FARGATE`
  launch type or a Fargate capacity-provider strategy. The same service network
  is reused for the migration task. It must allow the task to reach PostgreSQL,
  retrieve its ECS-injected secrets, pull from ECR, and send logs using the
  existing network design.
- The migration task's database role can apply the checked-in Alembic
  migrations. Migrations must be backward-compatible with the previous
  application revision because a deployment rollback never downgrades the
  schema.
- `BACKEND_READINESS_URL` returns HTTP 200 only when the backend is ready. The
  current `/readiness` handler checks its database connection. Redirects are
  rejected rather than followed. It must be
  reachable from the GitHub-hosted runner without embedding credentials in the
  URL. A private-only endpoint requires a separately configured runner/network
  path; this feature does not provision a self-hosted runner.
- Vercel's server runtime can reach the configured backend URL. A backend
  endpoint that is private to an unrelated VPC is not reachable by Vercel unless
  that connectivity already exists.

The workflow refuses to register an image deployment if the active ECS task
definition does not meet the Fargate, secret-reference, or CloudWatch logging
requirements. It does not create a cluster, service, task role, secret, log
group, VPC resource, RDS instance, or ECR repository.

## AWS OIDC and IAM

Create or reuse the GitHub Actions OIDC provider for
`https://token.actions.githubusercontent.com`. The AWS role trust policy must
require audience `sts.amazonaws.com` and the exact repository/environment
subject:

```text
repo:NeerajaBandi25/shopsmart-ai:environment:production
```

Do not trust a wildcard repository, branch, tag, or environment subject. The
workflow uses `id-token: write` only in the ECS deployment and rollback jobs;
there are no long-lived AWS access keys in GitHub.

Limit the deployment role to the resources and actions required by this
workflow:

| AWS service | Permitted actions and scope |
| --- | --- |
| ECR | `ecr:GetAuthorizationToken` (AWS requires `Resource: "*"`); `ecr:DescribeRepositories`, `ecr:DescribeImages`, `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, and `ecr:PutImage`, scoped to the existing image repository where supported |
| ECS | `ecs:DescribeServices`, `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`, `ecs:TagResource`, `ecs:RunTask`, `ecs:DescribeTasks`, `ecs:StopTask`, and `ecs:UpdateService`, scoped to the existing cluster, service, task-definition family, and tasks where supported |
| IAM | `iam:PassRole` only for the existing task execution role and task role, with `iam:PassedToService` restricted to `ecs-tasks.amazonaws.com` |

Use AWS's current service-authorization reference to confirm resource-level
support for each action in the target account. Where AWS requires a wildcard
resource, grant only that action and constrain it with supported condition
keys. `RegisterTaskDefinition` must not grant IAM role creation or role-policy
changes; `iam:PassRole` remains limited to the pre-existing ECS task roles.

The GitHub deployment role must not have permission to read Secrets Manager or
SSM parameter values, access RDS data, modify RDS, create infrastructure, change
IAM policies, or create ECS clusters/services. The ECS task execution role is
separate and handles image pulls, configured secret injection, and CloudWatch
logging. The application task role should retain only the permissions the
application actually needs.

## Release Procedure

1. Merge the reviewed feature/change to `main` through the repository's normal
   human review and required CI checks.
2. In GitHub Actions, select **Production deployment**, choose the current
   `main` branch, and dispatch the workflow.
3. Confirm the preflight identifies the dispatched SHA as current `main` and
   that the latest attempt of each of the four required CI jobs is successful.
  The workflow checks again after approval and before AWS authentication, after
  migrations immediately before ECS service mutation, and before Vercel
  promotion; a newly observed `main` commit blocks the stale release.
4. An authorized reviewer approves the `release-approval` environment job.
5. Monitor ECR image publication, the one-off Alembic task, ECS service
   stability/readiness, Vercel deployment/health, and promotion. The workflow
   reports success only after both backend and frontend health checks succeed.

Required CI check names are preserved exactly:

- `Backend tests (pytest, PostgreSQL)`
- `Backend security gates (Ruff, pip-audit)`
- `Frontend tests (jest, lint, prettier)`
- `Docker Compose smoke test`

The release workflow is `workflow_dispatch` only. It does not deploy on push or
PR events. Do not add a bypass for a missing, pending, stale, cancelled,
neutral, timed-out, or unsuccessful check.

## Failure and Recovery

- **Preflight or approval failure**: no production credentials are requested.
  Resolve the gate and dispatch again from the current `main` commit.
- **Image publication failure**: no ECS service change or migration occurs.
  Review the ECR/CloudTrail error, IAM scope, and repository configuration.
- **Migration failure**: the ECS service remains on its previous task
  definition. The migration task is stopped if its waiter fails. Inspect its
  CloudWatch logs and database state before retrying; never assume a partially
  applied migration was reverted.
- **ECS rollout or readiness failure**: the helper restores the previous task
  definition, waits for ECS stability, and checks backend readiness. A rollback
  or recovery-check failure is reported explicitly and requires operator
  intervention.
- **Vercel failure before promotion**: the production alias was not changed;
  the workflow rolls the backend back because the frontend release did not
  complete. A failed or cancelled promotion attempts Vercel rollback and
  verifies HTTP 200 before restoring the backend revision. If Vercel rollback
  cannot be confirmed, the workflow leaves the backend on the matching release
  revision and fails for operator recovery.
- **Workflow cancellation**: if backend task revisions were recorded, the
  compensation job checks the ECS service and restores the prior task definition
  when needed. If Vercel promotion had started, its job attempts rollback; ECS
  rollback waits for that recovery to be confirmed.
- **Rollback failure**: inspect the failed workflow step, ECS service events,
  CloudWatch task logs, and Vercel deployment activity. Restore the last known
  good application revision manually only after confirming database
  compatibility. The workflow never runs `alembic downgrade`.

GitHub workflow concurrency prevents two of these releases from running at the
same time, but it does not lock `main` or block unrelated manual deployments.
Avoid merging a new commit to `main` or making a separate production deployment
while a workflow release is in progress, especially during Vercel rollback.

## Local Validation and Cost

Deployment helper tests are offline and mock AWS CLI responses. CI parses and
checks the workflow and Vercel JSON without deployment credentials. No AWS,
Vercel, Docker, or paid service is contacted by those tests. Local development
continues to use the existing Docker Compose setup.

A real release consumes GitHub Actions, ECR, Fargate, CloudWatch Logs, and
Vercel capacity. Check current account pricing, quotas, and retention policies
before configuring or dispatching; no fixed free-tier assumption is made here.
