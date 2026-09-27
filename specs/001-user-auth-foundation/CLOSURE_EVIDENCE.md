# Feature 001 Closure Evidence

**Review date**: 2026-09-27
**Disposition**: Implementation and applicable automated tests are complete; one manual accessibility item remains pending and six items remain blocked by missing routes or an external HTTPS deployment.

## Task Classification

| Task | Result | Evidence or exact prerequisite |
|---|---|---|
| T070 | Blocked | No Feature 001 endpoint accepts a caller-supplied user/resource ID. Add this test when a concrete user-owned resource route is introduced; do not invent one for this feature. |
| T072 | Blocked | Same missing user-owned resource route; the self-profile endpoint is not a cross-user target route. |
| T073 | Blocked | Same missing route; owner/non-owner status behavior can only be specified and tested for concrete user-scoped routes. |
| T080 | Blocked | No route accepts resource IDs for the shared ownership helper to protect. Apply it when such a route is introduced. |
| T113 | Blocked, partially evidenced | Available authentication flows were exercised through the real Next.js BFF and FastAPI app locally. Browser Secure-cookie continuity requires an HTTPS browser origin; cross-user validation requires a concrete resource route, its authorization contract, and two users with owned/other-user fixtures. See below. |
| T114 | Pending manual completion | Registration/login evidence from the earlier local browser review remains recorded; the shared authenticated account tab was also inspected for semantics, keyboard order, and validation recovery. A concrete account validation defect was fixed and regression-tested. A screen-reader/assistive-technology pass remains outstanding. |
| T121 | Blocked | No deployed HTTPS target, deployment URL, or local HTTPS listener was available. SC-011 also does not enumerate the secure response headers expected for acceptance. See the exact prerequisites below. |

The Feature 001 checklist remains **117 complete, 1 pending, 6 blocked out of 124**, with unique task IDs.

## T113 Quickstart Run

The actual Next.js frontend ran at `http://127.0.0.1:3000` and the actual FastAPI app at `http://127.0.0.1:8000`. Authentication requests used the existing same-origin `/api/auth/*` BFF. The API used a disposable SQLite database in the workspace and a temporary launcher applying the same PostgreSQL-only check-constraint filter used by `backend/tests/conftest.py`. This is not PostgreSQL or deployment evidence. Cookie headers were supplied explicitly to BFF requests because the origin was HTTP; this does not prove browser handling of a `Secure` cookie.

| Quickstart scenario | Observed result | Classification |
|---|---|---|
| Register, login, identify user, logout | Register 201; login 200; `/auth/me` 200; logout 204; subsequent `/auth/me` 401. The login response included `Secure`, `HttpOnly`, and `SameSite=Strict`. | Proven at local BFF/API level, not browser Secure-cookie continuity. |
| Cross-user access denied | Only authenticated self-profile exists; there is no target-user profile, order, cart, document, or other owned-resource route in Feature 001. | Blocked by missing concrete user-owned resource route. |
| Weak password rejected | Registration returned 400 `weak_password`. | Proven at local BFF/API level. |
| Login rate limit | Five invalid-login attempts returned 401; the sixth returned 429 `rate_limited`. | Proven at local BFF/API level. |
| Inactivity expiration | Set the disposable test session's `last_activity` to 31 days before the request; `/auth/me` returned 401. | Proven at local app/SQLite level; the existing mocked-time tests remain the deterministic boundary evidence. |
| Password change invalidates sessions | CSRF retrieval returned 200; password change returned 204; old password login returned 401; new password login returned 200; logout returned 204 and the old session then returned 401. | Proven at local BFF/API level. |

The quickstart's complete browser/deployment run remains blocked: there is no HTTPS origin, so browser cookie continuity cannot be assessed, and the cross-user scenario has no real route. The embedded browser automation also did not emit form submit requests during its click attempts; the direct BFF HTTP requests above are reported separately and are not represented as browser form submission evidence.

## T114 Accessibility Review

### Observed and checked

