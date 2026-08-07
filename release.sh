#!/bin/bash
set -e
cd "$(dirname "$0")"
./.venv-build/bin/python3 -m PyInstaller yt-dlp-gui.spec --noconfirm 2>&1 | tail -20
osascript -e 'quit app "yt-dlp-gui"' 2>&1
sleep 1
pgrep -fl "yt-dlp-gui.app" || echo "not running"
rm -rf "/Applications/yt-dlp-gui.app"
cp -R "$(pwd)/dist/yt-dlp-gui.app" "/Applications/yt-dlp-gui.app"
ls -la "/Applications/yt-dlp-gui.app/Contents/MacOS"
