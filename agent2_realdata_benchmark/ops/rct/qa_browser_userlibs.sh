#!/usr/bin/env bash
# Developer QA only. Extract missing Chromium libraries from the configured OS package
# repository into a user-owned cache; never use this wrapper to run the live study.
set -e
if [ "$#" -eq 0 ]; then
  echo "Usage: bash ops/rct/qa_browser_userlibs.sh python -m scripts.rct_browser_qa --out /tmp/rct_chromium_02.json" >&2
  exit 2
fi
if ! command -v apt-get >/dev/null || ! command -v dpkg-deb >/dev/null; then
  echo "Requires Ubuntu/Debian apt and dpkg; ask the Linux administrator for Playwright dependencies." >&2
  exit 2
fi
BROWSER="$(find "$HOME/.cache/ms-playwright" -path '*/chrome-headless-shell-linux64/chrome-headless-shell' -type f | sort | tail -n 1)"
if [ -z "$BROWSER" ]; then
  echo "Headless Chromium not installed. Run: python -m playwright install chromium" >&2
  exit 2
fi
CACHE="$HOME/.cache/ijcai-rct-qa-browser-libs"
mkdir -p "$CACHE/debs" "$CACHE/root"
ARCH="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
LD_LIBRARY_PATH="$CACHE/root/usr/lib/$ARCH:$CACHE/root/lib/$ARCH:$LD_LIBRARY_PATH"
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
  packages=""
  for lib in $missing; do
    case "$lib" in
      libnspr4.so) pkg=libnspr4;;
      libnss3.so|libnssutil3.so|libsmime3.so|libssl3.so) pkg=libnss3;;
      libatk-1.0.so.0) pkg=libatk1.0-0;;
      libatk-bridge-2.0.so.0) pkg=libatk-bridge2.0-0;;
      libatspi.so.0) pkg=libatspi2.0-0;;
      libcups.so.2) pkg=libcups2;;
      libxkbcommon.so.0) pkg=libxkbcommon0;;
      libXcomposite.so.1) pkg=libxcomposite1;;
      libXdamage.so.1) pkg=libxdamage1;;
      libXfixes.so.3) pkg=libxfixes3;;
      libXrandr.so.2) pkg=libxrandr2;;
      libgbm.so.1) pkg=libgbm1;;
      libdrm.so.2) pkg=libdrm2;;
      libpango-1.0.so.0) pkg=libpango-1.0-0;;
      libcairo.so.2) pkg=libcairo2;;
      libasound.so.2) pkg=libasound2;;
      libX11-xcb.so.1) pkg=libx11-xcb1;;
      libX11.so.6) pkg=libx11-6;;
      libxcb.so.1) pkg=libxcb1;;
      libxshmfence.so.1) pkg=libxshmfence1;;
      libdbus-1.so.3) pkg=libdbus-1-3;;
      libglib-2.0.so.0|libgobject-2.0.so.0) pkg=libglib2.0-0;;
      libfontconfig.so.1) pkg=libfontconfig1;;
      libexpat.so.1) pkg=libexpat1;;
      *) echo "Unknown $lib: request system package installation from administrator." >&2; exit 3;;
    esac
    packages="$packages $pkg"
  done
  # Keep package provenance tied to configured OS repositories. This requires
  # working apt metadata and network access but no root privileges.
  echo "Attempting user-local extraction of:$packages"
  (cd "$CACHE/debs" && apt-get download $packages)
  for archive in "$CACHE/debs"/*.deb; do
    [ -f "$archive" ] || continue
    dpkg-deb -x "$archive" "$CACHE/root"
  done
done
echo "Unresolved dependencies after six passes. Ask the system administrator to run: python -m playwright install-deps chromium" >&2
exit 3
