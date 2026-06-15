#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-.venv/bin/python3}"
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv .venv
fi

case "$(uname -m)" in
  arm64)
    ELECTRON_ARCH="arm64"
    ;;
  x86_64)
    ELECTRON_ARCH="x64"
    ;;
  *)
    echo "Unsupported Mac architecture: $(uname -m)"
    exit 1
    ;;
esac

echo "[1/5] Installing Python build dependencies..."
"$PYTHON" -m pip install --disable-pip-version-check -e ".[desktop]"

echo "[2/5] Building the bundled transcription backend..."
"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath dist/backend-macos \
  --workpath build/pyinstaller-macos \
  desktop/backend.spec

echo "[3/5] Installing Electron dependencies..."
(
  cd desktop
  npm install
)

echo "[4/5] Building the macOS application..."
PACKAGER_ARGS=(
  "."
  "LocalTranscriber"
  "--platform=darwin"
  "--arch=$ELECTRON_ARCH"
  "--out=../dist/electron"
  "--overwrite"
  "--asar"
  "--extra-resource=../dist/backend-macos/local-transcriber-backend"
  "--app-bundle-id=com.koiyal.localtranscriber"
  "--app-category-type=public.app-category.productivity"
)

if [[ -n "${MAC_CODESIGN_IDENTITY:-}" ]]; then
  PACKAGER_ARGS+=(
    "--osx-sign.identity=$MAC_CODESIGN_IDENTITY"
    "--osx-sign.entitlements=entitlements.mac.plist"
    "--osx-sign.entitlements-inherit=entitlements.mac.plist"
  )
else
  echo "Warning: MAC_CODESIGN_IDENTITY is not set. Creating an unsigned test build."
fi

(
  cd desktop
  ./node_modules/.bin/electron-packager "${PACKAGER_ARGS[@]}"
)

APP_PATH="dist/electron/LocalTranscriber-darwin-$ELECTRON_ARCH/LocalTranscriber.app"
DMG_PATH="dist/LocalTranscriber-macOS-$ELECTRON_ARCH.dmg"
DMG_STAGE="build/dmg-macos-$ELECTRON_ARCH"

echo "[5/5] Creating the DMG..."
rm -rf "$DMG_STAGE"
mkdir -p "$DMG_STAGE"
ditto "$APP_PATH" "$DMG_STAGE/LocalTranscriber.app"
ln -s /Applications "$DMG_STAGE/Applications"
hdiutil create \
  -volname "Local Transcriber" \
  -srcfolder "$DMG_STAGE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

if [[ -n "${MAC_CODESIGN_IDENTITY:-}" ]]; then
  codesign --verify --deep --strict --verbose=2 "$APP_PATH"
fi

if [[ -n "${MAC_NOTARY_PROFILE:-}" ]]; then
  if [[ -z "${MAC_CODESIGN_IDENTITY:-}" ]]; then
    echo "MAC_NOTARY_PROFILE requires MAC_CODESIGN_IDENTITY."
    exit 1
  fi
  xcrun notarytool submit "$DMG_PATH" \
    --keychain-profile "$MAC_NOTARY_PROFILE" \
    --wait
  xcrun stapler staple "$DMG_PATH"
  xcrun stapler validate "$DMG_PATH"
fi

echo
echo "Mac build complete:"
echo "  $APP_PATH"
echo "  $DMG_PATH"
