#!/usr/bin/env bash
# Build SlideAnnotator and package it as an AppImage.
#
# Usage: packaging/build_linux.sh
#
# StarDist nuclei detection is unavailable on Linux: its NMS extension is a
# prebuilt macOS/arm64 binary. The app degrades with a message (see
# slideannotator/inference/nms.py).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import re,pathlib; print(re.search(r'__version__ = \"(.*)\"', pathlib.Path('slideannotator/__init__.py').read_text()).group(1))")"
APPIMAGE="dist/SlideAnnotator-${VERSION}-x86_64.AppImage"

echo "==> Building SlideAnnotator ${VERSION} (linux x86_64)"

echo "==> Rendering icons"
QT_QPA_PLATFORM=offscreen uv run python packaging/make_icons.py

echo "==> Running PyInstaller"
rm -rf build dist
uv run pyinstaller packaging/slideannotator.spec --noconfirm

echo "==> Verifying the frozen build"
QT_QPA_PLATFORM=offscreen dist/SlideAnnotator/SlideAnnotator --self-test

echo "==> Assembling AppDir"
APPDIR=dist/SlideAnnotator.AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/512x512/apps"
cp -a dist/SlideAnnotator/. "$APPDIR/usr/bin/"
cp packaging/SlideAnnotator.png "$APPDIR/usr/share/icons/hicolor/512x512/apps/slideannotator.png"
cp packaging/SlideAnnotator.png "$APPDIR/slideannotator.png"

cat > "$APPDIR/usr/share/applications/slideannotator.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SlideAnnotator
Comment=Histological slide annotation tool for mIF images
Exec=SlideAnnotator
Icon=slideannotator
Categories=Science;MedicalSoftware;Graphics;
Terminal=false
EOF
cp "$APPDIR/usr/share/applications/slideannotator.desktop" "$APPDIR/slideannotator.desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/SlideAnnotator" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> Building AppImage"
TOOL=dist/appimagetool
if [ ! -x "$TOOL" ]; then
    curl -sSfL -o "$TOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
# --appimage-extract-and-run: CI runners have no FUSE.
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE"

echo
echo "Built $APPIMAGE ($(du -h "$APPIMAGE" | cut -f1))"
