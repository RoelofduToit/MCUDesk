import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.diagnostics import DiagnosticsHub
from serialscope.ui.diagnostics_dialog import DiagnosticsDialog
from serialscope.ui.main_window import MainWindow


def test_diagnostics_dialog_creates_and_reset_does_not_disconnect() -> None:
    application = QApplication.instance() or QApplication([])
    hub = DiagnosticsHub()
    hub.note_connected("default")
    hub.note_structured_update("default", ("TC1",))
    dialog = DiagnosticsDialog(hub, lambda: (("default", "Device 1"),))
    dialog.show()
    application.processEvents()
    assert dialog.windowTitle() == "Diagnostics"
    assert dialog.channel_table.columnCount() == 7
    assert dialog.status_value.objectName() == "diagnosticsValue"
    assert dialog.status_value.height() >= 16
    dialog._reset()
    application.processEvents()
    assert hub.live.snapshot("default").structured_updates == 0
    dialog.close()
    application.processEvents()


def test_main_window_has_tools_diagnostics_without_clutter() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.resize(1200, 800)
    window.show()
    application.processEvents()
    assert window.diagnostics_action.text() == "Diagnostics..."
    assert window.workspace_tabs.count() == 4
    assert "Diagnostics" not in [
        window.workspace_tabs.tabText(index) for index in range(4)
    ]
    bar_height = window.connection_bar.height()
    window._show_diagnostics()
    application.processEvents()
    assert window._diagnostics_dialog is not None
    assert window._diagnostics_dialog.isVisible()
    window.resize(900, 700)
    application.processEvents()
    assert window.connection_bar.height() < 220
    window._diagnostics_dialog.close()
    window.close()
    application.processEvents()
    assert bar_height < 120
