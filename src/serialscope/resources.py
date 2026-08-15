"""CWD-independent lookup and loading of bundled application resources."""

from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


APPLICATION_ICON = Path("assets/icons/serialscope.png")


def resource_path(relative_path: str | Path) -> Path:
    """Resolve a resource in a source checkout or PyInstaller bundle."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return root / Path(relative_path)


def application_icon_path() -> Path:
    """Return the authoritative application icon location."""
    return resource_path(APPLICATION_ICON)


def apply_application_icon(
    application: QApplication,
    icon_path: Path | None = None,
) -> bool:
    """Apply the icon when available; cosmetic resource failure is non-fatal."""
    path = icon_path or application_icon_path()
    if not path.is_file():
        return False
    icon = QIcon(str(path))
    if icon.isNull():
        return False
    application.setWindowIcon(icon)
    return True
