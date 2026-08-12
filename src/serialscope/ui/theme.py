"""Centralized application and graph theme application."""

from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE


@dataclass(frozen=True, slots=True)
class GraphPalette:
    background: str
    foreground: str


LIGHT_GRAPH_PALETTE = GraphPalette("#f5f7fa", "#263442")
DARK_GRAPH_PALETTE = GraphPalette("#0a1016", "#aebdca")


def apply_application_theme(application: QApplication, theme: str) -> GraphPalette:
    """Apply one validated theme and return its matching graph palette."""
    if theme == "light":
        application.setStyleSheet(LIGHT_STYLE)
        return LIGHT_GRAPH_PALETTE
    application.setStyleSheet(DARK_STYLE)
    return DARK_GRAPH_PALETTE
