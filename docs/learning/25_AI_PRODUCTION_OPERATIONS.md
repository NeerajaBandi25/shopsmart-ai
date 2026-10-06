# 25. AI production operations

## What and why

Production operations combine tested authority boundaries, explicit configuration, health monitoring and graceful degradation. A local demo is evidence of local behavior, not hosted availability.

## Release flow

Apply versioned Alembic migrations, configure the server-side OpenRouter key/model and Redis connection, run deterministic backend and frontend gates, execute seeded browser journeys, and review the traces/evaluation report. Restrict externally shared policy to explicitly approved source keys. Keep payment and order facts on their existing authoritative services.

## Operational signals

Monitor provider success/failure, latency, token counts, configured cost, tool and retrieval duration, cache hit and fallback frequency. Rotate credentials through deployment secrets, bound provider retries and rate limits, and verify fallback behavior before changing model or prompt version.

## How to test and debug

Run backend tests with a disposable PostgreSQL test DB, real local Redis integration, frontend tests/build, and Playwright desktop/mobile coverage. A live provider smoke requires an available OpenRouter key and current free tool-capable model. No such credential means that single network-validation gate remains explicitly pending.

## Interview explanation

“Our release decision uses local reproducible evidence and calls out external validation separately. Migrations, provider configuration, Redis, observability and browser behavior all have explicit checks.”
