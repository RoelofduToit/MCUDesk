"""Placeholder controls for the side panel."""

from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

        heading = QLabel("DEVICE")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        layout.addWidget(self._connection_group())
        layout.addWidget(self._channels_group())
        layout.addWidget(self._session_group())
        layout.addStretch()
        self.set_connected(False)

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

    def _session_group(self) -> QGroupBox:
        group = QGroupBox("Session / logging")
        group.setObjectName("sessionSection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)

        session_name_label = QLabel("Session name")
        layout.addWidget(session_name_label)

        self.session_name_input = QLineEdit()
        self.session_name_input.setObjectName("sessionNameInput")
        self.session_name_input.setPlaceholderText("Optional")
        layout.addWidget(self.session_name_input)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(7)

        self.logging_status_dot = QLabel("●")
        self.logging_status_dot.setObjectName("loggingStatusDot")
        self.logging_status_dot.setProperty("recordingState", "inactive")
        status_layout.addWidget(self.logging_status_dot)

        self.logging_status_label = QLabel("Not recording")
        self.logging_status_label.setObjectName("loggingStatusLabel")
        status_layout.addWidget(self.logging_status_label)
        status_layout.addStretch()
        layout.addWidget(status_row)

        self.logging_filename_label = QLabel("")
        self.logging_filename_label.setObjectName("loggingFilenameLabel")
        self.logging_filename_label.setWordWrap(True)
        layout.addWidget(self.logging_filename_label)

        self.recording_elapsed_label = QLabel("00:00:00")
        self.recording_elapsed_label.setObjectName("recordingElapsedLabel")
        layout.addWidget(self.recording_elapsed_label)

        self.logged_bytes_label = QLabel("Logged: 0 B")
        self.logged_bytes_label.setObjectName("loggedBytesLabel")
        layout.addWidget(self.logged_bytes_label)

        self.logging_button = QPushButton("Start Logging")
        self.logging_button.setObjectName("loggingButton")
        layout.addWidget(self.logging_button)
        return group

    def set_connected(self, connected: bool) -> None:
        """Allow starting a recording only while serial is connected."""
        if self.logging_button.text() == "Start Logging":
            self.logging_button.setEnabled(connected)

    def set_logging_state(
        self,
        recording: bool,
        filename: str = "",
        byte_count: str = "0 B",
        elapsed: str = "00:00:00",
    ) -> None:
        """Present raw logging state without performing file operations."""
        self.logging_status_label.setText("Recording" if recording else "Not recording")
        state = "active" if recording else "inactive"
        self.logging_status_dot.setProperty("recordingState", state)
        self.logging_status_dot.style().unpolish(self.logging_status_dot)
        self.logging_status_dot.style().polish(self.logging_status_dot)
        self.logging_filename_label.setText(filename)
        self.recording_elapsed_label.setText(elapsed)
        self.logged_bytes_label.setText(f"Logged: {byte_count}")
        self.logging_button.setText("Stop Logging" if recording else "Start Logging")
        self.session_name_input.setEnabled(not recording)
