import pytest
from PySide6.QtWidgets import QApplication

from serialscope.ui.main_window import MainWindow
from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_theme_styles_menu_selection_and_disabled_items(stylesheet: str) -> None:
    assert "QMenu::item:selected:enabled" in stylesheet
    assert "QMenu::item:disabled" in stylesheet
    assert "background-color" in stylesheet.split(
        "QMenu::item:selected:enabled", maxsplit=1
    )[1].split("}", maxsplit=1)[0]


def test_file_actions_keep_functionality_across_theme_switches() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.open_session_action.text() == "Open Session..."
    assert window.open_session_action.isEnabled()
    assert window.close_session_action.text() == "Close Session"
    assert not window.close_session_action.isEnabled()

    for theme in ("light", "dark"):
        window.apply_theme(theme)
        assert window.open_session_action.isEnabled()
        assert not window.close_session_action.isEnabled()

    window.close()
    application.processEvents()
