"""Placeholder controls for the side panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.ui.channels_widget import ChannelsWidget
from serialscope.data import EventMarker


class SidePanel(QFrame):
    """Group future connection, channel, and session controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidePanel")
        self.setMinimumWidth(230)
        self._connected = False
        self._recording = False
        self._events: tuple[EventMarker, ...] = ()
        self._event_logging_available = False

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("sidePanelScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        content = QWidget()
        content.setObjectName("sidePanelContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        heading = QLabel("DEVICE")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading)

        layout.addWidget(self._connection_group())
        layout.addWidget(self._channels_group())
        layout.addWidget(self._session_group())
        layout.addStretch()
        self.scroll_area.setWidget(content)
        outer_layout.addWidget(self.scroll_area)
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

    def _channels_group(self) -> QGroupBox:
        group = QGroupBox("Channels")
        group.setObjectName("channelsSection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)

        self.channels_widget = ChannelsWidget()
        layout.addWidget(self.channels_widget)
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
        self.session_name_input.setPlaceholderText("Required")
        layout.addWidget(self.session_name_input)

        delimiter_label = QLabel("Data delimiter")
        layout.addWidget(delimiter_label)

        self.data_delimiter_combo = QComboBox()
        self.data_delimiter_combo.setObjectName("dataDelimiterCombo")
        self.data_delimiter_combo.addItem("Comma (,)", ",")
        self.data_delimiter_combo.addItem("Semicolon (;)", ";")
        self.data_delimiter_combo.addItem("Tab", "\t")
        layout.addWidget(self.data_delimiter_combo)

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

        event_row = QHBoxLayout()
        self.add_event_button = QPushButton("+ Add Event")
        self.add_event_button.setObjectName("addEventButton")
        event_row.addWidget(self.add_event_button)
        self.view_events_button = QPushButton("Events (0)")
        self.view_events_button.setObjectName("viewEventsButton")
        event_row.addWidget(self.view_events_button)
        layout.addLayout(event_row)

        self.logging_button = QPushButton("Start Logging")
        self.logging_button.setObjectName("loggingButton")
        layout.addWidget(self.logging_button)
        return group

    def set_connected(self, connected: bool) -> None:
        """Update recording availability for the serial connection state."""
        self._connected = connected
        self._update_logging_button_enabled()
        self._update_event_buttons()

    def set_logging_state(
        self,
        recording: bool,
        filename: str = "",
        byte_count: str = "0 B",
        elapsed: str = "00:00:00",
        event_logging_available: bool = True,
    ) -> None:
        """Present raw logging state without performing file operations."""
        self._recording = recording
        self._event_logging_available = recording and event_logging_available
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
        self.data_delimiter_combo.setEnabled(not recording)
        self._update_logging_button_enabled()
        self._update_event_buttons()

    def set_events(self, events: tuple[EventMarker, ...]) -> None:
        self._events = tuple(events)
        self.view_events_button.setText(f"Events ({len(self._events)})")
        self._update_event_buttons()

    @property
    def events(self) -> tuple[EventMarker, ...]:
        return self._events

    def _update_event_buttons(self) -> None:
        self.add_event_button.setEnabled(self._event_logging_available)
        self.view_events_button.setEnabled(bool(self._events))

    def _update_logging_button_enabled(self) -> None:
        self.logging_button.setEnabled(self._recording or self._connected)
