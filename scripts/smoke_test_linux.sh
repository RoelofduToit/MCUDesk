#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
EXECUTABLE="${PROJECT_ROOT}/dist/SerialScope/SerialScope"
SMOKE_DIRECTORY="$(mktemp -d)"

cleanup() {
    rm -rf -- "${SMOKE_DIRECTORY}"
}
trap cleanup EXIT

if [[ ! -x "${EXECUTABLE}" ]]; then
    echo "Packaged executable not found: ${EXECUTABLE}" >&2
    exit 1
fi

cd -- "${SMOKE_DIRECTORY}"
QT_QPA_PLATFORM=offscreen \
XDG_CONFIG_HOME="${SMOKE_DIRECTORY}/config" \
"${EXECUTABLE}" --packaging-smoke-test

echo "Packaged SerialScope started successfully from unrelated cwd: ${SMOKE_DIRECTORY}"
