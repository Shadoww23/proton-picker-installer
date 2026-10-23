#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION="$(python3 -c 'import core; print(core.VERSION)')"
NFPM="${NFPM:-nfpm}"

if ! command -v "$NFPM" >/dev/null 2>&1; then
  echo "nfpm is required: https://nfpm.goreleaser.com/install/" >&2
  exit 1
fi

python3 build/make_icon.py

ROOT="build/pkgroot"
rm -rf "$ROOT" dist/packages
mkdir -p \
  "$ROOT/usr/bin" \
  "$ROOT/usr/lib/proton-picker-setup" \
  "$ROOT/usr/share/applications" \
  "$ROOT/usr/share/icons/hicolor/512x512/apps" \
  "$ROOT/usr/share/doc/proton-picker-setup" \
  "$ROOT/usr/share/licenses/proton-picker-setup" \
  dist/packages

install -m644 main.py core.py build/icon.png "$ROOT/usr/lib/proton-picker-setup/"
install -m644 build/proton-picker-setup.desktop "$ROOT/usr/share/applications/"
install -m644 build/icon.png "$ROOT/usr/share/icons/hicolor/512x512/apps/proton-picker-setup.png"
install -m644 LICENSE "$ROOT/usr/share/doc/proton-picker-setup/LICENSE"
install -m644 README.md "$ROOT/usr/share/doc/proton-picker-setup/README.md"
install -m644 LICENSE "$ROOT/usr/share/licenses/proton-picker-setup/LICENSE"

cat > "$ROOT/usr/bin/proton-picker-setup" <<'EOF'
#!/bin/sh
exec python3 /usr/lib/proton-picker-setup/main.py "$@"
EOF
chmod 755 "$ROOT/usr/bin/proton-picker-setup"

sed "s/__VERSION__/$VERSION/g" build/nfpm.yaml.template > build/nfpm.yaml
"$NFPM" package --config build/nfpm.yaml --packager deb --target dist/packages/
"$NFPM" package --config build/nfpm.yaml --packager rpm --target dist/packages/

cd dist/packages
sha256sum *.deb *.rpm > SHA256SUMS-packages
ls -lh
