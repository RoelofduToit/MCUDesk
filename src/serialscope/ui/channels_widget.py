"""Scrollable presentation of detected channel values."""

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate


class ChannelsWidget(QWidget):
    """Retain channel labels and update their latest values in place."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.empty_label = QLabel("No channels detected")
        self.empty_label.setObjectName("channelsEmptyLabel")
        layout.addWidget(self.empty_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("channelsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setMaximumHeight(220)

        content = QWidget()
        self._form = QFormLayout(content)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(7)
        self.scroll_area.setWidget(content)
        self.scroll_area.hide()
        layout.addWidget(self.scroll_area)

        self._value_labels: dict[str, QLabel] = {}

    def update_channels(self, update: ChannelUpdate) -> None:
        """Display a channel update, rebuilding only for a new header."""
        if tuple(self._value_labels) != update.names:
            self._rebuild(update.names)

        for name, value in zip(update.names, update.values, strict=True):
            self._value_labels[name].setText(str(value))

    def reset(self) -> None:
        """Clear definitions and return to the empty state."""
        while self._form.rowCount():
            self._form.removeRow(0)
        self._value_labels.clear()
        self.scroll_area.hide()
        self.empty_label.show()

    def value_text(self, name: str) -> str | None:
        label = self._value_labels.get(name)
        return label.text() if label is not None else None

    def _rebuild(self, names: tuple[str, ...]) -> None:
        self.reset()
        for name in names:
            value_label = QLabel("—")
            value_label.setObjectName("channelValueLabel")
            self._form.addRow(name, value_label)
            self._value_labels[name] = value_label
        self.empty_label.hide()
        self.scroll_area.show()
