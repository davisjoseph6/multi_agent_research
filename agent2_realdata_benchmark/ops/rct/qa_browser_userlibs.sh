#!/usr/bin/env bash
# Developer QA only. Extract missing Chromium libraries from the configured OS package
# repository into a user-owned cache; never use this wrapper to run the live study.
set -e
# Ubuntu 24.04 renamed several runtime packages during the time64 transition.
# Resolve concrete distro packages through apt metadata rather than downloading
# virtual packages such as libasound2 (no candidate on Noble).
if ! command -v apt-get >/dev/null || ! command -v dpkg-deb >/dev/null ||
   ! command -v apt-cache >/dev/null; then
  echo "Requires Ubuntu/Debian apt-get, apt-cache and dpkg-deb; ask the administrator for Playwright dependencies." >&2
  exit 2
fi

apt_has_candidate() {
  local package="$1" candidate
  candidate="$(apt-cache policy "$package" 2>/dev/null |
    awk '$1 == "Candidate:" { print $2; exit }')"
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

resolve_package() {
  local library="$1" choices pkg
  case "$library" in
    libnspr4.so) choices="libnspr4";;
    libnss3.so|libnssutil3.so|libsmime3.so|libssl3.so) choices="libnss3";;
    libatk-1.0.so.0) choices="libatk1.0-0t64 libatk1.0-0";;
    libatk-bridge-2.0.so.0) choices="libatk-bridge2.0-0t64 libatk-bridge2.0-0";;
    libatspi.so.0) choices="libatspi2.0-0t64 libatspi2.0-0";;
    libcups.so.2) choices="libcups2t64 libcups2";;
    libxkbcommon.so.0) choices="libxkbcommon0";;
    libXcomposite.so.1) choices="libxcomposite1";;
    libXdamage.so.1) choices="libxdamage1";;
    libXfixes.so.3) choices="libxfixes3";;
    libXrandr.so.2) choices="libxrandr2";;
    libgbm.so.1) choices="libgbm1";;
    libdrm.so.2) choices="libdrm2";;
    libpango-1.0.so.0) choices="libpango-1.0-0";;
    libcairo.so.2) choices="libcairo2";;
    libasound.so.2) choices="libasound2t64 libasound2";;
    libX11-xcb.so.1) choices="libx11-xcb1";;
    libX11.so.6) choices="libx11-6";;
    libxcb.so.1) choices="libxcb1";;
    libxshmfence.so.1) choices="libxshmfence1";;
    libdbus-1.so.3) choices="libdbus-1-3";;
    libglib-2.0.so.0|libgobject-2.0.so.0) choices="libglib2.0-0t64 libglib2.0-0";;
    libfontconfig.so.1) choices="libfontconfig1";;
    libexpat.so.1) choices="libexpat1";;
    *) echo "Unknown browser library: $library; request OS package support." >&2; return 3;;
  esac
  for pkg in $choices; do
    if apt_has_candidate "$pkg"; then
      printf '%s\n' "$pkg"
      return 0
    fi
  done
  echo "No installable OS package in apt metadata for $library (tried: $choices)." >&2
  echo "Check /etc/os-release and apt-cache policy, or ask the OS administrator for Playwright dependencies." >&2
  return 3
}

# Diagnostic mode can be tested without Playwright, root, or a network call.
if [ "${1:-}" = "--resolve-package" ]; then
  if [ "$#" -ne 2 ]; then
    echo "Usage: bash qa_browser_userlibs.sh --resolve-package libasound.so.2" >&2
    exit 2
  fi
  resolve_package "$2"
  exit $?
fi

if [ "$#" -eq 0 ]; then
  echo "Usage: bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --out /tmp/rct_chromium_02.json" >&2
  exit 2
fi
BROWSER="$(find "$HOME/.cache/ms-playwright" -path '*/chrome-headless-shell-linux64/chrome-headless-shell' -type f | sort | tail -n 1)"
if [ -z "$BROWSER" ]; then
  echo "Headless Chromium not installed. Run: python -m playwright install chromium" >&2
  exit 2
fi
CACHE="$HOME/.cache/ijcai-rct-qa-browser-libs"
mkdir -p "$CACHE/debs" "$CACHE/root"
ARCH="$(uname -m)-linux-gnu"
LD_LIBRARY_PATH="$CACHE/root/usr/lib/$ARCH:$CACHE/root/lib/$ARCH:${LD_LIBRARY_PATH:-}"
export LD_LIBRARY_PATH
attempt=0
while [ "$attempt" -lt 6 ]; do
  attempt=$((attempt+1))
  missing="$(ldd "$BROWSER" | awk '/=> not found/ {print $1}' | sort -u)"
  if [ -z "$missing" ]; then
    echo "All Chromium headless-shell shared-library names resolved."
    exec "$@"
  fi
  echo "Missing shared libraries:"
  printf '%s\n' "$missing"
  packages=()
  declare -A seen=()
  for lib in $missing; do
    pkg="$(resolve_package "$lib")" || exit 3
    if [ -z "${seen[$pkg]:-}" ]; then
      packages+=("$pkg")
      seen["$pkg"]=1
    fi
  done
  # Keep package provenance tied to configured OS repositories. This requires
  # working apt metadata and network access but no root privileges.
  echo "Attempting user-local extraction of: ${packages[*]}"
  if ! (cd "$CACHE/debs" && apt-get download "${packages[@]}"); then
    echo "apt-get download failed. Inspect apt-cache policy, repository access and OS compatibility; no sudo workaround is attempted." >&2
    exit 3
  fi
  for archive in "$CACHE/debs"/*.deb; do
    [ -f "$archive" ] || continue
    dpkg-deb -x "$archive" "$CACHE/root"
  done
done
echo "Unresolved dependencies after six passes. Ask the system administrator to run: python -m playwright install-deps chromium" >&2
exit 3
