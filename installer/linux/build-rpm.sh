#!/usr/bin/env bash
# Build an .rpm package from the PyInstaller onedir output
# Usage: bash installer/linux/build-rpm.sh <version>
# Produces: release/VajraStocks.rpm

set -euo pipefail

VERSION="${1:?Usage: build-rpm.sh <version>}"
DIST_SRC="dist/VajraStocks"
RELEASE_DIR="release"
RPM_BUILD_DIR="$(pwd)/rpm-build"
HAS_ICON=0

echo "Building .rpm for version ${VERSION}"

# ── rpmbuild directory layout ─────────────────────────────────────────────────
rm -rf "${RPM_BUILD_DIR}"
mkdir -p "${RPM_BUILD_DIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# ── Pre-stage the app bundle directly in BUILD/ ───────────────────────────────
# We skip %prep / tarball extraction — just copy the binary bundle in.
APP_BUILD_DIR="${RPM_BUILD_DIR}/BUILD/vajrastocks-${VERSION}"
mkdir -p "${APP_BUILD_DIR}"
cp -r "${DIST_SRC}/." "${APP_BUILD_DIR}/"
chmod +x "${APP_BUILD_DIR}/VajraStocks"

# ── Optional icon ─────────────────────────────────────────────────────────────
if [[ -f "installer/assets/icon.png" ]]; then
  cp installer/assets/icon.png "${RPM_BUILD_DIR}/SOURCES/vajrastocks.png"
  HAS_ICON=1
fi

# ── Conditional icon lines for spec ───────────────────────────────────────────
ICON_INSTALL_LINE=""
ICON_FILE_LINE=""
if [[ "${HAS_ICON}" -eq 1 ]]; then
  ICON_INSTALL_LINE="cp %{_topdir}/SOURCES/vajrastocks.png %{buildroot}/usr/share/pixmaps/"
  ICON_FILE_LINE="/usr/share/pixmaps/vajrastocks.png"
fi

# ── Spec file ─────────────────────────────────────────────────────────────────
cat > "${RPM_BUILD_DIR}/SPECS/vajrastocks.spec" << SPECEOF
Name:           vajrastocks
Version:        ${VERSION}
Release:        1%{?dist}
Summary:        NSE Stock Analysis Platform
License:        Proprietary
URL:            https://github.com/abhishek4official/VajraStocks
BuildArch:      x86_64

%description
A desktop application for NSE stock screening, charting,
and technical analysis powered by a FastAPI backend.

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/vajrastocks
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/pixmaps

# Copy the pre-staged bundle (no tarball / %prep needed)
cp -r %{_topdir}/BUILD/vajrastocks-${VERSION}/. %{buildroot}/opt/vajrastocks/
chmod +x %{buildroot}/opt/vajrastocks/VajraStocks

cat > %{buildroot}/usr/bin/vajrastocks << 'LAUNCHER'
#!/usr/bin/env bash
exec /opt/vajrastocks/VajraStocks "\$@"
LAUNCHER
chmod +x %{buildroot}/usr/bin/vajrastocks

${ICON_INSTALL_LINE}

cat > %{buildroot}/usr/share/applications/vajrastocks.desktop << 'DESKTOP'
[Desktop Entry]
Name=VajraStocks
Comment=NSE Stock Analysis Platform
Exec=/opt/vajrastocks/VajraStocks
Icon=vajrastocks
Terminal=false
Type=Application
Categories=Finance;
StartupNotify=true
DESKTOP

%files
/opt/vajrastocks/
/usr/bin/vajrastocks
/usr/share/applications/vajrastocks.desktop
${ICON_FILE_LINE}

%post
update-desktop-database /usr/share/applications 2>/dev/null || true

%preun
pkill -x VajraStocks 2>/dev/null || true
SPECEOF

# ── Build ─────────────────────────────────────────────────────────────────────
rpmbuild --define "_topdir ${RPM_BUILD_DIR}" \
         -bb "${RPM_BUILD_DIR}/SPECS/vajrastocks.spec"

mkdir -p "${RELEASE_DIR}"
find "${RPM_BUILD_DIR}/RPMS" -name "*.rpm" -exec cp {} "${RELEASE_DIR}/VajraStocks.rpm" \;
rm -rf "${RPM_BUILD_DIR}"

echo "Built: ${RELEASE_DIR}/VajraStocks.rpm"
