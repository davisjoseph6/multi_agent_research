#!/usr/bin/env bash
# Privileged CI-only regression for the actual failure: systemd 200/CHDIR.
# Run only in a disposable GitHub Actions Ubuntu runner (never on the VPS).
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo "Run as root in isolated CI only" >&2; exit 2; }
command -v runuser >/dev/null
id nobody >/dev/null
WORKDIR="$(mktemp -d /tmp/supervisor-chdir-ci.XXXXXXXX)"
trap 'rm -rf -- "$WORKDIR"' EXIT
chmod 0755 "$WORKDIR"
SOURCE="$WORKDIR/private-ssh-upload"
RELEASES="$WORKDIR/srv/releases"
RELEASE="$RELEASES/test-commit"
STATE="$WORKDIR/private-databases"
mkdir -p "$SOURCE/agent2_realdata_benchmark/scripts"
install -d -m 0755 "$RELEASES" "$RELEASE"
install -d -m 0700 "$STATE"
printf 'app = None\n' > "$SOURCE/agent2_realdata_benchmark/scripts/supervisor_vps_wsgi.py"
chmod 0700 "$SOURCE"
test "$(stat -c %a "$SOURCE")" = 700

# Exactly the GNU cp -a behavior behind the user's failed first install.
cp -a "$SOURCE/." "$RELEASE/"
chmod -R go-w "$RELEASE"
test "$(stat -c %a "$RELEASE")" = 700
if runuser -u nobody -- test -x "$RELEASE"; then
    echo "Expected original CHDIR permission failure was not reproduced" >&2
    exit 1
fi

# New installer behavior: allow traversal of SOURCE-CODE ONLY.
chmod 0755 "$RELEASE"
runuser -u nobody -- test -x "$RELEASE/agent2_realdata_benchmark/scripts"
runuser -u nobody -- test -r "$RELEASE/agent2_realdata_benchmark/scripts/supervisor_vps_wsgi.py"
if runuser -u nobody -- test -x "$SOURCE"; then
    echo "Secret upload permissions were unexpectedly weakened" >&2
    exit 1
fi
if runuser -u nobody -- test -x "$STATE"; then
    echo "Private study state permissions were unexpectedly weakened" >&2
    exit 1
fi

# An earlier interrupted install has the same retained 0700 release root.
chmod 0700 "$RELEASE"
chmod 0755 "$RELEASE"
runuser -u nobody -- test -x "$RELEASE/agent2_realdata_benchmark"

echo "PASS: private 0700 upload reproduces CHDIR; 0755 release fixes it"
echo "PASS: secondary service user traverses code; private upload/state remain inaccessible"
echo "PASS: already-existing 0700 release repaired idempotently"
