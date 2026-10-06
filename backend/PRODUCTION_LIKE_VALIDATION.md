# Production-Like Local Validation

The `production-like-v1` dataset is deterministic, synthetic, and local-only. It creates 1,000 catalog products with canonical structured categories and seven reserved test accounts (`@shopsmart.local.invalid`), with owned carts, historical order snapshots, and explicitly synthetic backend-owned knowledge. It does not contain real people or production policy.

## Seed and Reset

Run from `backend/` after applying the existing Alembic migrations to the local database. The database must be on loopback; schema creation is not performed by this command.

PowerShell setup for a disposable local-only login password:

```powershell
$env:SHOPSMART_ENV = 'local'
$env:SHOPSMART_ALLOW_DEMO_SEEDING = 'true'
$seedPassword = Read-Host 'Enter a unique local-only seed password' -AsSecureString
$env:SHOPSMART_LOCAL_SEED_PASSWORD = [Net.NetworkCredential]::new('', $seedPassword).Password
```

Keep the password available in this local PowerShell session for browser validation. Existing seed-owned accounts retain their current password hash on repeat seed runs. Do not commit the password or reuse it outside this disposable environment; the application stores only password hashes.

Seed:

```powershell
python -m src.seed.production_like seed --apply
```

Repeat the seed command to restore the same product/cart/order fixtures without duplicating them. Passwords already assigned to an existing seed-owned account are preserved.

Reset only the reserved dataset:

```powershell
python -m src.seed.production_like reset-seeded-data --apply --confirm-version production-like-v1
```

Both commands require the local/test environment opt-in and a loopback database host. Production/staging labels, production-like database names, absent opt-in, and remote DB hosts fail closed. Reset refuses to proceed if a non-seeded shopper's cart/order references a seeded product. It removes conversations and sessions owned by the reserved synthetic accounts, but leaves unrelated users/products/carts/orders and all other knowledge sources untouched.

## Seeded Accounts

All accounts use the configured `SHOPSMART_LOCAL_SEED_PASSWORD` value above.

| Account                                            | Validation role                                            |
| -------------------------------------------------- | ---------------------------------------------------------- |
| `new-customer@shopsmart.local.invalid`             | Empty cart, no orders                                      |
| `returning-customer@shopsmart.local.invalid`       | Multi-item cart and several order statuses                 |
| `single-cart-customer@shopsmart.local.invalid`     | Single-item cart and one order                             |
| `quantity-update-customer@shopsmart.local.invalid` | Existing quantity-two line for update/increment validation |
| `no-orders-customer@shopsmart.local.invalid`       | Empty cart and no orders                                   |
| `empty-cart-customer@shopsmart.local.invalid`      | Empty cart and multiple orders                             |
| `cross-user-customer@shopsmart.local.invalid`      | Separate cart/order ownership boundary                     |

No loyalty/premium status is seeded because the current User model has no membership field.

## Data Limits

Category-constrained search uses the structured `products.category` field; text mentions cannot satisfy or override a category filter. The additive migration leaves pre-existing products with unknown category as `NULL`; they remain eligible for unrestricted searches but not category-constrained results until trustworthy catalog data is available. The schema still has no structured brands, variants, sale prices, or product metadata. Promotions are now persisted, backend-owned records evaluated deterministically against current time, shopper, cart lines, thresholds, and scope; the versioned synthetic fixture includes active, expired, future, targeted, and competing offers. Public/admin promotion management, membership tiers, redemption limits, and stacking remain unsupported. Order status strings include placed, confirmed, shipped, delivered, cancelled, returned, and refunded as historical examples, not as implemented transition workflows. The policy corpus is synthetic local validation content, not approved business policy; never publish it to production.

Versioned assistant scenarios are in `evals/datasets/commerce_production_like_v1.json`. Unit fixtures remain valuable for regression speed but are not product validation by themselves. The assistant must continue to obtain dynamic prices, stock, carts, orders, and offers only from existing authoritative services; RAG is limited to stable server-owned knowledge.

Run the backend service-level evaluation after seeding:

```powershell
python -m src.evals.production_like
```

It uses only the deterministic local provider, refuses non-local targets, checks the versioned routes and scenarios through the real services, and reports category distribution/precision plus five-sample median latency for catalog, assistant, cart, order, and policy retrieval paths. Use the shared local/test opt-in variables above; the runner never contacts paid providers.
