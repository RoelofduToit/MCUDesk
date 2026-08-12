import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.ui.graphs_widget import GraphsWidget


def test_graphs_widget_has_professional_empty_state() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()

    assert widget.empty_label.text() == "No channels are currently plotted."
    application.processEvents()
