from pathlib import Path
import configparser
import struct

from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.resources import (
    APPLICATION_ICON,
    application_icon_path,
    apply_application_icon,
)


def test_package_metadata_uses_authoritative_runtime_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    configuration = (project_root / "pyproject.toml").read_text("utf-8")

    assert 'dynamic = ["version"]' in configuration
    assert '\nversion = "' not in configuration
    assert 'version = {attr = "serialscope.__version__"}' in configuration
    assert '[project.gui-scripts]' in configuration
    assert 'mcudesk = "serialscope.app:main"' in configuration
    assert 'serialscope = "serialscope.app:main"' in configuration


def test_runtime_dependencies_are_explicit_and_development_is_separate() -> None:
    project_root = Path(__file__).resolve().parents[1]
    configuration = (project_root / "pyproject.toml").read_text("utf-8")

    runtime, development = configuration.split("[project.optional-dependencies]", 1)
    assert '"PySide6' in runtime
    assert '"pyqtgraph' in runtime
    assert '"pyserial' in runtime
    assert '"packaging' in runtime
    assert '"pytest' not in runtime
    assert '"pytest>=8,<9"' in development
    assert '"pyinstaller>=6.10,<7"' in development


def test_linux_spec_uses_package_entry_point_and_authoritative_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    spec = (project_root / "packaging" / "serialscope.spec").read_text("utf-8")

    assert '"serialscope" / "__main__.py"' in spec
    assert 'name="MCUDesk"' in spec
    assert "console=False" in spec
    assert 'datas=[(str(ICON_SOURCE), "assets/icons")]' in spec
    assert '"assets" / "icons" / "mcudesk.png"' in spec
    assert "0.9.2" not in spec


def test_authoritative_icon_exists_and_lookup_is_cwd_independent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    expected = project_root / APPLICATION_ICON

    monkeypatch.chdir(tmp_path)
    assert application_icon_path() == expected
    assert application_icon_path().is_file()


def test_application_icon_loads_and_missing_icon_is_nonfatal(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])

    assert apply_application_icon(application)
    assert not application.windowIcon().isNull()
    assert not apply_application_icon(application, tmp_path / "missing.png")


def test_generated_packaging_output_is_ignored_but_spec_is_tracked() -> None:
    project_root = Path(__file__).resolve().parents[1]
    ignore = (project_root / ".gitignore").read_text("utf-8")

    assert "build/" in ignore
    assert "dist/" in ignore
    assert "!packaging/serialscope.spec" in ignore
    assert "!packaging/serialscope_windows.spec" in ignore
    assert (project_root / "packaging" / "serialscope.spec").is_file()
    assert (project_root / "packaging" / "serialscope_windows.spec").is_file()


def test_module_entry_and_build_script_share_application_startup() -> None:
    project_root = Path(__file__).resolve().parents[1]
    module_entry = (project_root / "src" / "serialscope" / "__main__.py").read_text(
        "utf-8"
    )
    build_script = (project_root / "scripts" / "build_linux.sh").read_text(
        "utf-8"
    )

    assert "from serialscope.app import main" in module_entry
    assert "packaging/serialscope.spec" in build_script
    assert "main.py" not in build_script


def test_packaging_smoke_test_requires_bundled_icon() -> None:
    project_root = Path(__file__).resolve().parents[1]
    smoke_script = (project_root / "scripts" / "smoke_test_linux.sh").read_text(
        "utf-8"
    )

    assert 'dist/MCUDesk/_internal/assets/icons/mcudesk.png' in smoke_script


def test_linux_desktop_entry_uses_standard_launcher_and_icon_names() -> None:
    project_root = Path(__file__).resolve().parents[1]
    desktop_file = project_root / "packaging" / "linux" / "serialscope.desktop"
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(desktop_file, encoding="utf-8")

    entry = parser["Desktop Entry"]
    assert entry["Type"] == "Application"
    assert entry["Name"] == "MCUDesk"
    assert entry["Exec"] == "mcudesk"
    assert entry["Icon"] == "mcudesk"
    assert entry["Terminal"] == "false"
    assert "Engineering;" in entry["Categories"]


def test_linux_command_launcher_is_cwd_independent() -> None:
    project_root = Path(__file__).resolve().parents[1]
    launcher = (project_root / "packaging" / "linux" / "serialscope").read_text(
        "utf-8"
    )

    assert launcher.startswith("#!/bin/sh\n")
    assert 'exec /opt/serialscope/MCUDesk "$@"' in launcher
    assert str(project_root) not in launcher
    compatibility = (project_root / "packaging" / "linux" / "mcudesk").read_text("utf-8")
    assert compatibility == launcher


