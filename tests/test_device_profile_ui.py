from datetime import datetime, timezone
import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from serialscope.data import AlarmLimits
from serialscope.logging import RecordingSession, SessionConfig
from serialscope.parsing import ChannelUpdate
from serialscope.profiles import DeviceIdentity, ProfileStore, SerialSettings
from serialscope.serial import SerialConnection, SerialPortInfo
from serialscope.ui.main_window import MainWindow
from serialscope.ui.profile_dialogs import ProfileNameDialog


class Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)


class Reader:
    def __init__(self, _connection) -> None:
        self.bytes_received = Signal()
        self.failed = Signal()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def _store(tmp_path) -> ProfileStore:
    return ProfileStore(tmp_path / "profiles.json")


def _create_profile(store: ProfileStore, name="Reactor Pico", **overrides):
    values = {
        "serial": SerialSettings(baud_rate=230400, line_ending="CRLF"),
        "parser": "auto",
        "device_identity": DeviceIdentity(
            vid=0x2E8A, pid=0x000A, serial_number="PICO-001"
        ),
        "last_port": "/dev/ttyACM0",
        "channels": {
            "TC1": {
                "alias": "Reactor Temperature",
                "unit": "°C",
                "alarms": {"high": 500},
            },
            "OLD": {"alias": "Old Firmware Channel", "unit": "V"},
        },
    }
    values.update(overrides)
    return store.create(name, **values)


def test_profile_name_dialog_requires_non_whitespace_name() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ProfileNameDialog("Save Device Profile")
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not save.isEnabled()
    dialog.name_input.setText("   ")
    assert not save.isEnabled()
    dialog.name_input.setText("  Reactor Pico  ")
    assert save.isEnabled()
    assert dialog.profile_name == "Reactor Pico"
    dialog.close()
    application.processEvents()


