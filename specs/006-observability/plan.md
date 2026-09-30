# Implementation Plan: Operational Observability

## Summary

Complete the repository's documented observability direction by exposing the
already collected bounded backend metrics through a disabled-by-default,
Bearer-protected FastAPI endpoint and enriching unexpected-error logs with
safe request context. No external observability vendor or new package is
needed.

## Technical Context

- Runtime: FastAPI backend with existing request middleware, JSON logs,
  process-local metrics, security audit events, `/health`, and `/readiness`.
- Endpoint: `GET /api/v1/observability/metrics`, returning a typed snapshot of
  request counts, request duration aggregates, and allowlisted security event
  counts.
- Authorization/configuration: optional `OBSERVABILITY_METRICS_TOKEN`; blank
  disables the endpoint. Configured values must be at least 32 URL-safe
  characters and are compared in constant time.
- Logging: unexpected 500 records include method, route template, status, and
  exception type; exception message, traceback, credentials, and payloads are
  excluded.
- Authority: existing request middleware remains the source of aggregates;
  this feature only provides controlled read access and safe error context.

## Runtime Behavior

1. Every request continues to receive or propagate a validated request ID and
   produces the existing request completion log and bounded aggregate update.
2. Metrics reads return 404 when the dedicated token is unset or blank.
3. Configured metrics reads require a correct `Authorization: Bearer` header;
   invalid credentials return a generic 401 with a Bearer challenge.
4. Successful metrics reads return a validated JSON snapshot and never return
   identity or request-level information.
5. Unexpected server errors continue returning the existing generic 500
   envelope; logs add safe request context and omit exception contents.

## Security and Privacy

- Require a long, ASCII, whitespace-free secret; do not commit token values.
- Use constant-time byte comparison and never include authorization headers in
  logs or responses.
- Retain low-cardinality metric dimensions and process-local aggregates.
- Operators must provide the endpoint only on trusted networks and inject its
  token through deployment secret configuration.

## Performance and Failure Handling

- Snapshot copying uses the existing lock-protected in-memory counters; no
  database, Redis, network call, persistence, or background worker is added.
- Metrics collection is unchanged if no consumer is configured. The endpoint
  cannot make application startup, normal requests, health, or readiness
  depend on an external service.
- Metrics access failures are isolated to the observability endpoint.

## Configuration, Local Development, and Deployment

- Add optional `OBSERVABILITY_METRICS_TOKEN` to backend settings and Compose
  pass-through. Blank remains disabled for local and CI environments.
- Document setting a unique random secret and calling the versioned endpoint.
- Deployments that enable the endpoint must use their existing secret
  mechanism and network controls. No infrastructure, port, database, Redis,
  or frontend configuration changes are required.

## Testing and CI

- Unit-test optional, empty, valid, short, whitespace, and non-ASCII token
  configuration.
- Integration-test disabled behavior, missing/invalid credentials, successful
  metrics shape, bounded dimensions, and secret absence.
- Verify unexpected error logging and generic response preserve request ID
  context without including exception contents.
- Run full backend pytest, Ruff, pip-audit, frontend Jest/type/lint/format
  checks, Compose smoke validation where tooling permits, and diff/artifact
  audits. Existing CI remains the authoritative PR gate; no workflow change is
  required.
