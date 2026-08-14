"""Shared, content-sized multi-channel selector controls."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QWidget,
)


class ChannelToggle(QFrame):
    """Checkable frame with separately laid-out indicator and text widgets."""

    toggled = Signal(bool)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("channelToggle")
        self.setProperty("checked", False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 3, 9, 3)
        layout.setSpacing(6)

        self.indicator = QCheckBox("")
        self.indicator.setObjectName("channelToggleIndicator")
        self.indicator.setAccessibleName(text)
        self.indicator.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.indicator.toggled.connect(self._indicator_toggled)
        layout.addWidget(
            self.indicator,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        self.label = QLabel(text)
        self.label.setObjectName("channelToggleLabel")
        self.label.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(
            self.label,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        self.setAccessibleName(text)

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str) -> None:  # noqa: N802
        self.label.setText(text)
        self.indicator.setAccessibleName(text)
        self.setAccessibleName(text)
        self.label.updateGeometry()
        self.updateGeometry()

    def isChecked(self) -> bool:  # noqa: N802
        return self.indicator.isChecked()

    def setChecked(self, selected: bool) -> None:  # noqa: N802
        self.indicator.setChecked(selected)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
            and self.isEnabled()
        ):
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setChecked(not self.isChecked())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space and self.isEnabled():
            self.setChecked(not self.isChecked())
            event.accept()
            return
        super().keyPressEvent(event)

    def _indicator_toggled(self, selected: bool) -> None:
        self.setProperty("checked", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.toggled.emit(selected)


class ChannelSelector(QScrollArea):
    """Horizontally scrolling collection of independent channel toggles."""

    selection_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("channelSelector")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(60)
        self.setMaximumHeight(76)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content.setObjectName("channelSelectorContent")
        self._layout = QHBoxLayout(self._content)
        self._layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        self.setWidget(self._content)

        self.toggles: dict[str, ChannelToggle] = {}

    @property
    def selected_keys(self) -> tuple[str, ...]:
        return tuple(key for key, toggle in self.toggles.items() if toggle.isChecked())

    def add_channel(
        self,
        key: str,
        text: str | None = None,
        *,
        tooltip: str = "",
    ) -> ChannelToggle:
        existing = self.toggles.get(key)
        if existing is not None:
            return existing
        toggle = ChannelToggle(text if text is not None else key, self._content)
        toggle.setProperty("channelName", key)
        toggle.setToolTip(tooltip)
        toggle.toggled.connect(
            lambda selected, channel=key: self.selection_changed.emit(
                channel, selected
            )
        )
        self._layout.insertWidget(self._layout.count() - 1, toggle)
        self.toggles[key] = toggle
        return toggle

    def remove_channel(self, key: str) -> None:
        toggle = self.toggles.pop(key, None)
        if toggle is None:
            return
        self._layout.removeWidget(toggle)
        toggle.deleteLater()

    def clear_channels(self) -> None:
        for key in tuple(self.toggles):
            self.remove_channel(key)

    def set_channel_text(self, key: str, text: str, *, tooltip: str = "") -> None:
        toggle = self.toggles[key]
        toggle.setText(text)
        toggle.setToolTip(tooltip)
        toggle.updateGeometry()

    def set_channel_checked(self, key: str, selected: bool) -> None:
        self.toggles[key].setChecked(selected)
