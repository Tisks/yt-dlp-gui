#!/bin/bash
# Populates vendor/mac/ with the external tools the app ships, plus every
# Homebrew dylib they depend on, rewritten to load from @executable_path/../lib.
#
# Requires: brew install yt-dlp ffmpeg deno dylibbundler
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"

VENDOR="vendor/mac"
TOOLS=(yt-dlp ffmpeg ffprobe deno)

rm -rf "$VENDOR"
mkdir -p "$VENDOR/bin" "$VENDOR/lib"

for tool in "${TOOLS[@]}"; do
  src="$(command -v "$tool")" || { echo "Error: $tool not found on PATH"; exit 1; }
  cp "$src" "$VENDOR/bin/$tool"
done
chmod +x "$VENDOR"/bin/*

# One invocation for all three: dylibbundler's -od wipes the output directory on
# every run, so separate calls would leave only the last tool's libraries behind.
dylibbundler -od -b \
  -x "$VENDOR/bin/ffmpeg" \
  -x "$VENDOR/bin/ffprobe" \
  -x "$VENDOR/bin/deno" \
  -d "$VENDOR/lib" \
  -p "@executable_path/../lib/"

echo
echo "Vendored into $VENDOR:"
ls "$VENDOR/bin"
echo "$(ls "$VENDOR/lib" | wc -l | tr -d ' ') bundled libraries"
