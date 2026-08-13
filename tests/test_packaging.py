from pathlib import Path

from serialscope import __version__


def test_package_metadata_uses_authoritative_runtime_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    configuration = (project_root / "pyproject.toml").read_text("utf-8")

    assert 'dynamic = ["version"]' in configuration
    assert '\nversion = "' not in configuration
    assert 'version = {attr = "serialscope.__version__"}' in configuration
    assert __version__ == "0.9.2"
    assert '[project.gui-scripts]' in configuration
    assert 'serialscope = "serialscope.app:main"' in configuration


def test_runtime_dependencies_are_explicit_and_development_is_separate() -> None:
    project_root = Path(__file__).resolve().parents[1]
    configuration = (project_root / "pyproject.toml").read_text("utf-8")

    runtime, development = configuration.split("[project.optional-dependencies]", 1)
    assert '"PySide6' in runtime
    assert '"pyqtgraph' in runtime
    assert '"pyserial' in runtime
    assert '"pytest' not in runtime
    assert '"pytest>=8,<9"' in development
    assert '"pyinstaller>=6.10,<7"' in development


def test_linux_spec_uses_package_entry_point_and_authoritative_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    spec = (project_root / "packaging" / "serialscope.spec").read_text("utf-8")

    assert '"serialscope" / "__main__.py"' in spec
    assert 'name="SerialScope"' in spec
    assert "console=False" in spec
    assert "0.9.2" not in spec


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
