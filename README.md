# Tablio API

Django + DRF + Celery platform for Tablio. Boundaries are locked in [ADR 0001](https://github.com/tablio-hr/docs/blob/develop/architecture/adr/0001-platform-deployment-and-tenancy-boundary.md): **the host selects the surface; authentication selects the tenant.**

Feature work lands on `develop` (WSL stage). Production is `main` on dedicated-hel1 after **Promote to production**.

## Hosts

- Stage: `admin-stage.tablio.hr` (admin only), `api-stage.tablio.hr` (API only)
- Production: `admin.tablio.hr` (admin only), `api.tablio.hr` (API only)
- Cross-surface requests return 404. Unknown `Host` returns 400.

`POST /api/v1/early-access` is a public platform endpoint (no API key, no tenant). Browser CORS is limited to `https://stage.tablio.hr` and `https://tablio.hr`. Leads are listed in Django admin. After a successful save the API emails `info@tablio.hr` and sends a confirmation from `noreply@tablio.hr`. An SMTP failure is logged and does not delete the lead.

## Database

Django containers use the existing PostGIS service on the external `postgis` network:

```env
DB_HOST=postgis
DB_PORT=5432
DB_NAME=tablio_platform_db
DB_USER=tablio
```

Do not use a container ID or `127.0.0.1:5432` from Django. Host-side `psql` may use `127.0.0.1:5432`.

## Local

```bash
cp .env.example .env
# set DJANGO_SECRET_KEY and DB_PASSWORD
docker compose up -d --build
```

`/health/` is liveness. `/ready/` checks `tablio_platform_db` and Redis.

Create an API key (printed once):

```bash
docker compose --profile test-run run --rm django-run python manage.py create_api_app --tenant demo --name "demo"
```

Stage seed (not production, not PR CI). Passwords come from env or are printed once:

```bash
docker compose --profile test-run run --rm django-run python manage.py seed_stage_tenants
```

A changed env password does not overwrite a stored password unless you pass `--reset-admin-password`.

Staff login issues a Bearer token (`tablio_st_…`) with an absolute 12-hour `expires_at`. The raw token is shown once; only prefix + hash are stored. Logout is idempotent (`204`). A request must not send a staff Bearer token and an API key together (`400`). Staff mutations require `Idempotency-Key`.

Slice 1 plan: [001-tenant-location-auth-context](https://github.com/tablio-hr/docs/blob/develop/architecture/implementation/001-tenant-location-auth-context.md).

## Tests

Tests run only on PostGIS (`config.settings.test`). SQLite is not used. Django
creates a throwaway `test_*` database; it does not assert against the live
`DB_NAME`. The role must be able to `CREATE`/`DROP` that database — the stage
`tablio` role on the shared PostGIS cannot. Use a throwaway PostGIS, same as
PR CI:

```bash
./scripts/run-tests.sh
```

PR CI runs on dedicated-hel1 (`tablio-docker-runner`). HEL1 already binds
`127.0.0.1:5432`, so the job publishes PostGIS on `55432`. Stage deploy is
manual on WSL (`./scripts/deploy-stage.sh`), not a GitHub Actions job. See
[AGENTS.md](AGENTS.md).

## Release

```text
WSL develop (direct commit) → manual stage deploy → stage smoke
  → Promote to production PR → CI → main → production deploy
```
