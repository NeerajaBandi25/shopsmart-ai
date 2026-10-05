# Local order email delivery

Order and payment events are committed to `notification_outbox` with the order
transaction. The email worker delivers them after commit. The local `console`
provider intentionally discards email content. Use Resend with an owned,
verified domain or SMTP through a mailbox app password for inbox delivery.

## One-time Resend setup

1. Create a Resend account and add a domain you control in its Domains page.
2. Add the DNS records Resend shows at your domain host, then wait until the
   domain is verified. The sender address must use that verified domain.
3. Create an API key with email sending permission. Keep it private; do not
   paste it into chat, commit it, or put it in frontend configuration.

Resend setup references:

- [Verify a domain](https://resend.com/docs/dashboard/domains/introduction)
- [Send an email](https://resend.com/docs/api-reference/emails/send-email)

## Local Compose configuration

Put these values in the ignored root `.env` file (copy `.env.example` first):

```dotenv
EMAIL_PROVIDER=resend
EMAIL_FROM_ADDRESS=ShopSmart AI <orders@your-verified-domain.example>
RESEND_API_KEY=re_your_private_key
APP_ENV=local
PUBLIC_APP_URL=http://localhost:3000
```

Start/restart the services from the repository root:

```powershell
docker compose --profile email up -d --build backend email-worker frontend
```

The `email-worker` polls the same PostgreSQL database as the API, so existing
pending messages can be delivered after the provider is configured. View
worker health/logs with:

```powershell
docker compose ps email-worker
docker compose logs --tail 100 email-worker
```

Look for `email_outbox_worker_started` with provider `resend`, followed by
`EMAIL_SENT`. Logs omit addresses and message content. `EMAIL_FAILED` includes
a safe error code; provider response bodies and API keys are never logged.

## Local Gmail SMTP test without a domain

The Resend `onboarding@resend.dev` sender is not authorized for this order's
recipient, which is why Resend returned HTTP 403. Gmail SMTP can send to the
buyer from your own Gmail address without a custom domain. Google requires
2-Step Verification before it allows an app password. Create an app password
for this local test; do not use your normal Google password.

- [Google: sign in with app passwords](https://support.google.com/mail/answer/185833)
- [Google: Gmail SMTP settings](https://support.google.com/mail/answer/7104828)

The supplied PowerShell launcher prompts for the Gmail address and app
password (the password input is hidden and is not written to a file). Start it
from the same PowerShell session that has the local `DATABASE_URL` and
`SECRET_KEY` values, after stopping the existing backend:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local-with-gmail-smtp.ps1
```

That starts the API and local outbox worker together. At the prompts, enter
your Gmail address and its app password. At the request ID prompt, enter the
`request_id` from the prior `EMAIL_FAILED` log to rebuild that paid order's
failed notification from its saved order record; press Enter to skip. Other
pending order messages are picked up automatically. The worker refuses to
start with `console` or `capture`, so those sinks cannot silently consume
pending messages. The password exists only in the launched process environment
and is not persisted by the script. A provider acceptance response means the message was accepted for
delivery, not a guarantee against later bounce or spam filtering; check the
recipient's Spam folder and the sender mailbox's Sent folder if needed.
