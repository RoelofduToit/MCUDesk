"""Validated persistent application preferences."""

from PySide6.QtCore import QSettings


THEME_OPTIONS = ("dark", "light")
DELIMITER_OPTIONS = (",", ";", "\t")


class ApplicationSettings:
    """Store small user preferences through Qt's native settings backend."""

    def __init__(self, backend: QSettings | None = None) -> None:
        self._backend = backend if backend is not None else QSettings()

    @property
    def theme(self) -> str:
        value = self._backend.value("appearance/theme", "dark", type=str).lower()
        return value if value in THEME_OPTIONS else "dark"

    @property
    def structured_data_delimiter(self) -> str:
        value = self._backend.value(
            "recording/structured_data_delimiter", ",", type=str
        )
        return value if value in DELIMITER_OPTIONS else ","

    def set_theme(self, theme: str) -> None:
        self._backend.setValue(
            "appearance/theme", theme.lower() if theme.lower() in THEME_OPTIONS else "dark"
        )
        self._backend.sync()

    def set_structured_data_delimiter(self, delimiter: str) -> None:
        self._backend.setValue(
            "recording/structured_data_delimiter",
            delimiter if delimiter in DELIMITER_OPTIONS else ",",
        )
        self._backend.sync()
