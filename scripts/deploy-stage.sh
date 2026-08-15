#!/usr/bin/env bash
# Stage deploy on WSL only. Never SSHs to dedicated-hel1.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

unset SSH_AUTH_SOCK || true

branch="$(git branch --show-current)"
[[ "$branch" == "develop" ]] || {
  echo "deploy-stage requires branch develop (got ${branch})" >&2
  exit 1
}

git fetch origin develop
git pull --ff-only origin develop

if [[ "${SKIP_CLOUDFLARE:-}" != "1" ]]; then
  "${ROOT_DIR}/scripts/cloudflare_tunnel_upsert.sh"
fi

docker compose up -d --build django-migrate
docker compose up -d django celery-worker
echo "stage deploy finished $(git rev-parse --short HEAD)"
