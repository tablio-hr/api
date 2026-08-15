#!/usr/bin/env bash
# Stage only: remotely-managed tunnel ingress AND proxied CNAME.
# Both steps are required. Uses CF_DNS_TOKEN_STAGE. Never reads Traefik ACME tokens.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/allowlist.sh
source "${ROOT_DIR}/scripts/lib/allowlist.sh"

MODE="stage"
CF_API="https://api.cloudflare.com/client/v4"
ZONE_NAME="${CLOUDFLARE_ZONE_NAME:-tablio.hr}"
NAMES="${TABLIO_DNS_NAMES:-$STAGE_DNS_ALLOWLIST}"
TOKEN="${CF_DNS_TOKEN_STAGE:-}"
TUNNEL_ID="${CLOUDFLARE_TUNNEL_ID:-}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"
INGRESS_SERVICE="${TABLIO_TUNNEL_SERVICE:-http://traefik:80}"

[[ -n "$TOKEN" ]] || die "CF_DNS_TOKEN_STAGE is required"
[[ -n "$TUNNEL_ID" ]] || die "CLOUDFLARE_TUNNEL_ID is required"

for name in $NAMES; do
  assert_allowlist "$MODE" "$name"
done

if [[ "${TABLIO_DRY_RUN:-}" == "1" ]]; then
  echo "dry-run stage ingress+CNAME: $NAMES -> ${INGRESS_SERVICE}"
  exit 0
fi

[[ -n "$ACCOUNT_ID" ]] || die "CLOUDFLARE_ACCOUNT_ID is required"

cf_api() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-sS -X "$method" "${CF_API}${path}"
    -H "Authorization: Bearer ${TOKEN}"
    -H "Content-Type: application/json")
  if [[ -n "$data" ]]; then
    args+=(--data "$data")
  fi
  curl "${args[@]}"
}

json_get() {
  python3 -c 'import json,sys; d=json.load(sys.stdin); '"$1" <<<"$2"
}

zones="$(cf_api GET "/zones?name=${ZONE_NAME}&status=active")"
ZONE_ID="$(json_get 'print((d.get("result") or [{}])[0].get("id",""))' "$zones")"
[[ -n "$ZONE_ID" ]] || die "Zone ${ZONE_NAME} not found"

CNAME_TARGET="${TUNNEL_ID}.cfargotunnel.com"
ingress_ok=0
cname_ok=0

# Remotely-managed public hostnames (Cloudflare Tunnel config).
# Preserve Host: HTTP origin, no host rewrite.
ingress_payload="$(python3 - <<PY
import json
names = """${NAMES}""".split()
ingress = [{"hostname": n, "service": "${INGRESS_SERVICE}"} for n in names]
ingress.append({"service": "http_status:404"})
print(json.dumps({"config": {"ingress": ingress}}))
PY
)"
ingress_resp="$(cf_api PUT "/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations" "$ingress_payload")"
if python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("success") else 1)' <<<"$ingress_resp"; then
  ingress_ok=1
  echo "tunnel ingress updated for: $NAMES"
else
  echo "$ingress_resp" >&2
  die "tunnel ingress update failed"
fi

for name in $NAMES; do
  existing="$(cf_api GET "/zones/${ZONE_ID}/dns_records?type=CNAME&name=${name}")"
  rec_id="$(json_get 'r=(d.get("result") or [None])[0]; print(r.get("id","") if r else "")' "$existing")"
  payload="$(python3 -c 'import json,sys; print(json.dumps({"type":"CNAME","name":sys.argv[1],"content":sys.argv[2],"proxied":True,"ttl":1}))' "$name" "$CNAME_TARGET")"
  if [[ -n "$rec_id" ]]; then
    resp="$(cf_api PUT "/zones/${ZONE_ID}/dns_records/${rec_id}" "$payload")"
  else
    resp="$(cf_api POST "/zones/${ZONE_ID}/dns_records" "$payload")"
  fi
  if python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("success") else 1)' <<<"$resp"; then
    echo "upserted CNAME ${name} -> ${CNAME_TARGET}"
  else
    echo "$resp" >&2
    die "CNAME upsert failed for ${name}"
  fi
done
cname_ok=1

if [[ "$ingress_ok" -ne 1 || "$cname_ok" -ne 1 ]]; then
  die "stage tunnel upsert incomplete (ingress and CNAME are both required)"
fi
