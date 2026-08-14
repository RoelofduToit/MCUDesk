import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from serialscope.ui.channel_selector import ChannelSelector, ChannelToggle
from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE


def test_shared_selector_supports_independent_multiple_selection() -> None:
    application = QApplication.instance() or QApplication([])
    selector = ChannelSelector()
    changes: list[tuple[str, bool]] = []
    selector.selection_changed.connect(
        lambda channel, selected: changes.append((channel, selected))
    )
    first = selector.add_channel("one", "Channel 1")
    second = selector.add_channel("two", "Channel 2")
    selector.add_channel("three", "Channel 3")

    selector.set_channel_checked("one", True)
    second.setFocus(Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(second, Qt.Key.Key_Space)

    assert selector.selected_keys == ("one", "two")
    assert changes == [("one", True), ("two", True)]
    assert first.isChecked()
    assert second.isChecked()
    selector.close()
    application.processEvents()


def test_toggle_separates_textless_indicator_from_complete_label() -> None:
    application = QApplication.instance() or QApplication([])
    toggle = ChannelToggle("Reactor Temperature")

    assert toggle.indicator.text() == ""
    assert toggle.indicator.accessibleName() == "Reactor Temperature"
    assert toggle.label.text() == "Reactor Temperature"
    assert toggle.text() == "Reactor Temperature"
    assert toggle.accessibleName() == "Reactor Temperature"
    toggle.close()
    application.processEvents()


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
@pytest.mark.parametrize(
    "label",
    ["Channel 1", "Channel 8", "Channel 10", "Reactor Temperature"],
)
def test_toggle_size_uses_its_actual_rendered_label(
    stylesheet: str,
    label: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(stylesheet)
    toggle = ChannelToggle(label)
    toggle.show()
    application.processEvents()
    unchecked_width = toggle.width()
    unchecked_indicator_hint = toggle.indicator.sizeHint()
    unchecked_indicator_geometry = toggle.indicator.geometry().size()
    label_hint = toggle.label.sizeHint().width()
    label_minimum = toggle.label.minimumSizeHint().width()

    toggle.setChecked(True)
    application.processEvents()

    assert toggle.label.width() >= label_hint
    assert toggle.label.width() >= label_minimum
    assert toggle.minimumSizeHint().width() >= toggle.label.minimumSizeHint().width()
    assert toggle.width() == unchecked_width
    assert toggle.width() >= toggle.minimumSizeHint().width()
    assert 26 <= toggle.height() <= 30
    assert abs(toggle.indicator.geometry().center().y() - toggle.label.geometry().center().y()) <= 1
    assert toggle.indicator.sizeHint() == unchecked_indicator_hint
    assert toggle.indicator.geometry().size() == unchecked_indicator_geometry
    toggle.close()
    application.processEvents()


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_selector_scrolls_instead_of_compressing_channel_toggles(
    stylesheet: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(stylesheet)
    selector = ChannelSelector()
    labels = (
        "Channel 1",
        "Channel 2",
        "Channel 8",
        "Channel 9",
        "Channel 10",
        "PRESSURE",
        "Reactor Temperature",
        "Outlet Pressure",
    )
    for label in labels:
        selector.add_channel(label, label)
    selector.resize(650, 70)
    selector.show()
    application.processEvents()

    assert selector.horizontalScrollBar().maximum() > 0
    for toggle in selector.toggles.values():
        assert toggle.width() >= toggle.minimumSizeHint().width()
        assert toggle.width() >= toggle.sizeHint().width()
    selector.close()
    application.processEvents()


def test_clicking_label_area_toggles_the_whole_control() -> None:
    application = QApplication.instance() or QApplication([])
    toggle = ChannelToggle("Channel 8")
    toggle.show()
    application.processEvents()

    QTest.mouseClick(
        toggle,
        Qt.MouseButton.LeftButton,
        pos=toggle.label.geometry().center(),
    )

    assert toggle.isChecked()
    toggle.close()
    application.processEvents()
