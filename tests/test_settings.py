from datetime import datetime, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from serialscope.settings import ApplicationSettings


def _settings(path: Path) -> ApplicationSettings:
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    return ApplicationSettings(backend)


def test_default_preferences_are_dark_and_comma(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "settings.ini")

    assert settings.theme == "dark"
    assert settings.dashboard_numeric_style == "default"
    assert settings.dashboard_trend_window_seconds == 60
    assert settings.structured_data_delimiter == ","
    assert settings.automatically_check_for_updates
    assert settings.last_automatic_update_check is None


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_theme_selection_persists(tmp_path: Path, theme: str) -> None:
    path = tmp_path / "settings.ini"
    _settings(path).set_theme(theme)

    assert _settings(path).theme == theme


def test_theme_is_persisted_as_lowercase_value(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    settings = _settings(path)

    settings.set_theme("Light")

    backend = QSettings(str(path), QSettings.Format.IniFormat)
    assert backend.value("appearance/theme") == "light"


@pytest.mark.parametrize(
    "style",
    [
        "default",
        "seven_segment",
        "fourteen_segment",
        "lcd",
        "dot_matrix",
        "technical_mono",
    ],
)
def test_dashboard_numeric_style_persists(tmp_path: Path, style: str) -> None:
    path = tmp_path / "settings.ini"
    _settings(path).set_dashboard_numeric_style(style)

    assert _settings(path).dashboard_numeric_style == style
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    assert backend.value("appearance/dashboard_numeric_style") == style


@pytest.mark.parametrize("stored_style", ["Neon", "seven segment", "", "Default"])
def test_invalid_dashboard_numeric_style_falls_back_to_default(
    tmp_path: Path,
    stored_style: str,
) -> None:
    path = tmp_path / "settings.ini"
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    backend.setValue("appearance/dashboard_numeric_style", stored_style)
    backend.sync()

    assert _settings(path).dashboard_numeric_style == "default"


@pytest.mark.parametrize("seconds", [30, 60, 300, 600, 1_800, 3_600])
def test_dashboard_trend_window_persists_as_integer(
    tmp_path: Path,
    seconds: int,
) -> None:
    path = tmp_path / "settings.ini"
    _settings(path).set_dashboard_trend_window_seconds(seconds)

    assert _settings(path).dashboard_trend_window_seconds == seconds
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    assert int(backend.value("appearance/dashboard_trend_window_seconds")) == seconds


@pytest.mark.parametrize("stored", ["invalid", -1, 0, 31, 60.5, 3_601, ""])
def test_invalid_dashboard_trend_window_falls_back_to_one_minute(
    tmp_path: Path,
    stored: object,
) -> None:
    path = tmp_path / "settings.ini"
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    backend.setValue("appearance/dashboard_trend_window_seconds", stored)
    backend.sync()

    assert _settings(path).dashboard_trend_window_seconds == 60


@pytest.mark.parametrize("stored_theme", ["system", "System", "Neon"])
def test_old_or_invalid_stored_theme_falls_back_to_dark(
    tmp_path: Path,
    stored_theme: str,
) -> None:
    path = tmp_path / "settings.ini"
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    backend.setValue("appearance/theme", stored_theme)
    backend.sync()

    assert _settings(path).theme == "dark"


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_delimiter_preference_persists(tmp_path: Path, delimiter: str) -> None:
    path = tmp_path / "settings.ini"
    _settings(path).set_structured_data_delimiter(delimiter)

    assert _settings(path).structured_data_delimiter == delimiter


def test_invalid_delimiter_falls_back_to_comma(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    backend.setValue("recording/structured_data_delimiter", "|")
    backend.sync()

    assert _settings(path).structured_data_delimiter == ","


def test_update_preferences_and_last_check_persist(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    settings = _settings(path)
    checked_at = datetime(2026, 8, 15, 12, 30, tzinfo=timezone.utc)
    settings.set_automatically_check_for_updates(False)
    settings.set_last_automatic_update_check(checked_at)

    restored = _settings(path)
    assert not restored.automatically_check_for_updates
    assert restored.last_automatic_update_check == checked_at


def test_invalid_last_update_timestamp_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    backend = QSettings(str(path), QSettings.Format.IniFormat)
    backend.setValue("updates/last_automatic_check_utc", "not a date")
    assert _settings(path).last_automatic_update_check is None


def test_in_progress_sessions_are_registered_and_removed(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    settings = _settings(path)
    first = tmp_path / "session_a"
    second = tmp_path / "session_b"

    settings.add_in_progress_session(first)
    settings.add_in_progress_session(second)
    settings.add_in_progress_session(first)

    assert tuple(Path(item) for item in settings.in_progress_sessions()) == (
        second,
        first,
    )
    settings.remove_in_progress_session(first)
    assert tuple(Path(item) for item in settings.in_progress_sessions()) == (second,)
    settings.remove_in_progress_session(second)
    assert settings.in_progress_sessions() == ()
