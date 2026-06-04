#!/usr/bin/env bash
# Build an AppImage from the PyInstaller onedir output
# Usage: bash installer/linux/build-appimage.sh <version>
# Produces: release/VajraStocks.AppImage
# appimagetool is downloaded automatically if missing
#
# NOTE: GitHub Actions runners need FUSE:
#   sudo apt-get install -y fuse libfuse2
# (already handled in the release workflow)

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
  curl -sL \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
    -o "${APPIMAGETOOL}"
  chmod +x "${APPIMAGETOOL}"
fi

# ── AppDir layout ─────────────────────────────────────────────────────────────
# Correct structure: app bundle goes in usr/lib/vajrastocks/,
# a thin wrapper script lives in usr/bin/ — NOT the whole bundle in usr/bin/.
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/lib/vajrastocks"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy entire PyInstaller onedir bundle into lib/
cp -r "${DIST_SRC}/." "${APPDIR}/usr/lib/vajrastocks/"
chmod +x "${APPDIR}/usr/lib/vajrastocks/VajraStocks"

# Thin launcher in usr/bin so PATH-based calls work
cat > "${APPDIR}/usr/bin/vajrastocks" << 'LAUNCHER'
#!/usr/bin/env bash
exec "$(dirname "$(readlink -f "$0")")/../lib/vajrastocks/VajraStocks" "$@"
LAUNCHER
chmod +x "${APPDIR}/usr/bin/vajrastocks"

# ── AppRun — required root-level entry point for AppImage ────────────────────
cat > "${APPDIR}/AppRun" << 'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/lib/vajrastocks/VajraStocks" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# ── Desktop entry (must be at AppDir root) ────────────────────────────────────
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
  # Generate a minimal placeholder so appimagetool doesn't abort
  if command -v convert &>/dev/null; then
    convert -size 256x256 xc:'#1a1a2e' -fill '#e94560' \
      -font DejaVu-Sans-Bold -pointsize 80 -gravity center \
      -annotate 0 "VS" "${APPDIR}/vajrastocks.png" 2>/dev/null || \
      cp /usr/share/pixmaps/gnome-panel.png "${APPDIR}/vajrastocks.png" 2>/dev/null || \
      touch "${APPDIR}/vajrastocks.png"
  else
    touch "${APPDIR}/vajrastocks.png"
  fi
  cp "${APPDIR}/vajrastocks.png" \
    "${APPDIR}/usr/share/icons/hicolor/256x256/apps/vajrastocks.png" 2>/dev/null || true
fi

# ── Build AppImage ────────────────────────────────────────────────────────────
mkdir -p "${RELEASE_DIR}"
ARCH=x86_64 "${APPIMAGETOOL}" "${APPDIR}" "${RELEASE_DIR}/VajraStocks.AppImage"
chmod +x "${RELEASE_DIR}/VajraStocks.AppImage"
rm -rf "${APPDIR}"

echo "Built: ${RELEASE_DIR}/VajraStocks.AppImage"
