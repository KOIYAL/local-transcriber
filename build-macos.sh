#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The Mac app must be built on macOS."
  exit 1
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1"
    exit 1
  fi
}

python_is_supported() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    >/dev/null 2>&1
}

find_supported_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      local executable
      executable="$(command -v "$candidate")"
      if python_is_supported "$executable"; then
        echo "$executable"
        return 0
      fi
    fi
  done
  return 1
}

require_command npm
require_command ditto
require_command hdiutil

if [[ -n "${PYTHON:-}" ]]; then
  if [[ ! -x "$PYTHON" ]]; then
    echo "PYTHON points to a missing or non-executable file: $PYTHON"
    exit 1
  fi
  if ! python_is_supported "$PYTHON"; then
    echo "Python 3.10 or newer is required, but $PYTHON is older."
    exit 1
  fi
  case "$PYTHON" in
    .venv/bin/python|.venv/bin/python3|"$PWD"/.venv/bin/python|"$PWD"/.venv/bin/python3)
      ;;
    *)
      "$PYTHON" -m venv .venv
      PYTHON=".venv/bin/python3"
      ;;
  esac
elif [[ -x ".venv/bin/python3" ]]; then
  PYTHON=".venv/bin/python3"
else
  BASE_PYTHON="$(find_supported_python || true)"
  if [[ -z "$BASE_PYTHON" ]]; then
    echo "Python 3.10 or newer is required. Install it first, then rerun ./build-macos.sh."
    exit 1
  fi
  "$BASE_PYTHON" -m venv .venv
  PYTHON=".venv/bin/python3"
fi

if ! python_is_supported "$PYTHON"; then
  echo "Python 3.10 or newer is required, but $PYTHON is older."
  echo "Set PYTHON=/path/to/python3.10+ or recreate .venv with a supported Python."
  exit 1
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
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
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
  "--icon=../assets/app-icon.icns"
  "--extra-resource=../dist/backend-macos/local-transcriber-backend"
  "--app-bundle-id=com.koiyal.localtranscriber"
  "--app-category-type=public.app-category.productivity"
)

if [[ -n "${MAC_CODESIGN_IDENTITY:-}" ]]; then
  PACKAGER_ARGS+=(
    "--osx-sign.identity=$MAC_CODESIGN_IDENTITY"
    "--osx-sign.hardenedRuntime=true"
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
cp START_HERE_MAC.txt "$DMG_STAGE/START_HERE_MAC.txt"
ln -s /Applications "$DMG_STAGE/Applications"
hdiutil create \
  -volname "Local Transcriber" \
  -srcfolder "$DMG_STAGE" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

if [[ -n "${MAC_CODESIGN_IDENTITY:-}" ]]; then
  codesign --verify --deep --strict --verbose=2 "$APP_PATH"
  codesign --sign "$MAC_CODESIGN_IDENTITY" --timestamp "$DMG_PATH"
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
