"""Validated persistent application preferences."""

from datetime import datetime, timezone

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

    @property
    def automatically_check_for_updates(self) -> bool:
        value = self._backend.value("updates/automatic_check", True)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    @property
    def last_automatic_update_check(self) -> datetime | None:
        value = self._backend.value("updates/last_automatic_check_utc", "", type=str)
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

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

    def set_automatically_check_for_updates(self, enabled: bool) -> None:
        self._backend.setValue("updates/automatic_check", bool(enabled))
        self._backend.sync()

    def set_last_automatic_update_check(self, checked_at: datetime) -> None:
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        value = checked_at.astimezone(timezone.utc).isoformat()
        self._backend.setValue("updates/last_automatic_check_utc", value)
        self._backend.sync()
