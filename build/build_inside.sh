#!/usr/bin/env bash
set -euo pipefail

cd /src
VERSION="$(python3 -c 'import core; print(core.VERSION)')"
APPIMAGE="ProtonPickerSetup-${VERSION}-x86_64.AppImage"

python3 build/make_icon.py

rm -rf build/appdir build/proton-picker-setup dist
mkdir -p build/appdir/ProtonPickerSetup.AppDir/usr/bin
pyinstaller \
  --noconfirm \
  --clean \
  --onefile \
  --windowed \
  --name proton-picker-setup \
  --icon build/icon.png \
  --add-data "build/icon.png:." \
  main.py

APPDIR="build/appdir/ProtonPickerSetup.AppDir"
cp dist/proton-picker-setup "$APPDIR/usr/bin/proton-picker-setup"
cp build/icon.png "$APPDIR/proton-picker-setup.png"
cp build/proton-picker-setup.desktop "$APPDIR/proton-picker-setup.desktop"
cp build/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/proton-picker-setup"
ln -sf proton-picker-setup.png "$APPDIR/.DirIcon"

curl -fsSL -o /tmp/appimagetool \
  https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x /tmp/appimagetool
mkdir -p /out
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 /tmp/appimagetool "$APPDIR" "/out/${APPIMAGE}"

cd /out
sha256sum "$APPIMAGE" > SHA256SUMS
