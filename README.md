# Tablio API

Django + DRF + Celery platform for Tablio. Boundaries are locked in [ADR 0001](https://github.com/tablio-hr/docs/blob/develop/architecture/adr/0001-platform-deployment-and-tenancy-boundary.md): **the host selects the surface; authentication selects the tenant.**

Feature work lands on `develop` (WSL stage). Production is `main` on dedicated-hel1 after **Promote to production**.

## Hosts

- Stage: `admin-stage.tablio.hr` (admin only), `api-stage.tablio.hr` (API only)
- Production: `admin.tablio.hr` (admin only), `api.tablio.hr` (API only)
- Cross-surface requests return 404. Unknown `Host` returns 400.

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

Slice 1 plan: [001-tenant-location-auth-context](https://github.com/tablio-hr/docs/blob/develop/architecture/implementation/001-tenant-location-auth-context.md).

## Release

```text
feature PR → CI → develop stage deploy → stage smoke
  → Promote to production PR → main production deploy → production smoke
```
