"""PyInstaller one-folder configuration for the MCUDesk Windows build."""

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"
ICON_SOURCE = PROJECT_ROOT / "assets" / "icons" / "mcudesk.png"
WINDOWS_ICON = PROJECT_ROOT / "assets" / "icons" / "mcudesk.ico"

analysis = Analysis(
    [str(SOURCE_ROOT / "serialscope" / "__main__.py")],
    pathex=[str(SOURCE_ROOT)],
    binaries=[],
    datas=[(str(ICON_SOURCE), "assets/icons")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MCUDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(WINDOWS_ICON),
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MCUDesk",
)
