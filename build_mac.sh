#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "Strawvarie Hydration Hero — Mac build"
echo "======================================"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "ERROR: This build script is macOS only."
  echo "       PyInstaller cannot cross-compile a Mac .app from $(uname)."
  exit 1
fi

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  echo "Apple Silicon Mac detected (${ARCH}) — building a native ARM .app."
elif [[ "$ARCH" == "x86_64" ]]; then
  echo "Intel Mac detected (${ARCH}) — building an Intel .app."
else
  echo "Building for architecture: ${ARCH}"
fi

pick_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    if ! "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
      continue
    fi
    # macOS ships a stub python3 that opens the App Store — skip it.
    if "$candidate" -c "import sys" 2>&1 | grep -qi "install"; then
      continue
    fi
    echo "$candidate"
    return 0
  done
  return 1
}

PYTHON_CMD=""
if ! PYTHON_CMD="$(pick_python)"; then
  echo "ERROR: No usable Python 3.8+ found."
  echo
  echo "On a new MacBook (M1/M2/M3/M4/M5), install Python 3.12:"
  echo "  https://www.python.org/downloads/macos/"
  echo "  Choose the macOS 64-bit universal2 installer, then re-run ./build_mac.sh"
  echo
  echo "If pip later fails to compile packages, also run:"
  echo "  xcode-select --install"
  exit 1
fi

PY_VERSION="$("$PYTHON_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Using ${PYTHON_CMD} (Python ${PY_VERSION})"

PY_MINOR="$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.minor)')"
PY_MAJOR="$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.major)')"
if [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -ge 14 ]]; then
  echo "WARN: Python ${PY_VERSION} is very new."
  echo "      If the build fails, install Python 3.12 from python.org and run:"
  echo "      rm -rf venv && python3.12 -m venv venv && ./build_mac.sh"
fi

if [[ ! -f "$ROOT/heroes/male/default_hero.mp4" ]]; then
  echo "ERROR: Missing heroes/male/default_hero.mp4"
  echo "       Run: git pull"
  exit 1
fi

if [[ ! -f "$ROOT/assets/brand/strawvarie_logo.png" && ! -f "$ROOT/hydration_hero/assets/strawvarie_logo.png" ]]; then
  echo "ERROR: Missing logo asset. Run: git pull"
  exit 1
fi

PYTHON="${ROOT}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Creating virtual environment..."
  "$PYTHON_CMD" -m venv venv
  PYTHON="${ROOT}/venv/bin/python"
fi

echo "Installing dependencies..."
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt -r requirements-build.txt

echo "Checking Tkinter (required for the UI)..."
if ! "$PYTHON" -c "import tkinter; tkinter.Tk().destroy()" 2>/dev/null; then
  echo "ERROR: Tkinter is not available in this Python."
  echo "       Install Python from https://www.python.org/downloads/macos/ (not Homebrew-only)."
  echo "       Then: rm -rf venv && ./build_mac.sh"
  exit 1
fi

echo "Ensuring default hero frames (about 1 minute on first run)..."
if ! "$PYTHON" scripts/extract_default_frames.py; then
  echo "ERROR: Frame extraction failed."
  echo "       Try: $PYTHON scripts/extract_default_frames.py --force"
  exit 1
fi

FRAME_COUNT="$(
  find "$ROOT/heroes/male/frames" "$ROOT/heroes/male" -maxdepth 1 -name 'frame_*.png' 2>/dev/null | wc -l | tr -d ' '
)"
if [[ "$FRAME_COUNT" -lt 40 ]]; then
  echo "ERROR: Expected at least 40 hero frames, found ${FRAME_COUNT}."
  exit 1
fi

echo "Building Strawvarie Hydration Hero.app (this may take a few minutes)..."
"$PYTHON" -m PyInstaller hydration_hero.spec --noconfirm --clean

APP_PATH="${ROOT}/dist/Strawvarie Hydration Hero.app"
ZIP_PATH="${ROOT}/dist/Strawvarie-Hydration-Hero-mac.zip"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: Build finished but app bundle was not created."
  exit 1
fi

echo "Creating zip for sharing..."
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo
echo "Done!"
echo "  App: ${APP_PATH}"
echo "  Zip: ${ZIP_PATH}"
echo
if [[ "$ARCH" == "arm64" ]]; then
  echo "This ARM build runs on Apple Silicon Macs (M1/M2/M3/M4/M5)."
fi
echo "First launch if Mac blocks the app: Right-click -> Open -> Open"
