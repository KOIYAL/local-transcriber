#!/bin/bash
# Ad-hoc sign the unsigned macOS app so its signature verifies.
#
# Electron Packager leaves Electron's original signature over a bundle it has
# renamed and filled with the PyInstaller backend (Contents/Resources). That
# bundle fails `codesign --verify` and macOS calls the download "damaged".
# `codesign --deep` alone is not enough: it does not treat the backend's
# Mach-O files in Resources as nested code. So, inside out:
#   1. stop if a symbolic link still points outside the bundle (codesign rejects them)
#   2. sign every Mach-O file in Resources, deepest first
#   3. sign the whole app (frameworks and helpers via --deep)
#
# Usage: [PYTHON=path/to/python3] scripts/adhoc_sign_macos.sh path/to/LocalTranscriber.app
set -euo pipefail
PYTHON="${PYTHON:-python3}"

APP="$1"
APP_REAL="$(cd "$APP" && pwd -P)"

echo "Checking symbolic links that leave the bundle..."
# relativize_backend_links.py runs first; anything left here would make
# codesign reject the bundle, so stop with a clear message instead.
leaving=0
while IFS= read -r -d '' link; do
  resolved="$("$PYTHON" -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$link")"
  case "$resolved" in
    "$APP_REAL"/*) continue ;;
  esac
  echo "  link leaves the bundle: $link -> $(readlink "$link")"
  leaving=1
done < <(find "$APP" -type l -print0)
if [[ "$leaving" -ne 0 ]]; then
  echo "Fix the links above before signing."
  exit 1
fi

echo "Signing Mach-O files in Resources..."
count=0
while IFS= read -r path; do
  if file -b "$path" | grep -q "Mach-O"; then
    codesign --force --sign - "$path"
    count=$((count + 1))
  fi
done < <(find "$APP/Contents/Resources" -type f | awk -F/ '{ print NF "\t" $0 }' | sort -rn | cut -f2-)
echo "  signed $count file(s)"

echo "Signing the app bundle..."
codesign --force --deep --sign - "$APP"
