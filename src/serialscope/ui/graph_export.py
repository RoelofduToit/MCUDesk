"""Export the current Graphs plot as PNG or SVG without changing graph state."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgGenerator
from pyqtgraph.exporters import ImageExporter
from pyqtgraph.graphicsItems.PlotItem import PlotItem


class GraphExportError(Exception):
    """A user-presentable graph export failure."""


def default_graph_export_filename(suffix: str = ".png", when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    extension = suffix if suffix.startswith(".") else f".{suffix}"
    return f"MCUDesk_Graph_{stamp}{extension.lower()}"


def resolve_graph_export_path(path: Path, selected_filter: str = "") -> Path:
    """Append .png or .svg when the user omitted a supported extension."""
    suffix = path.suffix.lower()
    if suffix in {".png", ".svg"}:
        return path
    selected = selected_filter.lower()
    if ".svg" in selected:
        return path.with_suffix(".svg")
    if ".png" in selected or not suffix:
        return path.with_suffix(".png")
    raise GraphExportError("Unsupported graph export format. Choose PNG or SVG.")


def export_plot_item(plot_item: PlotItem, path: Path) -> None:
    """Write the current plot item using PyQtGraph exporters."""
    suffix = path.suffix.lower()
    if suffix == ".png":
        _export_png(plot_item, path)
        return
    if suffix == ".svg":
        _export_svg(plot_item, path)
        return
    raise GraphExportError("Unsupported graph export format. Choose PNG or SVG.")


def _export_png(plot_item: PlotItem, path: Path) -> None:
    try:
        exporter = ImageExporter(plot_item)
        width = int(plot_item.sceneBoundingRect().width())
        exporter.params["width"] = max(400, width)
        exporter.export(str(path))
    except GraphExportError:
        raise
    except Exception as error:
        raise GraphExportError(f"Could not export graph:\n\n{error}") from error
    if not path.is_file() or path.stat().st_size == 0:
        raise GraphExportError("Could not export graph:\n\nThe PNG file was not written.")


def _export_svg(plot_item: PlotItem, path: Path) -> None:
    """Render the plot scene to a vector SVG via Qt, not a PNG wrapper.

    PyQtGraph's SVGExporter in 0.13.7 fails on MCUDesk axis/grid path data,
    so Qt's SVG generator is used instead.
    """
    scene = plot_item.scene()
    if scene is None:
        raise GraphExportError("Could not export graph:\n\nThe plot has no scene.")
    target = plot_item.sceneBoundingRect()
    if target.width() < 1 or target.height() < 1:
        raise GraphExportError("Could not export graph:\n\nThe plot has no visible size.")
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(
        QSize(max(1, int(target.width())), max(1, int(target.height())))
    )
    generator.setViewBox(target)
    painter = QPainter()
    try:
        if not painter.begin(generator):
            raise GraphExportError("Could not export graph:\n\nCould not start SVG output.")
        scene.render(painter, target, target)
    except GraphExportError:
        raise
    except Exception as error:
        raise GraphExportError(f"Could not export graph:\n\n{error}") from error
    finally:
        if painter.isActive():
            painter.end()
    if not path.is_file() or path.stat().st_size == 0:
        raise GraphExportError("Could not export graph:\n\nThe SVG file was not written.")
