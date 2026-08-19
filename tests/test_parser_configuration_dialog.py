import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from serialscope.parsing import ColumnMapping, ParserConfiguration
from serialscope.ui.main_window import MainWindow
from serialscope.ui.parser_configuration_dialog import ParserConfigurationDialog


def test_dialog_creates_and_hides_mode_specific_controls() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ParserConfigurationDialog()
    assert dialog.mode_combo.currentData() == "auto"
    assert dialog.config_stack.currentIndex() == 0
    assert dialog.mapping_table.isHidden()

    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("delimited"))
    assert dialog.config_stack.currentIndex() == 1
    dialog.header_combo.setCurrentIndex(dialog.header_combo.findData("none"))
    assert not dialog.mapping_table.isHidden()

    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("key_value"))
    assert dialog.config_stack.currentIndex() == 2
    assert dialog.mapping_table.isHidden()

    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("json"))
    assert dialog.config_stack.currentIndex() == 3
    dialog.close()
    application.processEvents()


def test_mapping_preview_updates_from_sample() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ParserConfigurationDialog(
        ParserConfiguration(
            mode="delimited",
            delimiter="|",
            header_mode="none",
            columns=(
                ColumnMapping(0, "TC1"),
                ColumnMapping(1, "TC2"),
                ColumnMapping(2, "PRESSURE"),
                ColumnMapping(3, "RPM"),
            ),
        )
    )
    dialog.sample_input.setPlainText("23.4|25.1|101.3|1450")
    application.processEvents()
    assert dialog.preview_table.rowCount() == 4
    assert dialog.preview_table.item(0, 0).text() == "TC1"
    assert dialog.preview_table.item(0, 1).text() == "23.4"
    assert dialog.preview_table.item(0, 2).text() == "OK"
    dialog.close()
    application.processEvents()


def test_invalid_configuration_cannot_be_applied() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ParserConfigurationDialog()
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("delimited"))
    dialog.delimiter_combo.setCurrentIndex(dialog.delimiter_combo.findData("__custom__"))
    dialog.custom_delimiter.setText("")
    application.processEvents()
    apply_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not apply_button.isEnabled()
    dialog.close()
    application.processEvents()


def test_main_window_exposes_parser_configuration_without_clutter() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.show()
    application.processEvents()
    assert window.parser_configuration_action.text() == "Parser Configuration..."
    assert window.minimumSize().width() == 800
    assert window.minimumSize().height() == 520
    for width, height in ((1200, 800), (900, 700)):
        window.resize(width, height)
        application.processEvents()
        assert window.workspace_tabs.width() > 0
        assert window.side_panel.scroll_area.horizontalScrollBar().maximum() == 0
        assert window.connection_bar.width() <= window.width()
    window.close()
    application.processEvents()
