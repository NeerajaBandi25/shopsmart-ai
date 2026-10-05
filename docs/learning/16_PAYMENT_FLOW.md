# 16. Sandbox payment flow

## What

ShopSmart creates a payment record for an authoritative order and redirects the shopper to Stripe-hosted Checkout in **test mode only**. ShopSmart never receives or stores a card number or CVC. Orders and payments have separate statuses: checkout starts an order at `pending_payment` and payment at `requires_action`; only a verified provider event can move them to `paid` / `succeeded`.

## Why

The browser redirect is controlled by the shopper, so it cannot prove that money was received. A signed provider webhook plus a server-side comparison of order, amount, currency, and Checkout session protects the order from spoofed success messages. The provider boundary keeps Stripe-specific status names out of order services and leaves room for a second provider.

## Flow

1. The authenticated checkout API checks that valid `sk_test_` and `whsec_` credentials and safe success/cancel return URLs are configured before it reserves inventory.
2. Existing checkout logic locks products, rechecks stock and promotion rules, snapshots prices, rejects totals outside Stripe's INR range (₹0.50 through ₹999,999.99), and creates one idempotent `pending_payment` order.
3. A unique payment row is created for that order. The stable provider idempotency key is based on order ID and retry generation; a lost network response can be retried without making another charge session.
4. The API returns a hosted `checkout_url` and safe order/payment fields. A success query string is only navigation; it does not change backend state.
5. Stripe signs its webhook. The adapter checks the HMAC signature, five-minute timestamp window, and `livemode=false`, parses only supported Checkout events, and normalizes their outcome. The return URL carries an order reference so the UI can poll the authenticated order API; query values never set payment state.
6. The payment service checks session ID, order ID, amount, and currency, then records the event ID and transitions payment/order state in one transaction. A repeated event is acknowledged without repeating the transition. Expired Checkout cancels the order and restores inventory exactly once; failed payments remain retryable against the same order until the bounded retry budget is exhausted, when the order closes and stock is restored.
7. On success, the same transaction subtracts the purchased quantities from the shopper's current cart, preserving additional units added after checkout; the optional public notification hook queues order confirmation and receipt messages without allowing email-provider failure to undo payment.

## Key files

- `backend/src/services/payment_provider.py`: provider protocol, Stripe test adapter, signature and status normalization.
- `backend/src/services/payment_service.py`: payment row/session idempotency and verified transactional transitions.
- `backend/src/services/payment_reservation_worker.py`: bounded cleanup loop for old pending orders that never obtained a provider session.
- `backend/src/models/payment.py`: normalized payment and webhook event records.
- `backend/src/api/v1/order_routes.py`: authenticated checkout, shopper-owned order detail, same-order retry, and webhook endpoints.
- `backend/src/notifications/payment_events.py`: public notification integration hook.

## Security

Only explicit `PAYMENT_PROVIDER=stripe`, `PAYMENT_MODE=test`, `sk_test_`, and `whsec_` settings enable the Stripe adapter. Missing or live credentials make checkout return a safe 503 while catalog browsing stays available. Remote return URLs must use HTTPS and match an allowed frontend CORS origin; localhost HTTP is allowed only in local/test environments. Signed webhook events must explicitly set `livemode=false`. No Stripe SDK or card data enters domain code. Webhook bodies are capped at 1 MB, signatures are compared in constant time, and stale signed events are rejected. The webhook, not the redirect, is the sole payment authority. Read/retry endpoints are shopper-scoped and do not expose provider IDs or hosted-session IDs.

## Failure handling

If the hosted-session request has an ambiguous network failure, the pending order and its single payment row remain committed so the same checkout idempotency key can retry with the same provider idempotency key; releasing inventory could race a remote session that was created despite a lost response. Stripe Checkout sessions are explicitly set to expire after two hours. If no session ID was saved after three hours from the last attempt, the in-process reservation sweeper cancels the order and restores its stock; the safety window exceeds the remote session lifetime. Linked sessions are also checked against Stripe after two hours and ten minutes. An authenticated retrieval that reports the session expired or paid is passed through the same amount/order/session validation and transactional transition as a webhook; an open or unavailable session never releases inventory. Static credentials and return URLs are preflighted before reservation, and out-of-range totals are rejected before order creation. A definitive provider rejection closes the order and releases its reservation transactionally. A verified payment failure remains retryable through the owner-scoped action on the same order, keeping its inventory reservation and cart intact for up to 24 hours. The backend allows four retries after the initial session and then closes the order on the final verified failure. A stale verified failure that the shopper never retries is closed after 24 hours by the same worker, restoring stock transactionally. A verified Checkout expiration cancels the order and releases its reserved quantities in the same transaction; duplicate/delayed events cannot release stock twice. Terminal cancellation clears the browser key so a fresh checkout can create a new order. On payment success, only the quantity bought is removed from the cart, preserving extra quantities added while payment was in progress. A new provider attempt after a failed payment uses a higher stable idempotency generation while keeping the same payment record.

## How to test

Use Stripe test keys and a local webhook forwarder only when manually exercising the adapter. Automated tests inject an explicit fake provider and never call Stripe. Test coverage includes signature tampering, stale signatures, unknown event types, live-key refusal, normalized success/failure/cancel states, session replay, duplicate webhook delivery, and transactionally paid order state.

## How to debug

Search structured events `PAYMENT_SESSION_CREATED`, `PAYMENT_SESSION_FAILED`, `PAYMENT_WEBHOOK_VERIFIED`, `PAYMENT_WEBHOOK_IGNORED`, `PAYMENT_WEBHOOK_DUPLICATE`, `PAYMENT_WEBHOOK_PROCESSED`, and `shopsmart.commerce.audit` transitions. Correlate with `request_id`, `order_id`, and internal `payment_id`; logs never include credentials or provider request payloads. Centralized log retention is the commerce audit record; the webhook table stores dedupe markers only. Check order/payment status through the owner-scoped order endpoint. If checkout is 503, verify that both secrets are test-mode values and present in the backend environment.

## Interview explanation

“I kept payments behind a provider interface and used hosted Checkout so the application never handles card data. Checkout still computes prices and promotions under the existing transaction and persists one pending order/payment keyed by idempotency. A browser return does not grant paid status: a signed, time-bounded webhook must match the stored session, order, total, and currency before one transaction marks the payment and order successful. Webhook event IDs and the provider idempotency key make retries safe.”
