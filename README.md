# Tablio API

Django + DRF + Celery platform for Tablio. Feature work lands on `develop` (WSL stage). Production is `main` on dedicated-hel1 after **Promote to production**.

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

## Release

```text
feature PR → CI → develop stage deploy → stage smoke
  → Promote to production PR → main production deploy → production smoke
```