- Earlier local browser evidence for registration/login remains: both pages exposed level-one headings and named fields; registration exposed a named “Password requirements” list with textual met/not-met states. Registration and login keyboard order and the login button's visible focus ring were observed in that review. The shared auth pages were no longer reachable for a fresh review in this pass because the local server had stopped.
- The authenticated account browser tab rendered navigation links and logout, an “Account Information” level-one heading, a “Change Password” level-two heading, three named password textboxes, and the Change Password and Sign Out buttons.
- Keyboard Tab traversal on the account page reached the brand link, Dashboard, Account, Log Out, Current Password, New Password, Confirm New Password, Change Password, and Sign Out, then cycled back to the brand link. The navigation and buttons define focus-visible rings; the password inputs define a focus ring. A pixel-level visual focus check for every account control was not completed.
- Submitting mismatched password confirmation in the live account page exposed a defect: the page returned only the error alert, removed the password form and controls, and left focus on the document body. The page now keeps the account form mounted for validation errors and renders the mismatch once on Confirm New Password. The focused account-page regression test verifies the fields/actions remain available, exactly one alert is exposed, and the API is not called.
- Field labels are associated with their inputs. Error UI uses `role="alert"`; success UI uses `role="status"`. Password requirement changes are ordinary list text, not a live region, so dynamic announcements have not been established.

### Contrast finding and correction

The initial auth-page placeholder used the browser's computed `oklab(0 0 0 / 0.5)` over white, approximately 3.95:1, below the 4.5:1 WCAG AA normal-text threshold. Registration and login now explicitly use Tailwind `gray-600` for placeholders. The live login page computes that placeholder as `oklch(0.446 0.03 256.802)`, approximately 7.56:1 over white.

Other palette ratios computed from the rendered theme's declared foreground/background colors: `ink-500` on blush 5.45:1; `accent-600` on white 7.34:1; `leaf-600` on white 8.22:1; and field-label `gray-700` on white 10.31:1. These exceed 4.5:1 for normal text. This was a color-value contrast check, not a full pixel-level audit of every state or background.

### Still required for T114

A human must complete and record a screen-reader/assistive-technology pass, including whether password requirement state changes and form errors are announced appropriately. Reopen the authenticated account flow after the local app is running to confirm visual focus treatment across the form and navigation. No screen-reader test or WCAG conformance claim is made; T114 remains unchecked.

The current shared account browser was authenticated as `closure-review-20260927@example.test`. The local server stopped during this review, so post-fix behavior was verified by the focused Jest regression test rather than a second live-browser submission.

## T113 Remaining Prerequisites

- For Secure-cookie browser continuity: an accessible HTTPS frontend origin wired to the intended backend, a real browser session, and permission to inspect login/current-user/logout behavior without manually injecting cookies. This must exercise the actual `Secure` cookie over TLS; HTTP localhost and direct BFF requests are not substitutes.
- For cross-user validation: a concrete authenticated route that accepts a user-owned resource identifier, a documented owner/non-owner status contract (including whether denial is 403 or 404), and two test users with resources owned by each. The present `/api/v1/users/profile` is self-only and has no caller-selected target ID; `/api/v1/users/password` is also self-scoped.
- The earlier local flow used disposable SQLite, not PostgreSQL. If the quickstart's deployment acceptance includes database parity, a PostgreSQL-backed run is additional required evidence.

T070, T072, T073, and T080 therefore remain unchecked. Feature 001 has no concrete user-owned resource route in the backend API; the current user routes expose only self-profile and password operations. No synthetic route was introduced.

## T121 Deployment Prerequisites

T121 cannot be completed from this workspace. No deployed HTTPS hostname or test target was supplied; no local HTTPS listener was available; and the only local app run was HTTP on loopback. Completion requires an actual deployed HTTPS URL, permission and test credentials to exercise sensitive API responses, and a documented list of required secure headers/expected values. SC-011 says “secure headers” but does not enumerate them. Record trusted TLS/certificate behavior and observed response headers from that deployed target. Local cookie flags and localhost API tests are not substitutes.

## Validation Context

Previously recorded automated results remain: full backend 107 passed; focused auth 72 passed; TypeScript, ESLint, Ruff, Black, scoped Prettier, and `git diff --check` passed at that earlier point. In this review, all 55 frontend Jest tests passed, including the account validation regression, and editor diagnostics reported no errors in the changed TS/TSX and closure files. TypeScript, lint, and diff-check were attempted again, but the integrated PowerShell runner returned no output or exit markers, so those reruns are inconclusive. No production HTTPS or manual screen-reader verification is claimed.
