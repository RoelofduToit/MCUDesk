"""A simple HMI-style presentation tile for one structured channel."""

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


def format_dashboard_value(value: int | float) -> str:
    """Format a numeric measurement compactly without guessing units."""
    if isinstance(value, int):
        return str(value)
    numeric = float(value)
    if not math.isfinite(numeric):
        return "—"
    magnitude = abs(numeric)
    if numeric == 0 or 0.0001 <= magnitude < 1_000_000_000:
        return f"{numeric:.6f}".rstrip("0").rstrip(".")
    return f"{numeric:.6g}"


class ChannelTile(QFrame):
    """Display a channel name and its latest structured numeric value."""

    def __init__(self, channel_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_name = channel_name
        self.setObjectName("dashboardChannelTile")
        self.setMinimumSize(180, 112)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        self.name_label = QLabel(channel_name)
        self.name_label.setObjectName("dashboardTileName")
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.name_label)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("dashboardTileValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.value_label, 1)

    def set_value(self, value: int | float) -> None:
        self.value_label.setText(format_dashboard_value(value))
