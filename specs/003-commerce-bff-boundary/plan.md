# Implementation Plan: Same-Origin Commerce BFF

## Summary

Move the remaining browser-facing commerce API calls behind thin Next.js App Router handlers, reusing the Feature 001 server-only backend URL and cookie-relay convention. Keep FastAPI commerce contracts and business logic unchanged.

## Technical Context

- Frontend: existing Next.js App Router, TypeScript, `fetch`, Jest, and `API_INTERNAL_URL` server environment.
- Backend: existing FastAPI `/api/v1/products`, `/api/v1/cart`, and `/api/v1/orders` operations.
- Security: forward only explicitly permitted request headers; forward cookies on authenticated routes, CSRF on cart mutations and checkout, and checkout idempotency key; never trust a browser-provided upstream URL.
- Response handling: no-store; preserve status and safe body/content type, selected request/rate-limit headers, and each Set-Cookie value. Return a generic 503 for missing configuration or transport failure.
- Constraints: no backend business-logic edits, new dependencies, infra changes, manual browser testing, commit, push, or PR during this feature implementation.

## BFF Contract

| Same-origin route             | Method | FastAPI endpoint           | Forwarded request data                           |
| ----------------------------- | ------ | -------------------------- | ------------------------------------------------ |
| `/api/products`               | GET    | `/products`                | Query string                                     |
| `/api/cart`                   | GET    | `/cart`                    | Cookie                                           |
| `/api/cart/items`             | POST   | `/cart/items`              | Cookie, X-CSRF-Token, JSON body                  |
| `/api/cart/items/[productId]` | PUT    | `/cart/items/{product_id}` | Cookie, X-CSRF-Token, JSON body                  |
| `/api/cart/items/[productId]` | DELETE | `/cart/items/{product_id}` | Cookie, X-CSRF-Token                             |
| `/api/orders/checkout`        | POST   | `/orders/checkout`         | Cookie, X-CSRF-Token, Idempotency-Key, JSON body |
| `/api/orders`                 | GET    | `/orders`                  | Cookie                                           |

## Project Structure

- Shared server-only forwarding: `frontend/src/app/api/_commerce-proxy.ts`.
- Thin App Router handlers under `frontend/src/app/api/products/`, `cart/`, and `orders/`.
- Browser client functions remain in `frontend/src/lib/api-client.ts`, `cart-api.ts`, and `order-api.ts`.
- Route and client tests are colocated in `frontend/src/app/api/commerce-routes.test.ts` and `frontend/src/lib/*-api.test.ts`.

## Validation

Focused commerce BFF/client tests; existing commerce component tests; full frontend Jest; TypeScript no-emit; Next lint; Prettier check on changed frontend files; backend cart/order API tests where the selected local backend test environment permits; staged diff/whitespace and direct-URL audit.
