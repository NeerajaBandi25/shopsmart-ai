# Frontend Development

## Requirements

- Node.js 18 or newer
- npm 9 or newer
- The FastAPI backend and PostgreSQL database for live authentication flows

## Setup

From the `frontend/` directory:

```powershell
npm ci
Copy-Item .env.example .env.local
```

Set `API_INTERNAL_URL` to the backend's versioned API URL (for example, `http://localhost:8000/api/v1`). This variable is server-only and is used by the Next.js auth BFF; never rename it with a `NEXT_PUBLIC_` prefix. `NEXT_PUBLIC_API_URL` is retained for the product catalog and is not used for browser authentication. `NEXT_PUBLIC_APP_NAME` is optional.

Start the application:

```powershell
npm run dev
```

Browser authentication uses same-origin `/api/auth/*` routes. The BFF forwards session cookies and CSRF headers to FastAPI and relays session-cookie updates. Protected page middleware validates sessions through `/api/auth/me` and redirects only when the backend reports 401. Session cookies are Secure; production and browser-restart verification must use HTTPS.

## Tests and Quality

```powershell
npm test -- --runInBand
npm run lint
npm exec -- tsc --noEmit --incremental false
npm run format:check
```

Focused auth tests include the registration/login/account UI, API client, BFF routes, and middleware. Tests use controlled responses and do not require a live backend. A browser walkthrough with real cookies requires a running backend and HTTPS-capable frontend origin.
