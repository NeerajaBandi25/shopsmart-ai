# Quickstart: Promotion Engine Validation

## Safety Boundary

Do not point any migration, seed, evaluator, or browser flow at production or an unverified shared database. Use the isolated local/test PostgreSQL database only. Do not run the seed reset command as part of ordinary validation. Synthetic seeding requires the existing explicit local/test opt-in, loopback database check, and test-only password. No deployment is part of this feature.

## Backend

From `backend/`, activate the existing project environment and run focused tests first:

```powershell
python -m pytest tests/unit/test_promotion_service.py tests/unit/test_cart_service.py tests/unit/test_order_service.py
python -m pytest tests/integration/test_promotions_api.py tests/integration/test_cart_api.py tests/integration/test_order_checkout.py
```

Validate static quality and syntax:

```powershell
ruff check src tests
black --check src tests
python -m compileall -q src tests
```

Validate the migration graph and generated migration SQL before applying anything. Apply revision 013 only to an explicitly verified disposable local/test database, never to production or a normal shared developer database.

The production-like evaluator must run with the deterministic provider and a test-only database/environment. Seed only the versioned synthetic records and confirm the evaluator reports every promotion scenario passing. Do not reset seeded records unless a separate local-data cleanup is explicitly intended.

## Frontend

From `frontend/`, run the focused cart/checkout/assistant tests, then the frontend checks used by the repository CI:

```powershell
npm.cmd test -- --runInBand
npx.cmd tsc --noEmit
npm.cmd run lint
npm.cmd run format:check -- <changed frontend paths>
npm.cmd run build
```

Use the repository's installed tools; do not install packages or mass-format unrelated files for this feature.

## Browser Journey

Use the local app with the synthetic seeded shopper only:

1. Sign in using the local-only synthetic account.
2. Find a laptop and add it to the cart.
3. Ask the assistant for available offers and verify only backend promotion results are shown.
4. Apply `SAVE10` in the cart and verify `discount_total_cents` and `total_cents` match the API response.
5. Try unknown and expired codes and verify safe rejection with no stale total.
6. Change quantity and verify the quote recalculates; remove the code and verify automatic offer/original total behavior.
7. Sign in as a second synthetic shopper and verify the first shopper's cart/coupon cannot be read or mutated.
8. Complete checkout and verify the order pricing snapshot matches the backend's checkout response at placement.

Observe network responses for HTTP 500/503. Never use a real account or production data.
