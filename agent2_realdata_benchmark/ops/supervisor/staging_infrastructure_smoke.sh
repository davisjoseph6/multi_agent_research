#!/usr/bin/env bash
# Read-only public and loopback health smoke for an INSTALLED staging VPS.
# Run on the VPS (not from WSL); never prompt for, print, or transmit secrets.
set -Eeuo pipefail
SERVICE=ijcai-supervisor-staging
MONITOR=ijcai-supervisor-researcher
HOST=https://demo.selfhealing-edu.fr
CURRENT=/srv/ijcai-supervisor-staging/current
EXPECTED="${1:-}"

[[ "$EXPECTED" = "" || "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Optional expected SHA must have 40 lowercase hex characters" >&2; exit 2;
}
systemctl is-active --quiet "$SERVICE" || { echo "Study service inactive" >&2; exit 1; }
systemctl is-active --quiet "$MONITOR" || { echo "Researcher monitor inactive" >&2; exit 1; }
echo "PASS study and researcher services active"

RELEASE="$(readlink -f "$CURRENT")"
case "$RELEASE" in
  /srv/ijcai-supervisor-staging/releases/*) ;;
  *) echo "Unknown release path; aborting" >&2; exit 1 ;;
esac
SHA="${RELEASE##*/}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Unexpected release revision" >&2; exit 1; }
if [[ -n "$EXPECTED" && "$SHA" != "$EXPECTED" ]]; then
  echo "Deployed SHA does not match expected revision" >&2; exit 1
fi
echo "PASS deployed revision $SHA"

# Direct local connection must fail the canonical host/HTTPS security check.
direct="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8788/study/health)"
[[ "$direct" == 403 ]] || { echo "Unsafe direct health status: $direct" >&2; exit 1; }
echo "PASS direct HTTP blocked (403)"

researcher="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
  http://127.0.0.1:8790/admin/)"
[[ "$researcher" == 401 ]] || {
  echo "Researcher dashboard accessible without authentication: $researcher" >&2; exit 1;
}
echo "PASS unauthenticated researcher access denied (401)"

external="$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' \
  "$HOST/study/")"
[[ "$external" == 401 ]] || {
  echo "Unauthenticated public study status: $external" >&2; exit 1;
}
echo "PASS unauthenticated HTTPS study access denied (401)"
echo "No tokens, participant records, Caddy passwords or research answers accessed."
echo "This is staging infrastructure verification, not human-recruitment approval."
