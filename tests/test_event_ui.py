from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from serialscope.data import EventMarker
from serialscope.logging import RecordingSession, SessionConfig
from serialscope.ui.event_dialogs import AddEventDialog, EventListDialog
from serialscope.ui.main_window import MainWindow
from serialscope.ui.side_panel import SidePanel


def test_event_controls_follow_actual_recording_and_event_state() -> None:
    application = QApplication.instance() or QApplication([])
    panel = SidePanel()
    assert not panel.add_event_button.isEnabled()
    assert not panel.view_events_button.isEnabled()
    panel.set_connected(True)

    panel.set_logging_state(True, event_logging_available=True)
    assert panel.add_event_button.isEnabled()
    panel.set_events((EventMarker("one", 1.0, "Started pump"),))
    assert panel.view_events_button.isEnabled()
    assert panel.view_events_button.text() == "Events (1)"

    panel.set_logging_state(False)
    assert not panel.add_event_button.isEnabled()
    assert panel.view_events_button.isEnabled()
    panel.close()
    application.processEvents()


def test_add_dialog_rejects_empty_text_and_event_list_preserves_identity() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = AddEventDialog(1.25)
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()
    dialog.event_input.setText("  note  ")
    assert ok.isEnabled()
    assert dialog.event_text == "note"

    listing = EventListDialog((EventMarker("stable-id", 1.25, "note"),))
    assert listing.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == "stable-id"
    dialog.close()
    listing.close()
    application.processEvents()


def test_main_window_captures_timestamp_before_modal_confirmation(
    tmp_path, monkeypatch
) -> None:
    application = QApplication.instance() or QApplication([])

    class Clock:
        value = 100.0

        def __call__(self) -> float:
            return self.value

    clock = Clock()
    session = RecordingSession(
        clock=lambda: datetime(2026, 8, 14, tzinfo=timezone.utc),
        monotonic_clock=clock,
        event_id_factory=lambda: "event-1",
    )
    session.start(tmp_path, SessionConfig("Run", "COM4", 115200, "LF"))
    clock.value = 105.0

    class AcceptedDialog:
        event_text = "Operator confirmed"

        def __init__(self, elapsed_s, _parent):
            assert elapsed_s == 5.0

        def exec(self):
            clock.value = 115.0
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("serialscope.ui.main_window.AddEventDialog", AcceptedDialog)
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    window = MainWindow(port_scanner=lambda: [], recording_session=session)
    window._update_recording_presentation()

    window.add_event()

    assert session.events == (EventMarker("event-1", 5.0, "Operator confirmed"),)
    assert window.graphs_widget.events == session.events
    window.close()
    application.processEvents()


def test_cancelled_event_creates_no_row_or_graph_marker(tmp_path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession(
        clock=lambda: datetime(2026, 8, 14, tzinfo=timezone.utc),
        monotonic_clock=lambda: 100.0,
    )
    directory = session.start(
        tmp_path, SessionConfig("Cancel run", "COM4", 115200, "LF")
    )

    class CancelledDialog:
        event_text = "ignored"

        def __init__(self, _elapsed_s, _parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("serialscope.ui.main_window.AddEventDialog", CancelledDialog)
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    window = MainWindow(port_scanner=lambda: [], recording_session=session)
    window._update_recording_presentation()

    window.add_event()

    assert session.events == ()
    assert window.graphs_widget.events == ()
    with (directory / "events.csv").open(encoding="utf-8") as stream:
        assert len(stream.readlines()) == 1
    window.close()
    application.processEvents()