def test_debian_build_uses_authoritative_version_and_native_amd64_layout() -> None:
    project_root = Path(__file__).resolve().parents[1]
    build_script = (project_root / "scripts" / "build_linux_deb.sh").read_text(
        "utf-8"
    )

    assert "from serialscope import __version__" in build_script
    assert 'PACKAGE_NAME="serialscope"' in build_script
    assert 'ARCHITECTURE="$(dpkg --print-architecture)"' in build_script
    assert '[[ "${ARCHITECTURE}" == "amd64" ]]' in build_script
    assert "dist/MCUDesk_${APPLICATION_VERSION}_Linux_${ARCHITECTURE}.deb" in build_script
    assert "dist/serialscope_${APPLICATION_VERSION}_${ARCHITECTURE}.deb" in build_script
    assert 'STAGING_DIRECTORY="${PROJECT_ROOT}/build/deb/serialscope"' in build_script
    assert "${STAGING_DIRECTORY}/opt/serialscope" in build_script
    assert "${STAGING_DIRECTORY}/usr/bin" in build_script
    assert "${STAGING_DIRECTORY}/usr/share/applications" in build_script
    assert "hicolor/256x256/apps" in build_script
    assert 'Installed-Size: ${INSTALLED_SIZE}' in build_script
    assert '"${SCRIPT_DIRECTORY}/build_linux.sh"' in build_script
    assert __version__ in f"MCUDesk_{__version__}_Linux_amd64.deb"


def test_debian_packaging_uses_master_png_independently_of_windows_icon() -> None:
    project_root = Path(__file__).resolve().parents[1]
    build_script = (project_root / "scripts" / "build_linux_deb.sh").read_text(
        "utf-8"
    )
    assert (project_root / "assets" / "icons" / "mcudesk.png").is_file()
    assert (project_root / "assets" / "icons" / "mcudesk.ico").is_file()
    assert 'ICON_SOURCE="${PROJECT_ROOT}/assets/icons/mcudesk.png"' in build_script
    assert "image.scaled(" in build_script
    assert 'resized.save(str(destination), "PNG")' in build_script


def test_debian_maintainer_scripts_only_refresh_optional_caches() -> None:
    project_root = Path(__file__).resolve().parents[1]

    for name in ("postinst", "postrm"):
        script = (project_root / "packaging" / "linux" / name).read_text("utf-8")
        assert "command -v update-desktop-database" in script
        assert "command -v gtk-update-icon-cache" in script
        assert "|| true" in script
        assert "/home/" not in script


def test_debian_smoke_test_checks_package_identity_layout_and_permissions() -> None:
    project_root = Path(__file__).resolve().parents[1]
    smoke_script = (
        project_root / "scripts" / "smoke_test_linux_deb.sh"
    ).read_text("utf-8")

    assert "dpkg-deb --extract" in smoke_script
    assert "dpkg-deb --control" in smoke_script
    assert 'dpkg-deb -f "${PACKAGE_FILE}" Package' in smoke_script
    assert 'dpkg-deb -f "${PACKAGE_FILE}" Version' in smoke_script
    assert 'dpkg-deb -f "${PACKAGE_FILE}" Architecture' in smoke_script
    assert '[[ -x "${PACKAGE_ROOT}/opt/serialscope/MCUDesk" ]]' in smoke_script
    assert '[[ -x "${PACKAGE_ROOT}/usr/bin/mcudesk" ]]' in smoke_script
    assert '[[ -x "${PACKAGE_ROOT}/usr/bin/serialscope" ]]' in smoke_script
    assert "hicolor/256x256/apps/mcudesk.png" in smoke_script
    assert "--packaging-smoke-test" in smoke_script


def test_windows_spec_is_windowed_one_folder_and_bundles_runtime_icon() -> None:
    project_root = Path(__file__).resolve().parents[1]
    spec = (project_root / "packaging" / "serialscope_windows.spec").read_text(
        "utf-8"
    )

    assert '"serialscope" / "__main__.py"' in spec
    assert 'name="MCUDesk"' in spec
    assert "console=False" in spec
    assert "COLLECT(" in spec
    assert 'icon=str(WINDOWS_ICON)' in spec
    assert '"assets" / "icons" / "mcudesk.ico"' in spec
    assert 'datas=[(str(ICON_SOURCE), "assets/icons")]' in spec
    assert '"assets" / "icons" / "mcudesk.png"' in spec


