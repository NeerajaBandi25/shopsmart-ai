# Feature Specification: Operational Observability

**Feature Branch**: `feature/006-observability`

**Status**: Implemented

**Input**: Complete the observability requirements documented in `CLAUDE.md`,
the project constitution, and Paperclip backlog task T12 using the existing
FastAPI observability foundation.

## User Scenarios & Testing

### User Story 1 - Inspect Runtime Metrics (Priority: P1)

An operator can inspect bounded request, latency, and authentication audit
event aggregates for a backend process without exposing those metrics publicly
by default.

**Independent Test**: Integration tests verify disabled-by-default behavior,
Bearer authorization, bounded response shape, and that secret values do not
appear in the response.

### User Story 2 - Diagnose Unexpected Server Errors (Priority: P1)

An operator can correlate a generic client-facing 500 response with a request
ID, route template, method, status, and exception type in structured logs while
exception contents remain private.

**Independent Test**: Handler tests verify the safe structured context and
generic response while a sensitive exception message is absent from logs.

## Functional Requirements

- **FR-001**: Preserve existing structured request logs, request ID behavior,
  health/readiness endpoints, and authentication/authorization audit events.
- **FR-002**: Expose the existing process-local request counts, request duration
  aggregates, and allowlisted security event counters at a versioned backend
  endpoint only when explicitly enabled by configuration.
- **FR-003**: Protect the metrics endpoint with a dedicated Bearer token of at
  least 32 URL-safe characters; compare supplied credentials using
  a constant-time comparison. Missing configuration disables the endpoint.
- **FR-004**: Keep metric labels bounded and exclude request IDs, credentials,
  personal data, arbitrary paths, and request/response payloads.
- **FR-005**: Enrich unexpected 500 logs with safe method, route-template,
  status, and exception-type context. Do not log raw exception text or expose
  internal details in the HTTP response.
- **FR-006**: Make observability configuration optional for local and CI use;
  normal application startup and health/readiness must not depend on a metrics
  consumer or external monitoring service.
- **FR-007**: Do not change commerce, catalog, authentication/session, database,
  Redis, or frontend/BFF behavior beyond observing existing requests.

## Edge Cases

- An unset or blank metrics token returns 404 and does not reveal that metrics
  are available.
- Missing, malformed, or incorrect Bearer credentials return 401 without
  logging the credential.
- Non-ASCII or too-short configured tokens fail configuration validation.
- Counters remain process-local and reset on restart; multiple workers are not
  silently represented as one global total.
- Client-facing error responses stay generic even when the failure is
  unexpected; the request ID remains available for correlation.

## Out of Scope

Third-party monitoring vendors, Prometheus exporters, distributed metric
aggregation, persistent observability storage, AI metrics before AI runtime
paths exist, frontend telemetry, tracing infrastructure, and changes to
business/API contracts unrelated to observability.

## Acceptance Criteria

1. Operators can securely query bounded in-process metrics when configured.
2. Metrics remain disabled by default and no external dependency is required.
3. Unexpected server errors can be correlated from safe logs without exposing
   exception contents.
4. Existing health, readiness, request IDs, request metrics, and auth audit
   coverage continue to pass.
5. Focused and full backend validation, Compose smoke checks where available,
   and diff/scope audits pass.
