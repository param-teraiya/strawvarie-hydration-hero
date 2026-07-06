#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This build script is for macOS only."
  exit 1
fi

PYTHON="${ROOT}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
  PYTHON="${ROOT}/venv/bin/python"
fi

echo "Installing dependencies..."
"$PYTHON" -m pip install -q -r requirements.txt -r requirements-build.txt

echo "Ensuring default hero frames..."
"$PYTHON" scripts/extract_default_frames.py

echo "Building Strawvarie Hydration Hero.app ..."
"$PYTHON" -m PyInstaller hydration_hero.spec --noconfirm --clean

APP_PATH="${ROOT}/dist/Strawvarie Hydration Hero.app"
ZIP_PATH="${ROOT}/dist/Strawvarie-Hydration-Hero-mac.zip"

echo "Creating zip for sharing..."
rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"

echo
echo "Done!"
echo "  App: ${APP_PATH}"
echo "  Zip: ${ZIP_PATH}"
echo
echo "Send your friend the zip file."
echo "They unzip it, double-click the app, and if Mac blocks it:"
echo "  Right-click -> Open -> Open"
