#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${TABLIO_TEST_PG_NAME:-tablio-test-postgis}"
PORT="${TABLIO_TEST_PG_PORT:-55432}"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  -e POSTGRES_USER=tablio \
  -e POSTGRES_PASSWORD=tablio \
  -e POSTGRES_DB=tablio_platform_test_db \
  -p "127.0.0.1:${PORT}:5432" \
  postgis/postgis:16-3.4 >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$NAME" pg_isready -U tablio -d tablio_platform_test_db >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

PYTHON="${PYTHON:-python3}"
cd "$ROOT/backend"
DJANGO_SETTINGS_MODULE=config.settings.test \
  DB_HOST=127.0.0.1 \
  DB_PORT="$PORT" \
  DB_NAME=tablio_platform_test_db \
  DB_USER=tablio \
  DB_PASSWORD=tablio \
  "$PYTHON" manage.py test "$@"
