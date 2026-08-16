#!/usr/bin/env bash
# Build SlideAnnotator.app and package it as a .dmg.
#
# Usage: packaging/build_macos.sh
#
# Signs with a Developer ID and notarizes when these are set, otherwise falls
# back to an ad-hoc signature (which arm64 requires just to launch):
#   MACOS_CERTIFICATE        base64 of the Developer ID .p12
#   MACOS_CERTIFICATE_PWD    its password
#   MACOS_SIGN_IDENTITY      e.g. "Developer ID Application: Name (TEAMID)"
#   MACOS_NOTARY_KEY         base64 of the App Store Connect .p8 key
#   MACOS_NOTARY_KEY_ID      key id
#   MACOS_NOTARY_ISSUER      issuer uuid
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP="dist/SlideAnnotator.app"
VERSION="$(python3 -c "import re,pathlib; print(re.search(r'__version__ = \"(.*)\"', pathlib.Path('slideannotator/__init__.py').read_text()).group(1))")"
ARCH="$(uname -m)"
DMG="dist/SlideAnnotator-${VERSION}-macos-${ARCH}.dmg"

echo "==> Building SlideAnnotator ${VERSION} (${ARCH})"

echo "==> Rendering icons"
python3 -c "import PySide6" 2>/dev/null && python packaging/make_icons.py || \
  uv run python packaging/make_icons.py

echo "==> Running PyInstaller"
rm -rf build dist
uv run pyinstaller packaging/slideannotator.spec --noconfirm

echo "==> Signing"
if [ -n "${MACOS_SIGN_IDENTITY:-}" ]; then
    if [ -n "${MACOS_CERTIFICATE:-}" ]; then
        echo "    importing Developer ID certificate"
        KEYCHAIN="$RUNNER_TEMP/build.keychain"
        KEYCHAIN_PWD="$(uuidgen)"
        security create-keychain -p "$KEYCHAIN_PWD" "$KEYCHAIN"
        security set-keychain-settings -lut 21600 "$KEYCHAIN"
        security unlock-keychain -p "$KEYCHAIN_PWD" "$KEYCHAIN"
        echo "$MACOS_CERTIFICATE" | base64 --decode > "$RUNNER_TEMP/cert.p12"
        security import "$RUNNER_TEMP/cert.p12" -k "$KEYCHAIN" \
            -P "${MACOS_CERTIFICATE_PWD}" -T /usr/bin/codesign
        security set-key-partition-list -S apple-tool:,apple:,codesign: \
            -s -k "$KEYCHAIN_PWD" "$KEYCHAIN" >/dev/null
        security list-keychains -d user -s "$KEYCHAIN" login.keychain-db
        rm -f "$RUNNER_TEMP/cert.p12"
    fi
    codesign --force --deep --timestamp --options runtime \
        --entitlements packaging/entitlements.plist \
        --sign "$MACOS_SIGN_IDENTITY" "$APP"
else
    echo "    no MACOS_SIGN_IDENTITY: ad-hoc signing (users must bypass Gatekeeper)"
    codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict --verbose=2 "$APP"

echo "==> Building DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "SlideAnnotator ${VERSION}" -srcfolder "$STAGE" \
    -ov -format UDZO -fs HFS+ "$DMG"
rm -rf "$STAGE"

if [ -n "${MACOS_NOTARY_KEY:-}" ]; then
    echo "==> Notarizing"
    echo "$MACOS_NOTARY_KEY" | base64 --decode > "$RUNNER_TEMP/notary.p8"
    xcrun notarytool submit "$DMG" --wait \
        --key "$RUNNER_TEMP/notary.p8" \
        --key-id "$MACOS_NOTARY_KEY_ID" \
        --issuer "$MACOS_NOTARY_ISSUER"
    xcrun stapler staple "$DMG"
    rm -f "$RUNNER_TEMP/notary.p8"
else
    echo "==> Skipping notarization (no MACOS_NOTARY_KEY)"
fi

echo
echo "Built $DMG ($(du -h "$DMG" | cut -f1))"
