# Local Docker Environment

## Configure

Copy the root `.env.example` to `.env`, then set `DATABASE_URL` to the
PostgreSQL instance used by this project and replace `SECRET_KEY` with a random
secret. PostgreSQL is external and is not started by Compose. With Docker
Desktop, `host.docker.internal` can address PostgreSQL running on the host; on
other setups, use a hostname reachable from the containers.

`CORS_ORIGINS` must be a JSON array of exact trusted origins. The example
contains localhost origins for local development; set it to the actual
frontend origin(s) in each deployment environment. The application does not
assume or hard-code a production domain, and wildcard origins are rejected.

`NEXT_PUBLIC_API_URL` is embedded into browser JavaScript during the frontend
image build, so use a URL the browser can reach (by default,
`http://localhost:8000/api/v1`). Next.js middleware uses the private
`API_INTERNAL_URL` supplied to the frontend build and runtime by Compose to
reach the backend over the Compose network.

## Start

```sh
docker compose up --build -d
```

The backend uses `/health` for its process health check. `/readiness` currently
does not check database connectivity, so it is not used as the Compose health
check. Redis is checked with `redis-cli ping`; its data is persisted in the
`redis_data` volume and its port is not published to the host.

## Migrations

The backend container does not run migrations or create tables automatically.
After Compose starts, apply the checked-in Alembic migrations explicitly:

```sh
docker compose exec backend alembic upgrade head
```

The backend image includes the project-locked Alembic dependency and migration
files. The Compose backend disables the application's existing development
`create_all` startup behavior so Alembic remains the schema authority there.

## Optional Local Demo Products

Demo seeding is a manual, local-development-only operation. It is not run by
application startup, migrations, Docker startup, CI, or deployment. It inserts
only missing demo SKUs and leaves existing product records unchanged. Never
point it at a production or shared database.

From `backend/` in PowerShell, after configuring `DATABASE_URL` for a local
database and applying migrations:

```powershell
$previousDemoSeedSetting = $env:SHOPSMART_ALLOW_DEMO_SEEDING
try {
	$env:SHOPSMART_ALLOW_DEMO_SEEDING = "true"
	.\.venv\Scripts\python.exe -m scripts.seed_demo_products --apply
}
finally {
	if ($null -eq $previousDemoSeedSetting) {
		Remove-Item Env:SHOPSMART_ALLOW_DEMO_SEEDING -ErrorAction SilentlyContinue
	}
	else {
		$env:SHOPSMART_ALLOW_DEMO_SEEDING = $previousDemoSeedSetting
	}
}
```

Both `--apply` and `SHOPSMART_ALLOW_DEMO_SEEDING=true` are required. Without
both, the command refuses and makes no database connection or changes.

## Stop

```sh
docker compose down
```

Redis data remains in the named volume. To remove it as well, run
`docker compose down -v`.