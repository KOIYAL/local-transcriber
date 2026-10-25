#!/bin/bash
# Ad-hoc sign the unsigned macOS app so its signature verifies.
#
# Electron Packager leaves Electron's original signature over a bundle it has
# renamed and filled with the PyInstaller backend (Contents/Resources). That
# bundle fails `codesign --verify` and macOS calls the download "damaged".
# `codesign --deep` alone is not enough: it does not treat the backend's
# Mach-O files in Resources as nested code. So, inside out:
#   1. fix symbolic links that point outside the bundle (codesign rejects them)
#   2. sign every Mach-O file in Resources, deepest first
#   3. sign the whole app (frameworks and helpers via --deep)
#
# Usage: scripts/adhoc_sign_macos.sh path/to/LocalTranscriber.app
set -euo pipefail

APP="$1"
APP_REAL="$(cd "$APP" && pwd -P)"

echo "Checking symbolic links that leave the bundle..."
while IFS= read -r -d '' link; do
  target="$(readlink "$link")"
  resolved="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$link")"
  case "$resolved" in
    "$APP_REAL"/*) continue ;;
  esac
  if [[ -e "$resolved" ]]; then
    echo "  copying in: $link -> $target"
    rm "$link"
    cp -R "$resolved" "$link"
  else
    echo "  removing dangling link: $link -> $target"
    rm "$link"
  fi
done < <(find "$APP" -type l -print0)

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
