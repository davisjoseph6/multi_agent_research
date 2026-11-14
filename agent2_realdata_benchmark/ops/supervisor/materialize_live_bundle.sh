#!/usr/bin/env bash
# Materialize a pinned remote-tracking ref from a Git bundle.
# Unlike git clone this does not need refs/heads/* or a default bundle HEAD.
# Recovers only an interrupted empty checkout and never resets real data.
set -Eeuo pipefail
[[ "$#" -eq 4 ]] || {
  echo "Usage: materialize_live_bundle.sh ABSOLUTE_BUNDLE FULL_SHA ABSOLUTE_DEST REFNAME" >&2
  exit 2
}
BUNDLE="$1" SHA="$2" DEST="$3" REF="$4"
[[ "$BUNDLE" = /* && -f "$BUNDLE" && ! -L "$BUNDLE" ]] || {
  echo "An absolute non-symlinked Git bundle is required" >&2; exit 2
}
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Exact full SHA required" >&2; exit 2; }
[[ "$DEST" = /* && "$DEST" != / && "$DEST" != */. && "$DEST" != */.. ]] || {
  echo "An absolute dedicated checkout directory is required" >&2; exit 2
}
[[ "$REF" =~ ^refs/remotes/origin/[A-Za-z0-9._/-]+$ && "$REF" != *..* ]] || {
  echo "A pinned remote-tracking ref is required" >&2; exit 2
}
[[ -d "$(dirname "$DEST")" && ! -L "$(dirname "$DEST")" ]] || {
  echo "An existing non-symlink checkout parent is required" >&2; exit 2
}
# The local caller supplies a pinned GitHub SHA; require that the
# advertised bundle ref resolves to precisely those bytes.
mapfile -t matching < <(git bundle list-heads "$BUNDLE" | awk -v ref="$REF" '$2==ref {print $1}')
[[ "${#matching[@]}" -eq 1 && "${matching[0]}" == "$SHA" ]] || {
  echo "Git bundle does not advertise the requested SHA and ref" >&2; exit 2
}
if [[ -e "$DEST" || -L "$DEST" ]]; then
  [[ -d "$DEST" && ! -L "$DEST" && -d "$DEST/.git" && ! -L "$DEST/.git" ]] || {
    echo "Existing checkout location is not a plain Git directory" >&2; exit 2
  }
  if git -C "$DEST" rev-parse --verify 'HEAD^{commit}' >/dev/null 2>&1; then
    echo "Existing checkout has a commit; refusing to reset it" >&2; exit 2
  fi
  # A previous aborted clone left exactly .git and nothing else.
  if find "$DEST" -mindepth 1 -maxdepth 1 ! -name .git -print -quit | grep -q .; then
    echo "Existing checkout contains files; refusing to alter them" >&2; exit 2
  fi
  echo "Recovering a previously interrupted empty Git checkout."
else
  mkdir -m 0755 -- "$DEST"
  git -C "$DEST" init -q
fi
git -C "$DEST" fetch --no-tags -q "$BUNDLE" "$REF:refs/heads/ijcai-live-import"
git -C "$DEST" checkout -q --detach "$SHA"
[[ "$(git -C "$DEST" rev-parse --verify HEAD)" == "$SHA" ]] || {
  echo "Checked-out commit mismatch" >&2; exit 2
}
[[ -z "$(git -C "$DEST" status --porcelain)" ]] || {
  echo "Source checkout is unexpectedly dirty" >&2; exit 2
}
echo "PASS: pinned clean source checkout $SHA, existing LIVE data untouched."
