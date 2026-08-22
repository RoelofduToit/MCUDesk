import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session
from serialscope.ui.channel_tile import ChannelTile
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.ui.theme import apply_application_theme
from serialscope.ui.fonts import (
    FONTS_DIRECTORY,
    NUMERIC_DISPLAY_LABELS,
    NumericDisplayStyle,
    bundled_font_path,
    font_supports_text,
    load_numeric_display_fonts,
    normalize_numeric_display_style,
    numeric_display_family,
    numeric_display_font,
    reset_numeric_display_fonts_for_tests,
)
from serialscope.resources import resource_path


EXPECTED_FAMILIES = {
    NumericDisplayStyle.SEVEN_SEGMENT: "DSEG7 Classic",
    NumericDisplayStyle.LCD: "DSEG7 Classic",
    NumericDisplayStyle.FOURTEEN_SEGMENT: "DSEG14 Classic",
    NumericDisplayStyle.DOT_MATRIX: "Matrix Sans Print",
    NumericDisplayStyle.TECHNICAL_MONO: "IBM Plex Mono",
}


@pytest.fixture
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bundled_fonts(qapp: QApplication) -> None:
    reset_numeric_display_fonts_for_tests()
    load_numeric_display_fonts()


def test_unknown_style_identifier_falls_back_to_default() -> None:
    assert normalize_numeric_display_style(None) is NumericDisplayStyle.DEFAULT
    assert normalize_numeric_display_style("Neon") is NumericDisplayStyle.DEFAULT
    assert normalize_numeric_display_style("Seven Segment") is NumericDisplayStyle.DEFAULT
    assert (
        normalize_numeric_display_style("fourteen_segment")
        is NumericDisplayStyle.FOURTEEN_SEGMENT
    )


def test_each_installed_style_maps_to_expected_family(bundled_fonts) -> None:
    assert numeric_display_family(NumericDisplayStyle.DEFAULT) is None
    assert numeric_display_font(NumericDisplayStyle.DEFAULT) is None
    for style, family in EXPECTED_FAMILIES.items():
        assert numeric_display_family(style) == family
        font = numeric_display_font(style)
        assert font is not None
        assert font.family() == family
        assert font.italic() is (style is NumericDisplayStyle.LCD)


def test_bundled_font_files_are_resolved_from_assets(bundled_fonts) -> None:
    for style in EXPECTED_FAMILIES:
        path = bundled_font_path(style)
        assert path is not None
        assert path.is_file()
    assert (resource_path(FONTS_DIRECTORY) / "licenses").is_dir()


def test_missing_bundled_font_falls_back_without_raising(
    qapp: QApplication, tmp_path: Path, monkeypatch
) -> None:
    reset_numeric_display_fonts_for_tests()
    monkeypatch.setattr(
        "serialscope.ui.fonts.resource_path",
        lambda relative: tmp_path / Path(relative).name,
    )
    with pytest.warns(RuntimeWarning, match="missing"):
        load_numeric_display_fonts()
    assert numeric_display_font(NumericDisplayStyle.SEVEN_SEGMENT) is None
    assert numeric_display_family(NumericDisplayStyle.DOT_MATRIX) is None


def test_default_preserves_current_value_font(qapp: QApplication) -> None:
    tile = ChannelTile("TC1")
    original = QFont(tile.value_label.font())
    tile.set_value(25.3)
    tile.set_numeric_display_style(NumericDisplayStyle.DEFAULT)
    assert tile.value_label.font().family() == original.family()
    assert tile.value_label.property("numericFamily") in (None, "default")
    tile.close()
    qapp.processEvents()


