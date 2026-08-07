#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

DIST_DIR="dist/macos"
APP_PATH="$DIST_DIR/yt-dlp-gui.app"

./.venv-build/bin/python3 -m PyInstaller packaging/macos/yt-dlp-gui.spec \
  --noconfirm \
  --distpath "$DIST_DIR" \
  --workpath build/macos 2>&1 | tail -20

chmod +x "$PROJECT_ROOT/$APP_PATH/Contents/Frameworks/tools/bin/"*
codesign --force --deep --sign - "$PROJECT_ROOT/$APP_PATH"

osascript -e 'quit app "yt-dlp-gui"' 2>&1
sleep 1
pgrep -fl "yt-dlp-gui.app" || echo "not running"

rm -rf "/Applications/yt-dlp-gui.app"
cp -R "$PROJECT_ROOT/$APP_PATH" "/Applications/yt-dlp-gui.app"

ls -la "/Applications/yt-dlp-gui.app/Contents/MacOS"
