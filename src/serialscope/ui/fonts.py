"""Bundled Dashboard numeric-display typefaces.

Default keeps the current MCUDesk value font. Other styles load once via
Qt's application font database and fall back to Default when a file is
missing or a string contains unsupported glyphs.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
import warnings

from PySide6.QtGui import QFont, QRawFont

from serialscope.resources import resource_path

FONTS_DIRECTORY = Path("assets/fonts")


class NumericDisplayStyle(StrEnum):
    """Stable identifiers stored in application settings."""

    DEFAULT = "default"
    SEVEN_SEGMENT = "seven_segment"
    FOURTEEN_SEGMENT = "fourteen_segment"
    LCD = "lcd"
    DOT_MATRIX = "dot_matrix"
    TECHNICAL_MONO = "technical_mono"


NUMERIC_DISPLAY_STYLES: tuple[NumericDisplayStyle, ...] = tuple(NumericDisplayStyle)

NUMERIC_DISPLAY_LABELS: dict[NumericDisplayStyle, str] = {
    NumericDisplayStyle.DEFAULT: "Default",
    NumericDisplayStyle.SEVEN_SEGMENT: "Seven Segment",
    NumericDisplayStyle.FOURTEEN_SEGMENT: "Fourteen Segment",
    NumericDisplayStyle.LCD: "LCD",
    NumericDisplayStyle.DOT_MATRIX: "Dot Matrix",
    NumericDisplayStyle.TECHNICAL_MONO: "Technical Mono",
}

# Modest, centralized size tweaks after visual comparison at 24 pt.
NUMERIC_DISPLAY_SIZE_SCALE: dict[NumericDisplayStyle, float] = {
    NumericDisplayStyle.DEFAULT: 1.0,
    NumericDisplayStyle.SEVEN_SEGMENT: 1.0,
    NumericDisplayStyle.FOURTEEN_SEGMENT: 1.0,
    NumericDisplayStyle.LCD: 1.0,
    NumericDisplayStyle.DOT_MATRIX: 0.92,
    NumericDisplayStyle.TECHNICAL_MONO: 1.0,
}


class _BundledFace:
    __slots__ = ("style", "relative_path", "family", "italic")

    def __init__(
        self,
        style: NumericDisplayStyle,
        relative_path: str,
        family: str,
        *,
        italic: bool = False,
    ) -> None:
        self.style = style
        self.relative_path = relative_path
        self.family = family
        self.italic = italic


_BUNDLED_FACES: tuple[_BundledFace, ...] = (
    _BundledFace(
        NumericDisplayStyle.SEVEN_SEGMENT,
        "DSEG7Classic-Regular.ttf",
        "DSEG7 Classic",
    ),
    _BundledFace(
        NumericDisplayStyle.LCD,
        "DSEG7Classic-Italic.ttf",
        "DSEG7 Classic",
        italic=True,
    ),
    _BundledFace(
        NumericDisplayStyle.FOURTEEN_SEGMENT,
        "DSEG14Classic-Regular.ttf",
        "DSEG14 Classic",
    ),
    _BundledFace(
        NumericDisplayStyle.DOT_MATRIX,
        "MatrixSansPrint-Regular.ttf",
        "Matrix Sans Print",
    ),
    _BundledFace(
        NumericDisplayStyle.TECHNICAL_MONO,
        "IBMPlexMono-Regular.ttf",
        "IBM Plex Mono",
    ),
)

_loaded = False
_families: dict[NumericDisplayStyle, str] = {}
_italic: dict[NumericDisplayStyle, bool] = {}
_failed: set[NumericDisplayStyle] = set()
_warned: set[str] = set()


def normalize_numeric_display_style(value: object) -> NumericDisplayStyle:
    """Return a known style, defaulting unknown or empty values to Default."""
    if isinstance(value, NumericDisplayStyle):
        return value
    token = str(value or "").strip().lower()
    for style in NumericDisplayStyle:
        if style.value == token:
            return style
    return NumericDisplayStyle.DEFAULT


def numeric_display_style_items() -> tuple[tuple[str, str], ...]:
    """Return (label, identifier) pairs for Preferences."""
    return tuple(
        (NUMERIC_DISPLAY_LABELS[style], style.value)
        for style in NUMERIC_DISPLAY_STYLES
    )


def load_numeric_display_fonts() -> None:
    """Load bundled TTF files once. Safe to call before any tile exists."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    from PySide6.QtGui import QFontDatabase

    for face in _BUNDLED_FACES:
        path = resource_path(FONTS_DIRECTORY / face.relative_path)
        family = _add_application_font(path, face.family)
        if family is None:
            _failed.add(face.style)
            continue
        _families[face.style] = family
        _italic[face.style] = face.italic


def _add_application_font(path: Path, family_hint: str) -> str | None:
    from PySide6.QtGui import QFontDatabase

    if not path.is_file():
        _warn_once(f"Dashboard numeric font is missing: {path.name}")
        return None
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id != -1:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            return families[0]
    if family_hint in QFontDatabase.families():
        return family_hint
    _warn_once(f"Dashboard numeric font could not be loaded: {path.name}")
    return None


def _warn_once(message: str) -> None:
    if message in _warned:
        return
    _warned.add(message)
    warnings.warn(message, RuntimeWarning, stacklevel=3)


def reset_numeric_display_fonts_for_tests() -> None:
    """Allow tests to re-run loading against a different asset root."""
    global _loaded
    _loaded = False
    _families.clear()
    _italic.clear()
    _failed.clear()
    _warned.clear()


def bundled_font_path(style: NumericDisplayStyle) -> Path | None:
    for face in _BUNDLED_FACES:
        if face.style is style:
            return resource_path(FONTS_DIRECTORY / face.relative_path)
    return None


def numeric_display_family(style: NumericDisplayStyle | str) -> str | None:
    """Return the Qt family for a bundled style, or None for Default/failure."""
    load_numeric_display_fonts()
    resolved = normalize_numeric_display_style(style)
    if resolved is NumericDisplayStyle.DEFAULT:
        return None
    return _families.get(resolved)


def numeric_display_font(style: NumericDisplayStyle | str) -> QFont | None:
    """Return a QFont for the style, or None to keep the current MCUDesk font."""
    load_numeric_display_fonts()
    resolved = normalize_numeric_display_style(style)
    if resolved is NumericDisplayStyle.DEFAULT:
        return None
    family = _families.get(resolved)
    if family is None:
        return None
    font = QFont(family)
    font.setItalic(_italic.get(resolved, False))
    font.setWeight(QFont.Weight.Normal)
    font.setStyleHint(QFont.StyleHint.SansSerif, QFont.StyleStrategy.PreferAntialias)
    font.setKerning(False)
    if resolved is NumericDisplayStyle.TECHNICAL_MONO:
        font.setStyleHint(QFont.StyleHint.Monospace, QFont.StyleStrategy.PreferAntialias)
        font.setFixedPitch(True)
    return font


def numeric_display_size_scale(style: NumericDisplayStyle | str) -> float:
    resolved = normalize_numeric_display_style(style)
    return NUMERIC_DISPLAY_SIZE_SCALE.get(resolved, 1.0)


def font_supports_text(font: QFont, text: str) -> bool:
    """True when every non-space character exists in the font itself."""
    raw = QRawFont.fromFont(font)
    if not raw.isValid():
        return False
    return all(raw.supportsCharacter(character) for character in text if not character.isspace())
