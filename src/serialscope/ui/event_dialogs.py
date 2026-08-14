"""Small dialogs for creating and reviewing operator event markers."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import EventMarker


class AddEventDialog(QDialog):
    """Collect one non-empty operator annotation."""

    def __init__(self, elapsed_s: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Event")
        layout = QFormLayout(self)
        elapsed_display = QLineEdit(f"{elapsed_s:.3f} s")
        elapsed_display.setReadOnly(True)
        layout.addRow("Elapsed time", elapsed_display)
        self.event_input = QLineEdit()
        self.event_input.setObjectName("eventTextInput")
        self.event_input.setPlaceholderText("Operator note")
        layout.addRow("Event", self.event_input)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add Event")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.event_input.textChanged.connect(
            lambda text: self.buttons.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(bool(text.strip()))
        )
        layout.addRow(self.buttons)
        self.event_input.setFocus()

    @property
    def event_text(self) -> str:
        return self.event_input.text().strip()


class EventListDialog(QDialog):
    """Show immutable event timestamps and text for the current session."""

    def __init__(
        self, events: tuple[EventMarker, ...], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session Events")
        self.resize(560, 320)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(events), 2)
        self.table.setObjectName("eventListTable")
        self.table.setHorizontalHeaderLabels(("Elapsed Time", "Event"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        for row, marker in enumerate(events):
            elapsed_item = QTableWidgetItem(f"{marker.elapsed_s:.3f} s")
            elapsed_item.setData(Qt.ItemDataRole.UserRole, marker.event_id)
            self.table.setItem(row, 0, elapsed_item)
            self.table.setItem(row, 1, QTableWidgetItem(marker.text))
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
