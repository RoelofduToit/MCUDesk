import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel

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


def test_preferences_dialog_selects_dashboard_numeric_style() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = PreferencesDialog("dark", dashboard_numeric_style="dot_matrix")

    assert dialog.dashboard_numeric_style == "dot_matrix"
    labels = [
        dialog.numeric_style_combo.itemText(index)
        for index in range(dialog.numeric_style_combo.count())
    ]
    assert labels == [
        "Default",
        "Seven Segment",
        "Fourteen Segment",
        "LCD",
        "Dot Matrix",
        "Technical Mono",
    ]
    assert [child.title() for child in dialog.findChildren(QGroupBox)] == [
        "Appearance",
        "Dashboard",
        "Updates",
    ]
    assert dialog.findChild(QLabel, "dashboardNumericStyleLabel").text() == "Numeric style"
    dialog.numeric_style_combo.setCurrentText("Technical Mono")
    assert dialog.dashboard_numeric_style == "technical_mono"
    dialog.close()
    application.processEvents()


def test_preferences_dialog_selects_dashboard_trend_window() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = PreferencesDialog("dark", dashboard_trend_window_seconds=600)

    assert dialog.dashboard_trend_window_seconds == 600
    assert [
        dialog.trend_window_combo.itemText(index)
        for index in range(dialog.trend_window_combo.count())
    ] == [
        "30 seconds",
        "1 minute",
        "5 minutes",
        "10 minutes",
        "30 minutes",
        "1 hour",
    ]
    assert dialog.findChild(QLabel, "dashboardTrendWindowLabel").text() == (
        "Trend window"
    )
    dialog.trend_window_combo.setCurrentText("30 minutes")
    assert dialog.dashboard_trend_window_seconds == 1_800
    dialog.close()
    application.processEvents()


def test_preferences_dialog_edits_automatic_update_setting() -> None:
    QApplication.instance() or QApplication([])
    dialog = PreferencesDialog("dark", automatically_check_for_updates=False)

    assert not dialog.automatically_check_for_updates
    dialog.automatic_update_checkbox.setChecked(True)
    assert dialog.automatically_check_for_updates
    dialog.close()
