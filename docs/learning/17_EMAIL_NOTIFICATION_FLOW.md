# Transactional email flow

## What

ShopSmart records transactional email intent in a database outbox. The package renders responsive HTML plus plain text, then a separate worker delivers due messages through an `EmailProvider` boundary. The shipped providers are a local metadata-only console sink and an in-memory capture sink for tests. No external sending adapter is installed yet.

## Why

Checkout and verified payment state changes must not depend on an email vendor being available. The caller adds an outbox row in its current database transaction and flushes it; the outbox row commits or rolls back with the commerce change. A separate worker handles delivery and bounded retries after commit.

## Flow

1. A payment/order service calls `queue_payment_notification(db, event, order, owner_email, request_id)` after the authoritative state transition.
2. The hook selects a semantic template and builds an explicit `OrderEmail` DTO from the persisted order snapshot.
3. `EmailOutboxService.queue_order_email` validates the destination, payload size and dedupe key, then flushes a unique outbox row without committing.
4. A private worker process runs `python -m src.emails.worker`, claims due rows with `FOR UPDATE SKIP LOCKED`, and leases each row before making the provider call.
5. A successful call marks the row sent. Transient failures retry with exponential backoff and a maximum of eight attempts; permanent failures stop immediately.

The worker is at-least-once: if a process crashes after a provider accepts an email but before the sent status commits, a later retry may send a duplicate. A provider with idempotency support can reduce this risk when a real adapter is added.

## Key files

- `backend/src/emails/templates/order.py`: semantic DTO and escaped HTML/plain-text order templates.
- `backend/src/emails/providers.py`: provider protocol, capture/console adapters, safe provider selection.
- `backend/src/emails/model.py`: outbox table mapping.
- `backend/src/emails/service.py`: transaction-aware queueing, claims, delivery, and retry policy.
- `backend/src/emails/worker.py`: private polling worker entry point.
- `backend/src/notifications/payment_events.py`: stable hook for verified payment events.

## Schema and setup

`NotificationOutbox`, `Payment`, and webhook dedupe records are created by Alembic revision `018_payment_email_outbox`. Apply migrations before enabling checkout/webhook processing. The revision creates the unique dedupe constraints, due-work index, and status/attempt checks used by the outbox worker.

Set `EMAIL_PROVIDER=console`, `APP_ENV=development`, and `PUBLIC_APP_URL=http://localhost:3000` for local metadata-only sink behavior. Set `EMAIL_PROVIDER=capture` in tests. Console/capture selection intentionally fails in production/staging. `resend`, `mailtrap`, and `smtp` selection currently fails closed even when credentials exist because no delivery adapter/dependency has been approved or installed; there is no fake-success path.

## Security

The renderer HTML-escapes customer and product values, accepts only an app-owned relative order path, then prefixes that path with configured `PUBLIC_APP_URL`. Destinations reject header-injection characters and are never emitted in application logs; only their domain is logged. The console adapter discards subject/body. Provider exceptions are normalized without logging SDK exception text, which can contain recipient or message data. The outbox payload contains the email destination and a minimal order snapshot, so database access and retention policy must treat it as personal data.

No card data, payment credentials, provider identifiers, or database IDs are included in messages. Customer-visible order references are short references derived by the payment event facade, not raw UUID strings.

## Failure handling

Permanent normalized errors mark the event failed. Transient errors retry at 1, 2, 4, 8, 16, 32, 64, then 128 minutes (capped at six hours) and stop after eight attempts. A worker crash during delivery leaves a two-minute lease; after it expires another worker can reclaim the row. Checkout does not call the worker or provider inline.

## How to test

From `backend`, run the focused package tests with the repository's test environment:

```powershell
python -m pytest tests/unit/emails
```

The tests use an isolated SQLite outbox table and capture/failure providers. They make no external network calls.

## How to debug

Search structured logs for `EMAIL_QUEUED`, `EMAIL_SEND_STARTED`, `EMAIL_SENT`, `EMAIL_RETRY_SCHEDULED`, or `EMAIL_FAILED`. These events avoid bodies and full addresses. Inspect the outbox row by dedupe key in a protected database session; review status, attempt count, next attempt, and normalized error code. Never paste payload JSON into public logs or tickets.

## Interview explanation

“The verified payment transaction writes a deduplicated notification intent into the same database transaction as the order state. A private worker claims it with a short lease, sends via an adapter, and applies finite transient retries. That keeps checkout independent from email uptime. The provider interface is ready, but only local sinks ship today; external delivery remains disabled until a real adapter, credentials, and migration are reviewed.”
