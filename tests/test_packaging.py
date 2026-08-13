from pathlib import Path

from serialscope import __version__


def test_package_metadata_uses_authoritative_runtime_version() -> None:
    project_root = Path(__file__).resolve().parents[1]
    configuration = (project_root / "pyproject.toml").read_text("utf-8")

    assert 'dynamic = ["version"]' in configuration
    assert '\nversion = "' not in configuration
    assert 'version = {attr = "serialscope.__version__"}' in configuration
    assert __version__ == "0.9.1"
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
