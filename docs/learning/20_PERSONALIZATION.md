# 20. Personalization

## What and why

Personalization applies preferences that a shopper deliberately saves. It improves ranking while leaving prices, stock, order access and hard constraints under backend authority.

## Flow and files

The `shopper_preferences` table is keyed uniquely by the authenticated owner. `ShopperPreferenceService` validates and replaces the bounded explicit profile, and deletes it on request. Authenticated `GET`, `PUT` and `DELETE /api/v1/ai/preferences` support the preferences panel. The Next.js same-origin proxy forwards the browser session and CSRF token to FastAPI.

## Privacy and failure modes

Only explicit preferences persist. Behavioral views, comparisons and purchases are not silently promoted into a profile; inferred data is empty and behavioral memory is disabled. Requests cannot supply an owner ID. Foreign-key deletion follows account deletion. Hard constraints always outrank preferred brand or budget.

## How to test and debug

Run preference service/API tests and the browser preference journey. Verify save, reload, deletion and second-account isolation. Inspect only the authenticated profile response; avoid logging profile values.

## Interview explanation

“We persist an owner-scoped explicit profile with view, update and deletion controls. We never turn weak activity signals into permanent preferences without consent.”
