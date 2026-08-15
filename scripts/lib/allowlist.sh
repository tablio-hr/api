# Shared allowlists for Tablio DNS / tunnel scripts.
STAGE_DNS_ALLOWLIST="admin-stage.tablio.hr api-stage.tablio.hr"
PRODUCTION_DNS_ALLOWLIST="admin.tablio.hr api.tablio.hr"

die() {
  echo "$*" >&2
  exit 1
}

assert_allowlist() {
  local mode="$1"
  local name="$2"
  local allowed=""
  case "$mode" in
    stage) allowed="$STAGE_DNS_ALLOWLIST" ;;
    production) allowed="$PRODUCTION_DNS_ALLOWLIST" ;;
    *) die "Unknown mode: $mode" ;;
  esac
  local item
  for item in $allowed; do
    if [[ "$item" == "$name" ]]; then
      return 0
    fi
  done
  die "Hostname '$name' is not on the $mode allowlist"
}
