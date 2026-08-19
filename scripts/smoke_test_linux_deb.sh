#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
PYTHON_EXECUTABLE="${PROJECT_ROOT}/.venv/bin/python"
PACKAGE_NAME="serialscope"
ARCHITECTURE="$(dpkg --print-architecture)"
APPLICATION_VERSION="$("${PYTHON_EXECUTABLE}" -c 'from serialscope import __version__; print(__version__)')"
PACKAGE_FILE="${1:-${PROJECT_ROOT}/dist/MCUDesk_${APPLICATION_VERSION}_Linux_${ARCHITECTURE}.deb}"
SMOKE_DIRECTORY="$(mktemp -d)"
PACKAGE_ROOT="${SMOKE_DIRECTORY}/root"
CONTROL_ROOT="${SMOKE_DIRECTORY}/control"

cleanup() {
    rm -rf -- "${SMOKE_DIRECTORY}"
}
trap cleanup EXIT

fail() {
    echo "MCUDesk .deb smoke test failed: $*" >&2
    exit 1
}

[[ -f "${PACKAGE_FILE}" ]] || fail "package not found: ${PACKAGE_FILE}"
mkdir -p "${PACKAGE_ROOT}" "${CONTROL_ROOT}"
dpkg-deb --extract "${PACKAGE_FILE}" "${PACKAGE_ROOT}"
dpkg-deb --control "${PACKAGE_FILE}" "${CONTROL_ROOT}"

[[ "$(dpkg-deb -f "${PACKAGE_FILE}" Package)" == "${PACKAGE_NAME}" ]] \
    || fail "package name does not match."
[[ "$(dpkg-deb -f "${PACKAGE_FILE}" Version)" == "${APPLICATION_VERSION}" ]] \
    || fail "package version does not match serialscope.__version__."
[[ "$(dpkg-deb -f "${PACKAGE_FILE}" Architecture)" == "${ARCHITECTURE}" ]] \
    || fail "package architecture does not match the build host."
[[ -x "${PACKAGE_ROOT}/opt/serialscope/MCUDesk" ]] \
    || fail "installed application executable is missing or not executable."
[[ -x "${PACKAGE_ROOT}/usr/bin/mcudesk" ]] \
    || fail "MCUDesk command-line launcher is missing or not executable."
[[ -x "${PACKAGE_ROOT}/usr/bin/serialscope" ]] \
    || fail "compatibility command-line launcher is missing or not executable."
[[ -f "${PACKAGE_ROOT}/usr/share/applications/serialscope.desktop" ]] \
    || fail "desktop entry is missing."
[[ -f "${PACKAGE_ROOT}/usr/share/icons/hicolor/256x256/apps/mcudesk.png" ]] \
    || fail "hicolor application icon is missing."

grep -qx 'exec /opt/serialscope/MCUDesk "$@"' \
    "${PACKAGE_ROOT}/usr/bin/mcudesk" \
    || fail "MCUDesk launcher does not execute the installed bundle correctly."
grep -qx 'exec /opt/serialscope/MCUDesk "$@"' \
    "${PACKAGE_ROOT}/usr/bin/serialscope" \
    || fail "compatibility launcher does not execute the installed bundle correctly."
grep -qx 'Exec=mcudesk' \
    "${PACKAGE_ROOT}/usr/share/applications/serialscope.desktop" \
    || fail "desktop Exec field is invalid."
grep -qx 'Icon=mcudesk' \
    "${PACKAGE_ROOT}/usr/share/applications/serialscope.desktop" \
    || fail "desktop Icon field is invalid."
grep -qx 'Name=MCUDesk' \
    "${PACKAGE_ROOT}/usr/share/applications/serialscope.desktop" \
    || fail "desktop Name field is invalid."

if grep -R -F '/home/roelof' \
    "${PACKAGE_ROOT}/usr/bin" \
    "${PACKAGE_ROOT}/usr/share/applications" \
    "${CONTROL_ROOT}"; then
    fail "development-specific absolute path found in package metadata."
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate \
        "${PACKAGE_ROOT}/usr/share/applications/serialscope.desktop"
fi

RUN_DIRECTORY="${SMOKE_DIRECTORY}/run"
mkdir -p "${RUN_DIRECTORY}"
cd -- "${RUN_DIRECTORY}"
QT_QPA_PLATFORM=offscreen \
XDG_CONFIG_HOME="${SMOKE_DIRECTORY}/config" \
"${PACKAGE_ROOT}/opt/serialscope/MCUDesk" --packaging-smoke-test

echo "MCUDesk .deb package passed staged validation: ${PACKAGE_FILE}"