def test_value_label_receives_display_font_other_labels_do_not(
    qapp: QApplication, bundled_fonts
) -> None:
    tile = ChannelTile("Temperature")
    tile.set_value(25.3)
    name_family = tile.name_label.font().family()
    unit_family = tile.unit_label.font().family()
    status_family = tile.status_label.font().family()
    tile.unit_label.setText("°C")

    tile.set_numeric_display_style(NumericDisplayStyle.SEVEN_SEGMENT)

    assert tile.value_label.font().family() == "DSEG7 Classic"
    assert tile.name_label.font().family() == name_family
    assert tile.unit_label.font().family() == unit_family
    assert tile.status_label.font().family() == status_family
    apply_application_theme(qapp, "dark")
    tile.set_numeric_display_style(NumericDisplayStyle.SEVEN_SEGMENT)
    assert tile.value_label.font().family() == "DSEG7 Classic"
    assert tile.value_label.font().pointSize() <= 24
    assert tile.value_label.font().pointSize() >= 11
    assert tile.name_label.font().family() == "Sans Serif"
    tile.close()
    qapp.processEvents()


def test_unsupported_glyphs_fall_back_to_default_font(
    qapp: QApplication, bundled_fonts
) -> None:
    tile = ChannelTile("TC1")
    default_family = tile.value_label.font().family()
    tile.set_numeric_display_style(NumericDisplayStyle.SEVEN_SEGMENT)
    tile.value_label.setText("—")
    tile._apply_numeric_display_font()
    assert tile.value_label.font().family() == default_family

    tile.set_value(25.3)
    assert tile.value_label.font().family() == "DSEG7 Classic"
    tile.close()
    qapp.processEvents()


def test_changing_style_updates_existing_tiles_without_geometry_change(
    qapp: QApplication, bundled_fonts
) -> None:
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A",), (25.3,)))
    widget.set_channel_selected("A", True)
    widget.set_tile_size_preset("Normal")
    widget.resize(980, 500)
    widget.show()
    qapp.processEvents()

    tile = widget._tiles["A"]
    geometry = tile.geometry()
    value = tile.value_label.text()
    widget.set_numeric_display_style(NumericDisplayStyle.DOT_MATRIX)
    qapp.processEvents()

    assert tile is widget._tiles["A"]
    assert tile.value_label.text() == value
    assert tile.geometry() == geometry
    assert tile.value_label.font().family() == "Matrix Sans Print"
    assert widget.numeric_display_style == "dot_matrix"
    widget.close()
    qapp.processEvents()


def test_new_tile_inherits_current_numeric_style(
    qapp: QApplication, bundled_fonts
) -> None:
    widget = DashboardWidget()
    widget.set_numeric_display_style("technical_mono")
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2)))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)

    assert widget._tiles["A"].value_label.font().family() == "IBM Plex Mono"
    assert widget._tiles["B"].value_label.font().family() == "IBM Plex Mono"
    widget.close()
    qapp.processEvents()


def test_replay_tiles_use_selected_numeric_style(
    qapp: QApplication, bundled_fonts, tmp_path: Path
) -> None:
    directory = tmp_path / "session"
    directory.mkdir()
    (directory / "session.json").write_text(
        json.dumps({"structured_data_delimiter": ","}), encoding="utf-8"
    )
    (directory / "data.csv").write_text(
        "elapsed_s,A\n0,1.5\n1,25.3\n", encoding="utf-8"
    )
    widget = DashboardWidget()
    widget.set_numeric_display_style(NumericDisplayStyle.FOURTEEN_SEGMENT)
    widget.load_replay(load_replay_session(directory))
    widget.set_channel_selected("A", True)

    assert widget.tile_value_text("A") == "25.3"
    assert widget._tiles["A"].value_label.font().family() == "DSEG14 Classic"
    widget.close()
    qapp.processEvents()


def test_fourteen_segment_supports_scientific_plus(bundled_fonts) -> None:
    font = numeric_display_font(NumericDisplayStyle.FOURTEEN_SEGMENT)
    seven = numeric_display_font(NumericDisplayStyle.SEVEN_SEGMENT)
    assert font is not None
    assert seven is not None
    assert font_supports_text(font, "1.23e+06")
    assert not font_supports_text(seven, "1.23e+06")
    assert font_supports_text(seven, "-25.3")


def test_style_labels_cover_shipped_identifiers() -> None:
    assert list(NUMERIC_DISPLAY_LABELS) == list(NumericDisplayStyle)
