#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
VERSION="${1:-$(grep 'CURRENT_VERSION = ' "$SCRIPT_DIR/updater.py" | cut -d '"' -f 2)}"
ARCHIVE_NAME="dynamic-island-v${VERSION}-linux-x86_64.tar.gz"

echo "=== Building Standalone Dynamic Island Linux Release ==="

mkdir -p "$DIST_DIR" "$BUILD_DIR"

pyinstaller \
  --name dynamic-island \
  --onedir \
  --noconfirm \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR" \
  --add-data "$SCRIPT_DIR/fonts:fonts" \
  --hidden-import gi.repository.Gtk \
  --hidden-import gi.repository.Gdk \
  --hidden-import gi.repository.Gio \
  --hidden-import gi.repository.GLib \
  --hidden-import gi.repository.Gtk4LayerShell \
  --exclude-module PyQt6 \
  --exclude-module PyQt5 \
  --exclude-module PySide6 \
  --exclude-module pygame \
  --exclude-module numpy \
  --exclude-module matplotlib \
  --exclude-module torch \
  --exclude-module transformers \
  --exclude-module scipy \
  --exclude-module pandas \
  --exclude-module yt_dlp \
  "$SCRIPT_DIR/dynamic_island.py"

cd "$DIST_DIR"
tar --use-compress-program="gzip -1" -cf "$SCRIPT_DIR/$ARCHIVE_NAME" dynamic-island

echo "=== Build Complete! ==="
echo "Archive: $SCRIPT_DIR/$ARCHIVE_NAME"
ls -lh "$SCRIPT_DIR/$ARCHIVE_NAME"
