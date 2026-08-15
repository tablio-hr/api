#!/usr/bin/env bash
# Production deploy on dedicated-hel1 only. Never touches stage tunnel/DNS.
set -euo pipefail

SSH_HOST="dedicated-hel1"
REMOTE_PATH="/opt/stacks/tablio.hr/api"

REMOTE_SCRIPT=$(cat <<'EOF'
set -euo pipefail
unset SSH_AUTH_SOCK || true
cd /opt/stacks/tablio.hr/api
branch="$(git branch --show-current)"
[[ "$branch" == "main" ]] || {
  echo "deploy-production requires branch main (got ${branch})" >&2
  exit 1
}
git fetch origin main
git checkout main
git pull --ff-only origin main
if [[ "${SKIP_CLOUDFLARE:-}" != "1" ]]; then
  ./scripts/cloudflare_dns_upsert.sh
fi
docker compose up -d --build django-migrate
docker compose up -d django celery-worker
echo "production deploy finished $(git rev-parse --short HEAD)"
EOF
)

echo "==> SSH ${SSH_HOST} → ${REMOTE_PATH}"
ssh "$SSH_HOST" "$REMOTE_SCRIPT"
