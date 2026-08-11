"""Placeholder controls for the side panel."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SidePanel(QFrame):
    """Group future connection, channel, and session controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self.setMinimumWidth(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        heading = QLabel("WORKSPACE")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        layout.addWidget(self._connection_group())
        layout.addWidget(self._channels_group())
        layout.addWidget(self._session_group())
        layout.addStretch()

    @staticmethod
    def _connection_group() -> QGroupBox:
        group = QGroupBox("Connection")
        group.setObjectName("connectionSection")
        form = QFormLayout(group)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(9)
        form.addRow("Data bits", QLabel("8"))
        form.addRow("Parity", QLabel("None"))
        form.addRow("Stop bits", QLabel("1"))
        form.addRow("Flow control", QLabel("None"))
        return group

    @staticmethod
    def _channels_group() -> QGroupBox:
        group = QGroupBox("Channels")
        group.setObjectName("channelsSection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.addWidget(QLabel("No channels configured"))
        add_button = QPushButton("Add channel")
        add_button.setObjectName("addChannelButton")
        layout.addWidget(add_button)
        return group

    @staticmethod
    def _session_group() -> QGroupBox:
        group = QGroupBox("Session / logging")
        group.setObjectName("sessionSection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        capture = QCheckBox("Capture session data")
        capture.setObjectName("captureCheckBox")
        layout.addWidget(capture)
        destination = QComboBox()
        destination.setObjectName("logFormatCombo")
        destination.addItems(["Text", "CSV"])
        layout.addWidget(destination)
        return group
