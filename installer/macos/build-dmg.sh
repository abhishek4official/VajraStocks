#!/usr/bin/env bash
# Build a macOS .dmg from the PyInstaller onedir output
# Usage: bash installer/macos/build-dmg.sh <version>
# Produces: release/VajraStocks.dmg
# Requires: create-dmg (brew install create-dmg)

set -euo pipefail

VERSION="${1:?Usage: build-dmg.sh <version>}"
APP_NAME="VajraStocks"
DIST_SRC="dist/VajraStocks"
RELEASE_DIR="release"
APP_BUNDLE="${APP_NAME}.app"
STAGING="staging-macos"

echo "Building macOS .dmg for version ${VERSION}"

# ── Create .app bundle ────────────────────────────────────────────────────────
rm -rf "${STAGING}"
mkdir -p "${STAGING}/${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${STAGING}/${APP_BUNDLE}/Contents/Resources"

cp -r "${DIST_SRC}/." "${STAGING}/${APP_BUNDLE}/Contents/MacOS/"
chmod +x "${STAGING}/${APP_BUNDLE}/Contents/MacOS/VajraStocks"

# ── Info.plist ────────────────────────────────────────────────────────────────
cat > "${STAGING}/${APP_BUNDLE}/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key>    <string>VajraStocks</string>
  <key>CFBundleExecutable</key>     <string>VajraStocks</string>
  <key>CFBundleIdentifier</key>     <string>com.abhishek.vajrastocks</string>
  <key>CFBundleName</key>           <string>VajraStocks</string>
  <key>CFBundlePackageType</key>    <string>APPL</string>
  <key>CFBundleShortVersionString</key> <string>${VERSION}</string>
  <key>CFBundleVersion</key>        <string>${VERSION}</string>
  <key>LSMinimumSystemVersion</key> <string>12.0</string>
  <key>NSHighResolutionCapable</key> <true/>
</dict>
</plist>
EOF

# ── Copy icon ─────────────────────────────────────────────────────────────────
if [[ -f "installer/assets/icon.icns" ]]; then
  cp installer/assets/icon.icns "${STAGING}/${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
  /usr/libexec/PlistBuddy -c \
    "Add :CFBundleIconFile string AppIcon" \
    "${STAGING}/${APP_BUNDLE}/Contents/Info.plist" 2>/dev/null || true
fi

# ── Install create-dmg if needed ──────────────────────────────────────────────
if ! command -v create-dmg &>/dev/null; then
  echo "Installing create-dmg via brew..."
  brew install create-dmg
fi

# ── Codesign .app Bundle ──────────────────────────────────────────────────────
if [[ -n "${MACOS_SIGNING_IDENTITY:-}" ]]; then
  echo "Signing macOS .app bundle using identity: ${MACOS_SIGNING_IDENTITY}"
  codesign --force --options runtime --deep --sign "${MACOS_SIGNING_IDENTITY}" "${STAGING}/${APP_BUNDLE}"
else
  echo "No codesigning identity provided (MACOS_SIGNING_IDENTITY is empty). Skipping signing."
fi

# ── Build DMG ─────────────────────────────────────────────────────────────────
mkdir -p "${RELEASE_DIR}"

create-dmg \
  --volname "VajraStocks ${VERSION}" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "${APP_BUNDLE}" 150 185 \
  --app-drop-link 450 185 \
  --no-internet-enable \
  "${RELEASE_DIR}/VajraStocks.dmg" \
  "${STAGING}/"

rm -rf "${STAGING}"
echo "Built: ${RELEASE_DIR}/VajraStocks.dmg"

# ── Notarize DMG ──────────────────────────────────────────────────────────────
if [[ -n "${APPLE_ID:-}" && -n "${APPLE_PASSWORD:-}" && -n "${APPLE_TEAM_ID:-}" ]]; then
  echo "Submitting DMG for Apple notarization..."
  xcrun notarytool submit "${RELEASE_DIR}/VajraStocks.dmg" \
    --apple-id "${APPLE_ID}" \
    --password "${APPLE_PASSWORD}" \
    --team-id "${APPLE_TEAM_ID}" \
    --wait
  
  echo "Stapling notarization ticket to DMG..."
  xcrun stapler staple "${RELEASE_DIR}/VajraStocks.dmg"
else
  echo "Apple notarization credentials not provided (APPLE_ID/APPLE_PASSWORD/APPLE_TEAM_ID is empty). Skipping notarization."
fi
