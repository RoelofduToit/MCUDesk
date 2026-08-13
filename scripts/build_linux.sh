#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
PYTHON_EXECUTABLE="${PROJECT_ROOT}/.venv/bin/python"
SPEC_FILE="${PROJECT_ROOT}/packaging/serialscope.spec"
OUTPUT_DIRECTORY="${PROJECT_ROOT}/dist/SerialScope"

if [[ ! -x "${PYTHON_EXECUTABLE}" ]]; then
    echo "SerialScope project environment not found: ${PYTHON_EXECUTABLE}" >&2
    echo 'Create it and install: python -m pip install -e ".[dev,packaging]"' >&2
    exit 1
fi

if ! "${PYTHON_EXECUTABLE}" -c "import PyInstaller" 2>/dev/null; then
    echo 'PyInstaller is missing from .venv.' >&2
    echo 'Install it with: .venv/bin/python -m pip install -e ".[dev,packaging]"' >&2
    exit 1
fi

rm -rf -- "${PROJECT_ROOT}/build/SerialScope" "${OUTPUT_DIRECTORY}"

"${PYTHON_EXECUTABLE}" -m PyInstaller \
    --noconfirm \
    --clean \
    --workpath "${PROJECT_ROOT}/build/SerialScope" \
    --distpath "${PROJECT_ROOT}/dist" \
    "${SPEC_FILE}"

echo "SerialScope Linux bundle created at: ${OUTPUT_DIRECTORY}"
echo "Launch it with: ${OUTPUT_DIRECTORY}/SerialScope"
