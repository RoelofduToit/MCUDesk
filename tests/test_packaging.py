from pathlib import Path
import configparser

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
    assert __version__ == "0.11.0"
    assert '[project.gui-scripts]' in configuration
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
    assert 'name="SerialScope"' in spec
    assert "console=False" in spec
    assert 'datas=[(str(ICON_SOURCE), "assets/icons")]' in spec
    assert '"assets" / "icons" / "serialscope.png"' in spec
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
    assert (project_root / "packaging" / "serialscope.spec").is_file()


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

    assert 'dist/SerialScope/_internal/assets/icons/serialscope.png' in smoke_script


def test_linux_desktop_entry_uses_standard_launcher_and_icon_names() -> None:
    project_root = Path(__file__).resolve().parents[1]
    desktop_file = project_root / "packaging" / "linux" / "serialscope.desktop"
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(desktop_file, encoding="utf-8")

    entry = parser["Desktop Entry"]
    assert entry["Type"] == "Application"
    assert entry["Name"] == "SerialScope"
    assert entry["Exec"] == "serialscope"
    assert entry["Icon"] == "serialscope"
    assert entry["Terminal"] == "false"
    assert "Engineering;" in entry["Categories"]


def test_linux_command_launcher_is_cwd_independent() -> None:
    project_root = Path(__file__).resolve().parents[1]
    launcher = (project_root / "packaging" / "linux" / "serialscope").read_text(
        "utf-8"
    )

    assert launcher.startswith("#!/bin/sh\n")
    assert 'exec /opt/serialscope/SerialScope "$@"' in launcher
    assert str(project_root) not in launcher


def test_debian_build_uses_authoritative_version_and_native_amd64_layout() -> None:
    project_root = Path(__file__).resolve().parents[1]
    build_script = (project_root / "scripts" / "build_linux_deb.sh").read_text(
        "utf-8"
    )

    assert "from serialscope import __version__" in build_script
    assert 'PACKAGE_NAME="serialscope"' in build_script
    assert 'ARCHITECTURE="$(dpkg --print-architecture)"' in build_script
    assert '[[ "${ARCHITECTURE}" == "amd64" ]]' in build_script
    assert "dist/${PACKAGE_NAME}_${APPLICATION_VERSION}_${ARCHITECTURE}.deb" in build_script
    assert 'STAGING_DIRECTORY="${PROJECT_ROOT}/build/deb/serialscope"' in build_script
    assert "${STAGING_DIRECTORY}/opt/serialscope" in build_script
    assert "${STAGING_DIRECTORY}/usr/bin" in build_script
    assert "${STAGING_DIRECTORY}/usr/share/applications" in build_script
    assert "hicolor/256x256/apps" in build_script
    assert 'Installed-Size: ${INSTALLED_SIZE}' in build_script
    assert '"${SCRIPT_DIRECTORY}/build_linux.sh"' in build_script
    assert __version__ in f"serialscope_{__version__}_amd64.deb"


def test_debian_packaging_uses_master_icon_without_checked_in_derivatives() -> None:
    project_root = Path(__file__).resolve().parents[1]
    build_script = (project_root / "scripts" / "build_linux_deb.sh").read_text(
        "utf-8"
    )
    source_icons = list((project_root / "assets" / "icons").glob("serialscope*"))

    assert source_icons == [project_root / "assets" / "icons" / "serialscope.png"]
    assert 'ICON_SOURCE="${PROJECT_ROOT}/assets/icons/serialscope.png"' in build_script
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
    assert '[[ -x "${PACKAGE_ROOT}/opt/serialscope/SerialScope" ]]' in smoke_script
    assert '[[ -x "${PACKAGE_ROOT}/usr/bin/serialscope" ]]' in smoke_script
    assert "--packaging-smoke-test" in smoke_script
