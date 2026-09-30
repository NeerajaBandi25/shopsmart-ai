# Backend Observability

The backend emits compact JSON log records to standard output with a UTC
timestamp, level, message, logger name, request ID, and allowlisted context.
HTTP request completion records include the normalized method, route template,
status, and duration. Security events include login success/failure, rate
limiting, registration, logout, password changes, authentication failures,
and authorization denials. Passwords, email addresses, cookies, session IDs,
CSRF tokens, and exception messages are not included in these events.

The existing `login_attempts` table remains the persistent login audit record;
observability does not add duplicate rows or a new migration.

Request metrics are maintained in process memory: counts by bounded HTTP method
and status class, request duration count/total/max, and counts for a fixed set
of security event names. They are intentionally not exposed through an HTTP
endpoint unless an operator configures `OBSERVABILITY_METRICS_TOKEN`. With a
unique random token of at least 32 URL-safe characters configured,
`GET /api/v1/observability/metrics` returns the existing aggregate snapshot and
requires `Authorization: Bearer <token>`. Without a token the endpoint returns
404; a missing or invalid token returns 401. The token is never logged or
included in metric output. Keep the endpoint behind trusted network controls
and provide the token through the deployment secret mechanism, not source
control.

Metrics are reset when a process restarts. In a multi-worker deployment, each
worker has independent counters; deploy a separate aggregation/export solution
only when required, without putting user IDs, request IDs, email addresses, or
arbitrary paths in metric labels. Unexpected 500 logs include the exception
type and safe request context, but omit exception messages and tracebacks to
avoid leaking sensitive values. The corresponding request completion log
records route template, status, duration, and request ID.

Incoming `X-Request-ID` values are accepted only when they contain 1 to 64
ASCII letters, digits, dots, underscores, or hyphens and begin with an
alphanumeric character. Otherwise the application generates a UUID-based ID.

For local Compose development, leave `OBSERVABILITY_METRICS_TOKEN` blank to
keep the endpoint disabled, or supply a unique random token in the root `.env`
file and call the endpoint with its Bearer authorization header. No database,
Redis, or third-party monitoring service is required for metrics collection.
