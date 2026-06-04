#!/usr/bin/env bash
# Build an AppImage from the PyInstaller onedir output
# Usage: bash installer/linux/build-appimage.sh <version>
# Produces: release/VajraStocks.AppImage
# Requires: appimagetool available (downloaded automatically if missing)

set -euo pipefail

VERSION="${1:?Usage: build-appimage.sh <version>}"
DIST_SRC="dist/VajraStocks"
RELEASE_DIR="release"
APPDIR="AppDir"

echo "Building AppImage for version ${VERSION}"

# ── Download appimagetool if needed ───────────────────────────────────────────
APPIMAGETOOL="./appimagetool-x86_64.AppImage"
if [[ ! -f "${APPIMAGETOOL}" ]]; then
  echo "Downloading appimagetool..."
  curl -sL "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
    -o "${APPIMAGETOOL}"
  chmod +x "${APPIMAGETOOL}"
fi

# ── AppDir layout ─────────────────────────────────────────────────────────────
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

cp -r "${DIST_SRC}/." "${APPDIR}/usr/bin/"
chmod +x "${APPDIR}/usr/bin/VajraStocks"

# ── AppRun entry point ────────────────────────────────────────────────────────
cat > "${APPDIR}/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/VajraStocks" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# ── Desktop entry ─────────────────────────────────────────────────────────────
cat > "${APPDIR}/vajrastocks.desktop" << EOF
[Desktop Entry]
Name=VajraStocks
Comment=NSE Stock Analysis Platform
Exec=VajraStocks
Icon=vajrastocks
Terminal=false
Type=Application
Categories=Finance;
EOF

# ── Icon ──────────────────────────────────────────────────────────────────────
if [[ -f "installer/assets/icon.png" ]]; then
  cp installer/assets/icon.png "${APPDIR}/vajrastocks.png"
  cp installer/assets/icon.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/vajrastocks.png"
else
  # Create a minimal placeholder icon so appimagetool doesn't fail
  if command -v convert &>/dev/null; then
    convert -size 256x256 xc:'#1a1a2e' -fill '#e94560' \
      -font DejaVu-Sans-Bold -pointsize 80 -gravity center \
      -annotate 0 "VS" "${APPDIR}/vajrastocks.png" 2>/dev/null || touch "${APPDIR}/vajrastocks.png"
  else
    touch "${APPDIR}/vajrastocks.png"
  fi
fi

# ── Build AppImage ─────────────────────────────────────────────────────────────
mkdir -p "${RELEASE_DIR}"
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${RELEASE_DIR}/VajraStocks.AppImage"
chmod +x "${RELEASE_DIR}/VajraStocks.AppImage"
rm -rf "${APPDIR}"

echo "Built: ${RELEASE_DIR}/VajraStocks.AppImage"