def test_custom_mode_is_default_and_profile_apply_does_not_connect(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    store = _store(tmp_path)
    profile = _create_profile(store)
    port = SerialPortInfo(
        "/dev/ttyACM1",
        vid=0x2E8A,
        pid=0x000A,
        serial_number="PICO-001",
    )
    window = MainWindow(port_scanner=lambda: [port], profile_store=store)

    assert window.connection_bar.profile_combo.currentText() == "Custom"
    assert window.connection_bar.source_combo.isHidden()
    window.connection_bar.profile_combo.setCurrentIndex(
        window.connection_bar.profile_combo.findData(profile.profile_id)
    )

    source = window._selected_source
    assert not source.is_connected
    assert source.baud_rate == 230400
    assert source.line_ending == "CRLF"
    assert window.connection_bar.selected_device == "/dev/ttyACM1"
    assert window.connection_bar.profile_status_label.text() == "Detected"
    presentation = window._channel_metadata.get("TC1")
    assert presentation.alias == "Reactor Temperature"
    assert presentation.unit == "°C"
    assert presentation.alarms == AlarmLimits(high=500)
    assert window.side_panel.channels_widget.value_text("OLD") is None

    window._handle_source_update(
        source.source_id, ChannelUpdate(("TC1", "NEW"), (450, 10))
    )
    assert window._channel_metadata.get("NEW").alias == ""
    assert window.side_panel.channels_widget.value_text("NEW") == "10"
    window._channel_metadata.set("TC1", "Changed locally", "K")
    window._apply_channel_metadata()
    assert store.get(profile.profile_id).channels["TC1"]["unit"] == "°C"
    window.close()
    application.processEvents()


def test_multi_device_sources_keep_independent_profile_associations(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    store = _store(tmp_path)
    pico = _create_profile(store, "Pico")
    arduino = _create_profile(
        store,
        "Arduino",
        serial=SerialSettings(baud_rate=9600, line_ending="LF"),
        device_identity=DeviceIdentity(vid=0x2341, pid=0x0043),
    )
    window = MainWindow(port_scanner=lambda: [], profile_store=store)
    first_id = window._selected_source_id
    window.connection_bar.profile_combo.setCurrentIndex(
        window.connection_bar.profile_combo.findData(pico.profile_id)
    )
    window.connection_bar.add_source_button.click()
    second_id = window._selected_source_id
    window.connection_bar.profile_combo.setCurrentIndex(
        window.connection_bar.profile_combo.findData(arduino.profile_id)
    )

    assert window._source_profiles == {
        first_id: pico.profile_id,
        second_id: arduino.profile_id,
    }
    assert window._source_manager.get(first_id).baud_rate == 230400
    assert window._source_manager.get(second_id).baud_rate == 9600
    window.close()
    application.processEvents()


def test_ambiguous_profile_requires_manual_port_choice(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    store = _store(tmp_path)
    profile = _create_profile(
        store,
        device_identity=DeviceIdentity(
            vid=0x10C4, pid=0xEA60, manufacturer="Silicon Labs"
        ),
    )
    ports = [
        SerialPortInfo(
            "COM4", vid=0x10C4, pid=0xEA60, manufacturer="Silicon Labs"
        ),
        SerialPortInfo(
            "COM5", vid=0x10C4, pid=0xEA60, manufacturer="Silicon Labs"
        ),
    ]
    window = MainWindow(port_scanner=lambda: ports, profile_store=store)
    window.connection_bar.profile_combo.setCurrentIndex(
        window.connection_bar.profile_combo.findData(profile.profile_id)
    )

    assert window.connection_bar.profile_status_label.text() == "Choose port"
    assert window.connection_bar.selected_port is None
    window.connection_bar.port_combo.setCurrentIndex(1)
    assert window.connection_bar.selected_device == "COM5"
    window.close()
    application.processEvents()


def test_profile_controls_lock_for_connection_and_recording(tmp_path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4", in_waiting=0)
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=Reader,
        profile_store=_store(tmp_path),
    )
    window.connection_bar.connect_button.click()
    assert not window.connection_bar.profile_combo.isEnabled()
    window.connection_bar.connect_button.click()
    assert window.connection_bar.profile_combo.isEnabled()
    window.close()

    session = RecordingSession(
        clock=lambda: datetime(2026, 8, 14, tzinfo=timezone.utc)
    )
    session.start(tmp_path / "sessions", SessionConfig("Run", "COM4", 115200, "LF"))
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    recording_window = MainWindow(
        port_scanner=lambda: [],
        recording_session=session,
        profile_store=_store(tmp_path),
    )
    recording_window._update_recording_presentation()
    assert not recording_window.connection_bar.profile_combo.isEnabled()
    recording_window.close()
    application.processEvents()


def test_profile_save_update_rename_and_delete_actions(tmp_path, monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    store = _store(tmp_path)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")], profile_store=store
    )
    names = iter(("Bench Controller", "Renamed Controller"))

    class AcceptedNameDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            self.profile_name = next(names)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "serialscope.ui.main_window.ProfileNameDialog", AcceptedNameDialog
    )
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )
    window._save_current_profile()
    profile_id = window.connection_bar.selected_profile_id
    assert profile_id is not None

    window.connection_bar.baud_combo.setCurrentText("460800")
    window._update_current_profile()
    assert store.get(profile_id).serial.baud_rate == 460800
    window._rename_current_profile()
    assert store.get(profile_id).name == "Renamed Controller"
    window._delete_current_profile()
    assert store.profiles == ()
    assert window.connection_bar.profile_combo.currentText() == "Custom"
    window.close()
    application.processEvents()


def test_theme_switch_preserves_selected_profile(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    store = _store(tmp_path)
    profile = _create_profile(store)
    window = MainWindow(port_scanner=lambda: [], profile_store=store)
    window.connection_bar.profile_combo.setCurrentIndex(
        window.connection_bar.profile_combo.findData(profile.profile_id)
    )

    window.apply_theme("light")
    assert window.connection_bar.selected_profile_id == profile.profile_id
    window.apply_theme("dark")
    assert window.connection_bar.selected_profile_id == profile.profile_id
    window.close()
    application.processEvents()


def test_corrupt_profile_storage_does_not_prevent_window_startup(
    tmp_path, monkeypatch
) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "profiles.json"
    path.write_text("{broken", encoding="utf-8")
    warnings = []
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.warning",
        lambda *_args: warnings.append(_args[-1]),
    )
    window = MainWindow(port_scanner=lambda: [], profile_store=ProfileStore(path))
    application.processEvents()

    assert window.windowTitle() == "MCUDesk"
    assert not window.connection_bar.profile_combo.isEnabled()
    assert warnings and "left unchanged" in warnings[0]
    assert path.read_text("utf-8") == "{broken"
    window.close()
    application.processEvents()
