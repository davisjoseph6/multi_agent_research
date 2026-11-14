#!/usr/bin/env bash
# Update a PREPARED, NOT ACTIVE isolated LIVE installation to a newer
# exact Git release while preserving every existing database and credential.
# Will not run against an activated, running or publicly routed LIVE system.
# Required inputs: pinned complete Git bundle and the SHA of its advertised
# research branch ref. Never imports STAGING records.
set -Eeuo pipefail
[[ "$EUID" -eq 0 && "$#" -eq 2 ]] || {
  echo "Usage: sudo bash upgrade_pending_live_release.sh ABSOLUTE_BUNDLE FULL_SHA" >&2
  exit 2
}
BUNDLE="$1" SHA="$2"
[[ "$BUNDLE" = /* && -f "$BUNDLE" && ! -L "$BUNDLE" &&
   "$SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Non-symlink absolute bundle and full release SHA required" >&2
  exit 2
}
PREFIX=/srv/ijcai-supervisor-live
STATE=/var/lib/ijcai-supervisor-live
PRIVATE=/etc/ijcai-supervisor-live
USER=ijcai-supervisor-live
REF=refs/remotes/origin/research/ijcai2027-supervisor-consent-gdpr-20261112
LOCK=/run/lock/ijcai-supervisor-live-install.lock
exec 9>"$LOCK"
flock -n 9 || { echo "LIVE install lock busy" >&2; exit 2; }
for unit in ijcai-supervisor-live-study.service \
            ijcai-supervisor-live-recruitment.service \
            ijcai-supervisor-live-control.service \
            ijcai-supervisor-live-reminders.timer; do
  if systemctl is-active --quiet "$unit" ||
     systemctl is-enabled --quiet "$unit"; then
    echo "Refusing update: LIVE unit is active/enabled: $unit" >&2
    exit 2
  fi
done
[[ -L "$PREFIX/current" && ! -L "$PREFIX/releases" &&
   -d "$PREFIX/releases" && ! -L "$STATE" &&
   -d "$STATE/document_registry/versions" &&
   ! -e "$STATE/document_registry/current" &&
   ! -e "$PRIVATE/live.env" &&
   ! -e /etc/caddy/ijcai-supervisor-live.caddy ]] || {
  echo "Not a safely pending and unactivated LIVE installation" >&2
  exit 2
}
id "$USER" >/dev/null
CURRENT="$(readlink "$PREFIX/current")"
[[ "$CURRENT" =~ ^releases/[0-9a-f]{40}$ ]] || {
  echo "Unexpected current release symlink" >&2; exit 2
}
OLD="${CURRENT#releases/}"
[[ "$OLD" != "$SHA" ]] || {
  echo "Already prepared at requested revision; no changes made."
  exit 0
}
[[ -d "$PREFIX/releases/$OLD" &&
   "$(git -C "$PREFIX/releases/$OLD" rev-parse HEAD)" == "$OLD" &&
   -z "$(git -C "$PREFIX/releases/$OLD" status --porcelain)" ]] || {
  echo "Existing release is unclean or mismatched; refusing update" >&2
  exit 2
}
[[ -x "$PREFIX/venv/bin/python" ]] || {
  echo "Existing prepared LIVE Python environment missing" >&2; exit 2
}
HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/materialize_live_bundle.sh"
[[ -f "$HELPER" && ! -L "$HELPER" ]] || {
  echo "Pinned materialization helper must accompany the installer" >&2; exit 2
}
bash "$HELPER" "$BUNDLE" "$SHA" "$PREFIX/releases/$SHA" "$REF"
# Create a NEW pending bundle bound to the new code commit. Never rename
# the old version or mark either version approved.
runuser -u "$USER" -- bash -c '
  set -Eeuo pipefail
  cd "$1/agent2_realdata_benchmark"
  "$2" -m scripts.supervisor_doc_bundle_cli \
    --registry "$3/document_registry" \
    --commit "$4" \
    --draft-source "$3/document_intake_empty"
' bash "$PREFIX/releases/$SHA" "$PREFIX/venv/bin/python" "$STATE" "$SHA"
TEMP="$PREFIX/.pending-current.$$"
[[ ! -e "$TEMP" && ! -L "$TEMP" ]] || {
  echo "Unexpected transient link exists" >&2; exit 2
}
cleanup(){ rm -f -- "$TEMP"; }
trap cleanup EXIT
ln -s "releases/$SHA" "$TEMP"
mv -Tf -- "$TEMP" "$PREFIX/current"
trap - EXIT
[[ "$(git -C "$PREFIX/current" rev-parse HEAD)" == "$SHA" ]] || {
  echo "Unexpected post-upgrade release revision" >&2; exit 2
}
echo "PASS: pending-only LIVE code upgraded from $OLD to $SHA."
echo "Existing LIVE state/credentials were not migrated, deleted or overwritten."
echo "LIVE services remain stopped, documents pending and recruitment disabled."
