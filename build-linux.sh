#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "Build on x86_64 Linux; cross-compiling the backend is not supported."
  exit 1
fi

for command in npm node curl sha256sum tar; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command"
    exit 1
  fi
done

if [[ -n "${PYTHON:-}" ]]; then
  case "$PYTHON" in
    .venv/bin/python|.venv/bin/python3|"$PWD"/.venv/bin/python|"$PWD"/.venv/bin/python3) ;;
    *) "$PYTHON" -m venv .venv ;;
  esac
elif [[ ! -x .venv/bin/python ]]; then
  BASE_PYTHON="$(command -v python3.12 || command -v python3 || true)"
  if [[ -z "$BASE_PYTHON" ]]; then
    echo "Python 3.10+ with venv support is required (3.12 recommended)."
    exit 1
  fi
  "$BASE_PYTHON" -m venv .venv
fi
PYTHON="$PWD/.venv/bin/python"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
# Use the same package version as Electron Packager for the archive name.
VERSION="$(node -p 'require("./desktop/package.json").version')"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Expected a three-part release version in desktop/package.json."
  exit 1
fi

echo "[1/5] Installing Python build dependencies..."
# Prefer CPU wheels. If a source build is needed, avoid host-specific CPU flags.
CMAKE_ARGS="-DGGML_CUDA=OFF -DGGML_NATIVE=OFF" \
  "$PYTHON" -m pip install --disable-pip-version-check --prefer-binary \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
  -e ".[desktop,summary,diarize]"

echo "[2/5] Fetching the modelshelf binary..."
# Verified against the official v0.2.0 release asset and its SHA-256 digest.
MODELSHELF_URL="https://github.com/KOIYAL/modelshelf/releases/download/v0.2.0/modelshelf-linux-x64"
MODELSHELF_SHA256="5cc7d53f67efca282287ebb73ee46c21c5ce70a9febca8bdfa70a928d6237cfe"
mkdir -p vendor
if ! echo "$MODELSHELF_SHA256  vendor/modelshelf" | sha256sum --check --status 2>/dev/null; then
  curl --fail --location --retry 3 --connect-timeout 15 --max-time 180 \
    "$MODELSHELF_URL" -o vendor/modelshelf.download
  echo "$MODELSHELF_SHA256  vendor/modelshelf.download" | sha256sum --check
  mv vendor/modelshelf.download vendor/modelshelf
fi
chmod +x vendor/modelshelf

# v0.2.0 requires glibc 2.39, newer than Ubuntu 22.04. Keep transcription
# usable on that runner and do not advertise an unusable summary engine.
BUNDLE_MODELSHELF=1
if ! vendor/modelshelf --version; then
  BUNDLE_MODELSHELF=0
  echo "NOTE: modelshelf cannot run on this host; omitting the summary CLI."
fi

echo "[3/5] Building the bundled backend..."
LT_BUNDLE_MODELSHELF="$BUNDLE_MODELSHELF" "$PYTHON" -m PyInstaller \
  --noconfirm --clean \
  --distpath dist/backend-linux \
  --workpath build/pyinstaller-linux \
  desktop/backend.spec

echo "[4/5] Packaging Electron for Linux x64..."
# Keep build caches writable even when the user's home is read-only.
export npm_config_cache="${npm_config_cache:-$PWD/build/npm-cache}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-$PWD/build/electron-cache}"
(
  cd desktop
  npm ci
  ./node_modules/.bin/electron-packager . LocalTranscriber \
    --platform=linux --arch=x64 --out=../dist/electron --overwrite --asar \
    --download.cacheRoot="$ELECTRON_CACHE" \
    --extra-resource=../dist/backend-linux/local-transcriber-backend
)

echo "[5/5] Creating the portable archive..."
APP_DIR="dist/electron/LocalTranscriber-linux-x64"
ARCHIVE="dist/LocalTranscriber-$VERSION-linux-x64.tar.gz"
# Electron Packager made the backend's symbolic links absolute (pointing at
# this build machine); point them back inside the package.
python3 scripts/relativize_backend_links.py \
  "$APP_DIR/resources/local-transcriber-backend" dist/backend-linux/local-transcriber-backend
cp START_HERE_LINUX.txt "$APP_DIR/START_HERE_LINUX.txt"
cp LICENSE "$APP_DIR/LICENSE-local-transcriber.txt"
# Keep the guide accurate for the actual build host, including local builds.
{
  echo
  echo "Build version: $VERSION"
  echo "Build host: $(getconf GNU_LIBC_VERSION)"
  echo "Bundled modelshelf: $BUNDLE_MODELSHELF (1=yes, 0=no)"
} >> "$APP_DIR/START_HERE_LINUX.txt"
tar -czf "$ARCHIVE" -C dist/electron LocalTranscriber-linux-x64

echo "Linux build complete: $ARCHIVE"
