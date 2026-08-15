#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
PYTHON_EXECUTABLE="${PROJECT_ROOT}/.venv/bin/python"
PYINSTALLER_BUNDLE="${PROJECT_ROOT}/dist/SerialScope"
PACKAGING_SOURCE="${PROJECT_ROOT}/packaging/linux"
STAGING_DIRECTORY="${PROJECT_ROOT}/build/deb/serialscope"
PACKAGE_NAME="serialscope"
ARCHITECTURE="$(dpkg --print-architecture)"
ICON_SOURCE="${PROJECT_ROOT}/assets/icons/serialscope.png"

fail() {
    echo "SerialScope .deb build failed: $*" >&2
    exit 1
}

command -v dpkg-deb >/dev/null 2>&1 || fail "dpkg-deb is required."
[[ -x "${PYTHON_EXECUTABLE}" ]] || fail "project environment not found: ${PYTHON_EXECUTABLE}"
[[ -f "${ICON_SOURCE}" ]] || fail "authoritative icon not found: ${ICON_SOURCE}"
[[ "${ARCHITECTURE}" == "amd64" ]] || fail "this milestone supports native amd64 builds only (host reports ${ARCHITECTURE})."

APPLICATION_VERSION="$("${PYTHON_EXECUTABLE}" -c 'from serialscope import __version__; print(__version__)')"
[[ -n "${APPLICATION_VERSION}" ]] || fail "authoritative application version is empty."
dpkg --validate-version "${APPLICATION_VERSION}" >/dev/null 2>&1 \
    || fail "application version is not a valid Debian version: ${APPLICATION_VERSION}"

PACKAGE_FILE="${PROJECT_ROOT}/dist/${PACKAGE_NAME}_${APPLICATION_VERSION}_${ARCHITECTURE}.deb"

"${SCRIPT_DIRECTORY}/build_linux.sh"
[[ -x "${PYINSTALLER_BUNDLE}/SerialScope" ]] \
    || fail "PyInstaller executable was not created."

rm -rf -- "${STAGING_DIRECTORY}"
mkdir -p \
    "${STAGING_DIRECTORY}/DEBIAN" \
    "${STAGING_DIRECTORY}/opt/serialscope" \
    "${STAGING_DIRECTORY}/usr/bin" \
    "${STAGING_DIRECTORY}/usr/share/applications" \
    "${STAGING_DIRECTORY}/usr/share/icons/hicolor/256x256/apps"

cp -a "${PYINSTALLER_BUNDLE}/." "${STAGING_DIRECTORY}/opt/serialscope/"
install -m 0755 "${PACKAGING_SOURCE}/serialscope" \
    "${STAGING_DIRECTORY}/usr/bin/serialscope"
install -m 0644 "${PACKAGING_SOURCE}/serialscope.desktop" \
    "${STAGING_DIRECTORY}/usr/share/applications/serialscope.desktop"
install -m 0755 "${PACKAGING_SOURCE}/postinst" \
    "${STAGING_DIRECTORY}/DEBIAN/postinst"
install -m 0755 "${PACKAGING_SOURCE}/postrm" \
    "${STAGING_DIRECTORY}/DEBIAN/postrm"

"${PYTHON_EXECUTABLE}" - "${ICON_SOURCE}" \
    "${STAGING_DIRECTORY}/usr/share/icons/hicolor/256x256/apps/serialscope.png" <<'PYTHON'
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

source, destination = map(Path, sys.argv[1:])
image = QImage(str(source))
if image.isNull():
    raise SystemExit(f"Cannot load authoritative icon: {source}")
resized = image.scaled(
    256,
    256,
    Qt.AspectRatioMode.KeepAspectRatio,
    Qt.TransformationMode.SmoothTransformation,
)
if resized.width() != 256 or resized.height() != 256:
    raise SystemExit("Authoritative icon is not square; cannot create a 256x256 icon.")
if not resized.save(str(destination), "PNG"):
    raise SystemExit(f"Cannot write packaged icon: {destination}")
PYTHON

INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "${STAGING_DIRECTORY}" | cut -f1)"

cat >"${STAGING_DIRECTORY}/DEBIAN/control" <<CONTROL
Package: ${PACKAGE_NAME}
Version: ${APPLICATION_VERSION}
Section: utils
Priority: optional
Architecture: ${ARCHITECTURE}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Roelof du Toit <136355778+RoelofduToit@users.noreply.github.com>
Depends: libc6 (>= 2.38), libegl1, libgl1, libwayland-client0, libwayland-cursor0
Homepage: https://github.com/RoelofduToit/SerialScope
Description: Serial data acquisition, logging and visualization
 SerialScope is a desktop serial terminal and engineering data tool with
 structured parsing, recording, graphing, dashboards and session replay.
CONTROL

chmod -R u=rwX,go=rX "${STAGING_DIRECTORY}/opt/serialscope"
chmod 0755 \
    "${STAGING_DIRECTORY}/opt/serialscope/SerialScope" \
    "${STAGING_DIRECTORY}/usr/bin/serialscope" \
    "${STAGING_DIRECTORY}/DEBIAN/postinst" \
    "${STAGING_DIRECTORY}/DEBIAN/postrm"
chmod 0644 \
    "${STAGING_DIRECTORY}/DEBIAN/control" \
    "${STAGING_DIRECTORY}/usr/share/applications/serialscope.desktop" \
    "${STAGING_DIRECTORY}/usr/share/icons/hicolor/256x256/apps/serialscope.png"

[[ "$(sed -n 's/^Exec=//p' "${STAGING_DIRECTORY}/usr/share/applications/serialscope.desktop")" == "serialscope" ]] \
    || fail "desktop Exec field is invalid."
[[ "$(sed -n 's/^Icon=//p' "${STAGING_DIRECTORY}/usr/share/applications/serialscope.desktop")" == "serialscope" ]] \
    || fail "desktop Icon field is invalid."

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "${STAGING_DIRECTORY}/usr/share/applications/serialscope.desktop"
else
    echo "desktop-file-validate is unavailable; structural desktop-entry checks passed."
fi

rm -f -- "${PACKAGE_FILE}"
dpkg-deb --build --root-owner-group "${STAGING_DIRECTORY}" "${PACKAGE_FILE}"
"${SCRIPT_DIRECTORY}/smoke_test_linux_deb.sh" "${PACKAGE_FILE}"

PACKAGE_SIZE="$(du -h "${PACKAGE_FILE}" | cut -f1)"
echo "SerialScope Debian package created: ${PACKAGE_FILE}"
echo "Package size: ${PACKAGE_SIZE}"
