import csv
import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from serialscope.replay import load_replay_session
from serialscope.ui.main_window import MainWindow


class ConnectedService:
    def __init__(self) -> None:
        self.is_connected = True
        self.disconnect_calls = 0

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.is_connected = False


def make_session(path: Path) -> Path:
    path.mkdir()
    (path / "session.json").write_text(
        json.dumps(
            {
                "session_name": "Thermal soak",
                "serialscope_version": "0.5.2",
                "structured_data_delimiter": ";",
                "serial": {"device": "/dev/ttyACM0", "baud_rate": 115200},
                "elapsed_seconds": 4000,
                "structured_row_count": 3,
            }
        ),
        encoding="utf-8",
    )
    with (path / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerows(
            [
                ["elapsed_s", "TC1", "RPM"],
                ["0", "20", ""],
                ["120.5", "21.5", "1000"],
                ["4000", "22", "1100"],
            ]
        )
    return path


def test_replay_populates_data_graphs_metadata_and_can_close(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.load_session(make_session(tmp_path / "session"))
    assert window.is_replay_mode
    assert window.replay_banner.text().startswith("Replay Mode — Thermal soak")
    assert "/dev/ttyACM0" in window.replay_banner.toolTip()
    assert window.data_widget.value_text("TC1") == "22"
    assert window.side_panel.channels_widget.value_text("RPM") == "1100"
    assert window.graphs_widget.channel_names == ("TC1", "RPM")
    assert window.dashboard_widget.channel_names == ("TC1", "RPM")
    assert window.dashboard_widget.selected_channels == ()
    window.dashboard_widget.set_channel_selected("TC1", True)
    assert window.dashboard_widget.tile_value_text("TC1") == "22"
    window.graphs_widget.set_channel_selected("TC1", True)
    x_values, y_values = window.graphs_widget._series["TC1"].getData()
    assert x_values.tolist() == pytest.approx([0.0, 120.5, 4000.0])
    assert y_values.tolist() == [20.0, 21.5, 22.0]
    assert not window.connection_bar.isEnabled()

    history_before = window.graphs_widget._series["TC1"].getData()[1].tolist()
    window.apply_theme("light")
    assert window.graphs_widget.selected_channels == ("TC1",)
    assert window.graphs_widget._series["TC1"].getData()[1].tolist() == history_before
    assert window.dashboard_widget.selected_channels == ("TC1",)
    assert window.dashboard_widget.tile_value_text("TC1") == "22"

    window.close_session()
    assert not window.is_replay_mode
    assert window.data_widget.channel_names == ()
    assert window.graphs_widget.channel_names == ()
    assert window.dashboard_widget.channel_names == ()
    assert window.dashboard_widget.tile_count == 0
    assert window.connection_bar.isEnabled()
    window.close()
    app.processEvents()


def test_load_error_is_presented_without_entering_replay(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, message: messages.append((title, message)),
    )
    window = MainWindow(port_scanner=lambda: [])

    assert not window.load_session(tmp_path / "missing")
    assert messages and messages[0][0] == "Session replay error"
    assert not window.is_replay_mode
    window.close()
    app.processEvents()


def test_sidebar_scrolls_vertically_only() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    area = window.side_panel.scroll_area
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    window.close()
    app.processEvents()


def test_loader_data_is_independent_of_live_parser(tmp_path: Path) -> None:
    session = load_replay_session(make_session(tmp_path / "session"))
    assert session.samples[-1].elapsed_s == 4000.0


def test_open_session_declined_disconnect_keeps_live_connection(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    connection = ConnectedService()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
    )
    directory_dialog_called = False

    def choose_directory(*_args) -> str:
        nonlocal directory_dialog_called
        directory_dialog_called = True
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose_directory)
    window = MainWindow(port_scanner=lambda: [], serial_connection=connection)

    window.open_session()

    assert connection.is_connected
    assert connection.disconnect_calls == 0
    assert not directory_dialog_called
    window.close()
    app.processEvents()


def test_confirmed_disconnect_allows_session_open(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    connection = ConnectedService()
    session_path = make_session(tmp_path / "session")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *_args: str(session_path)
    )
    window = MainWindow(port_scanner=lambda: [], serial_connection=connection)

    window.open_session()

    assert connection.disconnect_calls == 1
    assert window.is_replay_mode
    window.close()
    app.processEvents()


def test_active_recording_blocks_open_without_stopping_it(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    window = MainWindow(port_scanner=lambda: [])
    window._recording_session._started_at = window._recording_session._now()

    window.open_session()

    assert window._recording_session.is_recording
    assert warnings == ["Stop the active recording before opening a session."]
    # Restore the synthetic state; no files were opened by this test.
    window._recording_session._clear_active_state()
    window.close()
    app.processEvents()
