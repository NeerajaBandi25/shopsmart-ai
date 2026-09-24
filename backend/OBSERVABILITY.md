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
endpoint and are reset when a process restarts. In a multi-worker deployment,
each worker has independent counters; aggregation/export can be added later
without putting user IDs, request IDs, email addresses, or arbitrary paths in
metric labels.

Incoming `X-Request-ID` values are accepted only when they contain 1 to 64
ASCII letters, digits, dots, underscores, or hyphens and begin with an
alphanumeric character. Otherwise the application generates a UUID-based ID.