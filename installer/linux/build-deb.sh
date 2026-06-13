#!/usr/bin/env bash
# Build a .deb package from the PyInstaller onedir output
# Usage: bash installer/linux/build-deb.sh <version>
# Produces: release/VajraStocks.deb

set -euo pipefail

VERSION="${1:?Usage: build-deb.sh <version>}"
PKG_NAME="vajrastocks"
ARCH="amd64"
DIST_SRC="dist/VajraStocks"
STAGE="staging-deb/${PKG_NAME}_${VERSION}_${ARCH}"
RELEASE_DIR="release"

echo "Building .deb for version ${VERSION}"

# ── Stage directory layout ────────────────────────────────────────────────────
rm -rf staging-deb
mkdir -p "${STAGE}/DEBIAN"
mkdir -p "${STAGE}/opt/vajrastocks"
mkdir -p "${STAGE}/usr/share/applications"
mkdir -p "${STAGE}/usr/share/pixmaps"
mkdir -p "${STAGE}/usr/bin"

# ── Copy application files ────────────────────────────────────────────────────
cp -r "${DIST_SRC}/." "${STAGE}/opt/vajrastocks/"
chmod +x "${STAGE}/opt/vajrastocks/VajraStocks"

# ── Launcher symlink ──────────────────────────────────────────────────────────
cat > "${STAGE}/usr/bin/vajrastocks" << 'EOF'
#!/usr/bin/env bash
exec /opt/vajrastocks/VajraStocks "$@"
EOF
chmod +x "${STAGE}/usr/bin/vajrastocks"

# ── Desktop entry ─────────────────────────────────────────────────────────────
cat > "${STAGE}/usr/share/applications/vajrastocks.desktop" << EOF
[Desktop Entry]
Name=VajraStocks
Comment=NSE Stock Analysis Platform
Exec=/opt/vajrastocks/VajraStocks
Icon=vajrastocks
Terminal=false
Type=Application
Categories=Finance;
StartupNotify=true
EOF

# ── Copy icon if present ──────────────────────────────────────────────────────
if [[ -f "installer/assets/icon.png" ]]; then
  cp installer/assets/icon.png "${STAGE}/usr/share/pixmaps/vajrastocks.png"
fi

# ── DEBIAN/control ────────────────────────────────────────────────────────────
INSTALLED_SIZE=$(du -sk "${STAGE}/opt/vajrastocks" | cut -f1)
cat > "${STAGE}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: finance
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Abhishek <noreply@github.com>
Description: VajraStocks NSE Stock Analysis Platform
 A desktop application for NSE stock screening, charting,
 and technical analysis powered by a FastAPI backend.
EOF

# ── DEBIAN/postinst ────────────────────────────────────────────────────────────
cat > "${STAGE}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
chmod 755 "${STAGE}/DEBIAN/postinst"

# ── DEBIAN/prerm ──────────────────────────────────────────────────────────────
cat > "${STAGE}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e
if pgrep -x "VajraStocks" >/dev/null; then
    echo "Stopping active VajraStocks processes before package modification..."
    pkill -x "VajraStocks" || true
    sleep 1
fi
EOF
chmod 755 "${STAGE}/DEBIAN/prerm"

# ── Build .deb ─────────────────────────────────────────────────────────────────
mkdir -p "${RELEASE_DIR}"
dpkg-deb --build --root-owner-group "${STAGE}" "${RELEASE_DIR}/VajraStocks.deb"
rm -rf staging-deb

echo "Built: ${RELEASE_DIR}/VajraStocks.deb"
