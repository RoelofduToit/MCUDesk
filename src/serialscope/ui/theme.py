"""Centralized application and graph theme application."""

from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE


@dataclass(frozen=True, slots=True)
class GraphPalette:
    background: str
    foreground: str
    cursor: str
    readout_background: str
    event_marker: str
    event_marker_hover: str


LIGHT_GRAPH_PALETTE = GraphPalette(
    "#f5f7fa", "#263442", "#46697c", "#e4edf2", "#b4681c", "#854800"
)
DARK_GRAPH_PALETTE = GraphPalette(
    "#0a1016", "#aebdca", "#7ba9bf", "#182630", "#e0a04b", "#ffd089"
)


def apply_application_theme(application: QApplication, theme: str) -> GraphPalette:
    """Apply one validated theme and return its matching graph palette."""
    if theme == "light":
        application.setStyleSheet(LIGHT_STYLE)
        return LIGHT_GRAPH_PALETTE
    application.setStyleSheet(DARK_STYLE)
    return DARK_GRAPH_PALETTE