def test_windows_icon_contains_conventional_multiresolution_sizes() -> None:
    project_root = Path(__file__).resolve().parents[1]
    icon = project_root / "assets" / "icons" / "mcudesk.ico"
    data = icon.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", data)
    assert (reserved, image_type) == (0, 1)
    assert count >= 7

    sizes = set()
    for index in range(count):
        width, height = struct.unpack_from("BB", data, 6 + index * 16)
        sizes.add((width or 256, height or 256))
    assert {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)} <= sizes


def test_windows_build_and_smoke_scripts_are_cwd_independent() -> None:
    project_root = Path(__file__).resolve().parents[1]
    build_script = (project_root / "scripts" / "build_windows.ps1").read_text(
        "utf-8"
    )
    smoke_script = (
        project_root / "scripts" / "smoke_test_windows.ps1"
    ).read_text("utf-8")

    assert '$PSScriptRoot ".."' in build_script
    assert "packaging\\serialscope_windows.spec" in build_script
    assert "-m PyInstaller" in build_script
    assert "--clean" in build_script
    assert "Remove-Item Env:PYTHONPATH" in build_script
    assert "Remove-Item Env:PYTHONHOME" in build_script
    assert '$BundleDirectory = Join-Path $DistRoot "MCUDesk"' in build_script
    assert "MCUDesk.exe" in build_script
    assert "qwindows.dll" in build_script
    assert '$PSScriptRoot ".."' in smoke_script
    assert "MCUDesk.exe" in smoke_script
    assert "Get-PeSubsystem" in smoke_script
    assert "Start-Process" in smoke_script
    assert "-WorkingDirectory $SmokeDirectory" in smoke_script
    assert "CloseMainWindow" in smoke_script


def test_windows_packaging_documentation_covers_build_and_manual_validation() -> None:
    project_root = Path(__file__).resolve().parents[1]
    documentation = (project_root / "docs" / "PACKAGING_WINDOWS.md").read_text(
        "utf-8"
    )

    assert ".\\scripts\\build_windows.ps1" in documentation
    assert ".\\scripts\\smoke_test_windows.ps1" in documentation
    assert "dist\\MCUDesk\\MCUDesk.exe" in documentation
    assert "COM ports" in documentation
    assert "No installer" in documentation


WINDOWS_APP_ID = "{E893C988-663D-46E8-8C25-E4B83C414F1E}"


def test_windows_installer_keeps_stable_appid_and_mcudesk_branding() -> None:
    project_root = Path(__file__).resolve().parents[1]
    installer = (project_root / "packaging" / "windows" / "serialscope.iss").read_text(
        "utf-8"
    )
    assert f"AppId={{{{E893C988-663D-46E8-8C25-E4B83C414F1E}}" in installer
    assert '{E893C988-663D-46E8-8C25-E4B83C414F1E}' in installer
    assert installer.count(WINDOWS_APP_ID) == 1
    assert "UsePreviousAppDir=yes" in installer
    assert r"DefaultDirName={autopf}\MCUDesk" in installer
    assert '#define AppName "MCUDesk"' in installer
    assert '#define AppExeName "MCUDesk.exe"' in installer
    assert "MCUDesk_{#AppVersion}_Windows_x64_Setup" in installer
    assert "mcudesk.ico" in installer
    assert r"dist\MCUDesk\*" in installer
    assert "{app}\\SerialScope.exe" in installer


def test_current_windows_release_workflow_is_tag_driven() -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = (
        project_root / ".github" / "workflows" / "build-windows-current-release.yml"
    ).read_text("utf-8")
    historical = (
        project_root / ".github" / "workflows" / "build-windows-release.yml"
    ).read_text("utf-8")

    assert "workflow_dispatch:" in current
    assert "tag:" in current
    assert "required: true" in current
    assert "windows-latest" in current
    assert "ref: ${{ inputs.tag }}" in current
    assert "git describe --tags --exact-match HEAD" in current
    assert "src\\serialscope\\__init__.py" in current
    assert '".[dev,packaging]"' in current
    assert "QT_QPA_PLATFORM: offscreen" in current
    assert r".\scripts\build_windows.ps1" in current
    assert r".\scripts\smoke_test_windows.ps1" in current
    assert r".\scripts\build_windows_installer.ps1" in current
    assert "MCUDesk_${Version}_Windows_x64_Setup.exe" in current
    assert "gh release upload $Tag $Installer" in current
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in current
    assert "contents: write" in current
    assert "actions: write" in current
    assert "This workflow never publishes a release." in current
    assert "gh release edit" not in current
    assert "ref: v0.13.0" not in current
    assert "SerialScope_0.13.0_Windows_x64_Setup.exe" not in current

    assert "ref: v0.13.0" in historical
    assert "SerialScope_0.13.0_Windows_x64_Setup.exe" in historical
