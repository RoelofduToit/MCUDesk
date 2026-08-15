"""Shared series colours for Graphs plots and dashboard sparklines."""

from collections.abc import Sequence

import pyqtgraph as pg
from PySide6.QtGui import QColor


SERIES_HUES = 12
SERIES_MIN_VALUE = 180
DARK_TILE_BACKGROUND = QColor("#151e28")
LIGHT_TILE_BACKGROUND = QColor("#F3F6F8")
_MIN_CONTRAST = 3.0


def series_color_at(index: int) -> QColor:
    """Return the Graphs-tab colour for a channel at a stable insertion index."""
    return QColor(pg.intColor(index, hues=SERIES_HUES, minValue=SERIES_MIN_VALUE))


def series_color_for_channel(name: str, ordered_names: Sequence[str]) -> QColor:
    """Colour one channel using the same index rule as the Graphs tab."""
    peers = color_peers(name, ordered_names)
    try:
        index = peers.index(name)
    except ValueError:
        index = len(peers)
    return series_color_at(index)


def color_peers(name: str, ordered_names: Sequence[str]) -> tuple[str, ...]:
    """Keep multi-source tiles aligned with that device's GraphsWidget."""
    group = _source_group(name)
    return tuple(item for item in ordered_names if _source_group(item) == group)


def sparkline_color_for_channel(
    name: str,
    ordered_names: Sequence[str],
    *,
    light_theme: bool = False,
) -> QColor:
    """Graphs colour, nudged only when the tile background would hide it."""
    background = LIGHT_TILE_BACKGROUND if light_theme else DARK_TILE_BACKGROUND
    return adapt_contrast(series_color_for_channel(name, ordered_names), background)


def adapt_contrast(color: QColor, background: QColor) -> QColor:
    """Preserve hue; adjust value only until the line is readable on the tile."""
    adapted = QColor(color)
    background_is_dark = _relative_luminance(background) < 0.5
    for _ in range(12):
        if _contrast_ratio(adapted, background) >= _MIN_CONTRAST:
            return adapted
        hue, saturation, value, alpha = adapted.getHsv()
        if hue < 0:
            return adapted
        if background_is_dark:
            value = min(255, value + 12)
        else:
            value = max(40, value - 12)
        adapted.setHsv(hue, saturation, value, alpha)
    return adapted


def _source_group(name: str) -> str:
    source_id, separator, _channel = name.partition("\x1f")
    return source_id if separator else ""


def _relative_luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        component = value / 255.0
        if component <= 0.03928:
            return component / 12.92
        return ((component + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def _contrast_ratio(first: QColor, second: QColor) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)
