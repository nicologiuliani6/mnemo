#!/usr/bin/env bash
# Pacchetto Linux dell'app standalone `mnemo` (PyInstaller, niente Python
# richiesto). Installa:
#   /opt/mnemo/mnemo          l'app
#   /usr/local/bin/mnemo      il link
# Dipende dal pacchetto `kairos` (VM e app per eseguire i programmi) e da gcc
# (preprocessore e link degli eseguibili di `mnemo compile`).
#
#   packaging/linux/build.sh deb|rpm|arch
#
# Versione: PKG_VERSION dall'ambiente (la CI la prende dal tag vX.Y.Z),
# altrimenti quella di pyproject.toml.
set -euo pipefail

FORMAT="${1:-}"
case "${FORMAT}" in deb|rpm|arch) ;; *) echo "uso: $0 deb|rpm|arch"; exit 1;; esac

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${ROOT_DIR}/../.." && pwd)"
PKG_NAME=mnemo
KAIROS_MIN=1.2.0   # primo pacchetto chiamato `kairos` (prima: kairosapp)
MAINTAINER="${MAINTAINER:-Nicolo Giuliani <nicolo.giuliani6@studio.unibo.it>}"
DESCRIPTION="Mnemo: compiler from a reversible C subset to Kairos"
PKG_VERSION="${PKG_VERSION:-$(sed -n 's/^version = "\(.*\)"/\1/p' "${PROJECT_ROOT}/pyproject.toml")}"
BUILD_DIR="${ROOT_DIR}/.build"
PY="${PROJECT_ROOT}/.venv/bin/python"

[[ -x "${PY}" ]] || { echo "Manca ${PROJECT_ROOT}/.venv: esegui make venv"; exit 1; }
"${PY}" -m pip install -q pyinstaller

# App standalone: il codice di mnemo, le librerie Kairos (mnemo/lib), gli
# header finti e lo stub C degli eseguibili nativi.
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
(cd "${PROJECT_ROOT}" && "${PY}" -m PyInstaller --onefile --log-level ERROR \
    --distpath "${BUILD_DIR}/dist" --workpath "${BUILD_DIR}/work" --specpath "${BUILD_DIR}" \
    --name mnemo \
    --add-data "${PROJECT_ROOT}/mnemo/lib:mnemo/lib" \
    --add-data "${PROJECT_ROOT}/mnemo/fake_include:mnemo/fake_include" \
    --add-data "${PROJECT_ROOT}/mnemo/mnemo_bundle_main.c:mnemo" \
    packaging/mnemo_main.py)
APP="${BUILD_DIR}/dist/mnemo"
[[ -x "${APP}" ]] || { echo "PyInstaller non ha prodotto ${APP}"; exit 1; }

case "${FORMAT}" in
deb)
  ARCH="$(dpkg --print-architecture)"
  STAGE="${BUILD_DIR}/${PKG_NAME}_${PKG_VERSION}_${ARCH}"
  mkdir -p "${STAGE}/DEBIAN" "${STAGE}/opt/mnemo" "${STAGE}/usr/local/bin"
  install -m 755 "${APP}" "${STAGE}/opt/mnemo/mnemo"
  ln -s /opt/mnemo/mnemo "${STAGE}/usr/local/bin/mnemo"
  cat > "${STAGE}/DEBIAN/control" <<CTL
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Section: devel
Priority: optional
Architecture: ${ARCH}
Maintainer: ${MAINTAINER}
Depends: libc6, kairos (>= ${KAIROS_MIN}), gcc
Description: ${DESCRIPTION}
CTL
  dpkg-deb --build --root-owner-group "${STAGE}" "${ROOT_DIR}/${PKG_NAME}_${PKG_VERSION}_${ARCH}.deb"
  ;;
rpm)
  ARCH="$(uname -m)"
  TOP="${BUILD_DIR}/rpmbuild"
  mkdir -p "${TOP}/"{BUILD,RPMS,SOURCES,SPECS,SRPMS}
  cat > "${TOP}/SPECS/${PKG_NAME}.spec" <<SPEC
Name:           ${PKG_NAME}
Version:        ${PKG_VERSION}
Release:        1%{?dist}
Summary:        ${DESCRIPTION}
License:        Proprietary
BuildArch:      ${ARCH}
Requires:       glibc, kairos >= ${KAIROS_MIN}, gcc

%description
${DESCRIPTION}

%install
mkdir -p %{buildroot}/opt/mnemo %{buildroot}/usr/local/bin
install -m 755 ${APP} %{buildroot}/opt/mnemo/mnemo
ln -sf /opt/mnemo/mnemo %{buildroot}/usr/local/bin/mnemo

%files
/opt/mnemo/mnemo
/usr/local/bin/mnemo
SPEC
  rpmbuild --define "_topdir ${TOP}" -bb "${TOP}/SPECS/${PKG_NAME}.spec"
  cp "${TOP}"/RPMS/"${ARCH}"/*.rpm "${ROOT_DIR}/"
  ;;
arch)
  mkdir -p "${BUILD_DIR}/arch"
  cat > "${BUILD_DIR}/arch/PKGBUILD" <<PKG
pkgname=${PKG_NAME}
pkgver=${PKG_VERSION}
pkgrel=1
pkgdesc="${DESCRIPTION}"
arch=('x86_64' 'aarch64')
license=('custom')
depends=('glibc' 'kairos>=${KAIROS_MIN}' 'gcc')
options=('!debug' '!strip')
package() {
  install -d "\${pkgdir}/opt/mnemo" "\${pkgdir}/usr/local/bin"
  install -m 755 "${APP}" "\${pkgdir}/opt/mnemo/mnemo"
  ln -sf /opt/mnemo/mnemo "\${pkgdir}/usr/local/bin/mnemo"
}
PKG
  (cd "${BUILD_DIR}/arch" && PKGDEST="${ROOT_DIR}" makepkg -f --nodeps --cleanbuild)
  ;;
esac
echo "Pacchetto in ${ROOT_DIR}"
