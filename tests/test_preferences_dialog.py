import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.ui.preferences_dialog import PreferencesDialog


@pytest.mark.parametrize(
    ("label", "theme"), [("Dark", "dark"), ("Light", "light")]
)
def test_preferences_dialog_selects_supported_theme(label: str, theme: str) -> None:
    application = QApplication.instance() or QApplication([])
    dialog = PreferencesDialog("dark")

    dialog.theme_combo.setCurrentText(label)

    assert dialog.selected_theme == theme
    assert [dialog.theme_combo.itemText(index) for index in range(2)] == [
        "Dark",
        "Light",
    ]
    dialog.close()
    application.processEvents()
