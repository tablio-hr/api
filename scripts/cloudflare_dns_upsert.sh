#!/usr/bin/env bash
# Production only: upsert proxied A/AAAA for admin.tablio.hr and api.tablio.hr.
# Uses CF_DNS_TOKEN_PRODUCTION. Never reads Traefik ACME tokens.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/allowlist.sh
source "${ROOT_DIR}/scripts/lib/allowlist.sh"

MODE="production"
CF_API="https://api.cloudflare.com/client/v4"
ZONE_NAME="${CLOUDFLARE_ZONE_NAME:-tablio.hr}"
NAMES="${TABLIO_DNS_NAMES:-$PRODUCTION_DNS_ALLOWLIST}"
TOKEN="${CF_DNS_TOKEN_PRODUCTION:-}"
IPV4="${TABLIO_HEL1_IPV4:-65.108.196.92}"
IPV6="${TABLIO_HEL1_IPV6:-}"

[[ -n "$TOKEN" ]] || die "CF_DNS_TOKEN_PRODUCTION is required"
[[ "${CF_DNS_TOKEN_STAGE:-}" == "" ]] || true

for name in $NAMES; do
  assert_allowlist "$MODE" "$name"
done

if [[ "${TABLIO_DRY_RUN:-}" == "1" ]]; then
  echo "dry-run production upsert: $NAMES"
  exit 0
fi

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

zones="$(cf_api GET "/zones?name=${ZONE_NAME}&status=active")"
ZONE_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("result") or [{}])[0].get("id",""))' <<<"$zones")"
[[ -n "$ZONE_ID" ]] || die "Zone ${ZONE_NAME} not found"

upsert_record() {
  local fqdn="$1" type="$2" content="$3"
  [[ -n "$content" ]] || return 0
  local existing
  existing="$(cf_api GET "/zones/${ZONE_ID}/dns_records?type=${type}&name=${fqdn}")"
  local rec_id
  rec_id="$(python3 -c 'import json,sys; d=json.load(sys.stdin); r=(d.get("result") or [None])[0]; print(r.get("id","") if r else "")' <<<"$existing")"
  local payload
  payload="$(python3 -c 'import json,sys; print(json.dumps({"type":sys.argv[1],"name":sys.argv[2],"content":sys.argv[3],"proxied":True,"ttl":1}))' "$type" "$fqdn" "$content")"
  if [[ -n "$rec_id" ]]; then
    cf_api PUT "/zones/${ZONE_ID}/dns_records/${rec_id}" "$payload" >/dev/null
  else
    cf_api POST "/zones/${ZONE_ID}/dns_records" "$payload" >/dev/null
  fi
  echo "upserted ${type} ${fqdn} -> ${content}"
}

for name in $NAMES; do
  upsert_record "$name" A "$IPV4"
  upsert_record "$name" AAAA "$IPV6"
done
