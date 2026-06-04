#!/usr/bin/env bash
# Build an .rpm package from the PyInstaller onedir output
# Usage: bash installer/linux/build-rpm.sh <version>
# Produces: release/VajraStocks.rpm

set -euo pipefail

VERSION="${1:?Usage: build-rpm.sh <version>}"
RELEASE="1"
DIST_SRC="dist/VajraStocks"
RELEASE_DIR="release"
RPM_BUILD_DIR="rpm-build"

echo "Building .rpm for version ${VERSION}"

# ── rpmbuild directory layout ─────────────────────────────────────────────────
rm -rf "${RPM_BUILD_DIR}"
mkdir -p "${RPM_BUILD_DIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# ── Bundle sources ─────────────────────────────────────────────────────────────
TARBALL="${RPM_BUILD_DIR}/SOURCES/vajrastocks-${VERSION}.tar.gz"
tar -czf "${TARBALL}" -C "$(dirname "${DIST_SRC}")" "$(basename "${DIST_SRC}")" \
    --transform "s|^VajraStocks|vajrastocks-${VERSION}|"

# ── Icon ──────────────────────────────────────────────────────────────────────
if [[ -f "installer/assets/icon.png" ]]; then
  cp installer/assets/icon.png "${RPM_BUILD_DIR}/SOURCES/vajrastocks.png"
fi

# ── Spec file ─────────────────────────────────────────────────────────────────
cat > "${RPM_BUILD_DIR}/SPECS/vajrastocks.spec" << EOF
Name:           vajrastocks
Version:        ${VERSION}
Release:        ${RELEASE}%{?dist}
Summary:        NSE Stock Analysis Platform
License:        Proprietary
URL:            https://github.com/abhishek4official/VajraStocks
Source0:        vajrastocks-%{version}.tar.gz
Source1:        vajrastocks.png
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

cp -r %{_sourcedir}/../BUILD/vajrastocks-%{version}/. %{buildroot}/opt/vajrastocks/
chmod +x %{buildroot}/opt/vajrastocks/VajraStocks

cat > %{buildroot}/usr/bin/vajrastocks << 'LAUNCHER'
#!/usr/bin/env bash
exec /opt/vajrastocks/VajraStocks "\$@"
LAUNCHER
chmod +x %{buildroot}/usr/bin/vajrastocks

if [ -f %{_sourcedir}/vajrastocks.png ]; then
  cp %{_sourcedir}/vajrastocks.png %{buildroot}/usr/share/pixmaps/
fi

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
%{?_sourcedir:/usr/share/pixmaps/vajrastocks.png}

%post
update-desktop-database /usr/share/applications 2>/dev/null || true

%preun
pkill -x VajraStocks 2>/dev/null || true
EOF

# ── Build ─────────────────────────────────────────────────────────────────────
# Extract source so %install can copy it
mkdir -p "${RPM_BUILD_DIR}/BUILD/vajrastocks-${VERSION}"
tar -xzf "${TARBALL}" -C "${RPM_BUILD_DIR}/BUILD/" --strip-components=1

rpmbuild --define "_topdir $(pwd)/${RPM_BUILD_DIR}" \
         -bb "${RPM_BUILD_DIR}/SPECS/vajrastocks.spec"

mkdir -p "${RELEASE_DIR}"
find "${RPM_BUILD_DIR}/RPMS" -name "*.rpm" -exec cp {} "${RELEASE_DIR}/VajraStocks.rpm" \;
rm -rf "${RPM_BUILD_DIR}"

echo "Built: ${RELEASE_DIR}/VajraStocks.rpm"
