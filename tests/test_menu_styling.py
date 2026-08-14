import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.ui.about_dialog import AboutDialog, APPLICATION_AUTHOR, GITHUB_URL
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


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_theme_has_semantic_warning_and_alarm_tile_states(stylesheet: str) -> None:
    assert 'alarmState="warning"' in stylesheet
    assert 'alarmState="alarm"' in stylesheet


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_theme_styles_all_connection_status_states(stylesheet: str) -> None:
    assert "QFrame#connectionStatusIndicator" in stylesheet
    assert 'connectionState="connected"' in stylesheet
    assert 'connectionState="error"' in stylesheet
    assert "QLabel#connectionStatusDot" in stylesheet
    assert "QLabel#connectionStatusLabel" in stylesheet


def test_menu_bar_shows_author_authoritative_version_and_updates_link(
    monkeypatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    opened: list[QUrl] = []
    monkeypatch.setattr(
        "serialscope.ui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    window = MainWindow(port_scanner=lambda: [])

    assert window.menu_author_label.text() == APPLICATION_AUTHOR == "Roelof du Toit"
    assert window.menu_version_label.text() == f"v{__version__}"
    assert window.github_updates_button.text() == "GitHub / Updates"
    assert "releases and updates" in window.github_updates_button.toolTip()
    assert window.about_action.text() == "About SerialScope"
    window.github_updates_button.click()
    assert opened == [QUrl(GITHUB_URL)]

    for theme in ("light", "dark"):
        window.apply_theme(theme)
        assert window.menu_author_label.text() == APPLICATION_AUTHOR
        assert window.menu_version_label.text() == f"v{__version__}"
        assert window.github_updates_button.isEnabled()
    window.close()
    application.processEvents()


def test_about_dialog_uses_shared_application_information() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = AboutDialog()
    text = dialog.information_label.text()

    assert dialog.windowTitle() == "About SerialScope"
    assert "SerialScope" in text
    assert f"Version {__version__}" in text
    assert APPLICATION_AUTHOR in text
    assert GITHUB_URL in text
    assert dialog.information_label.openExternalLinks()
    dialog.close()
    application.processEvents()


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_theme_styles_github_updates_hover(stylesheet: str) -> None:
    assert "QToolButton#githubUpdatesButton:hover" in stylesheet
    hover = stylesheet.split(
        "QToolButton#githubUpdatesButton:hover", maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    assert "background-color" in hover
    assert "border-color" in hover
