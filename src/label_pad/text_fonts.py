"""Canvas-side text font helpers."""

from __future__ import annotations

from PySide6.QtGui import QFont

from label_pad.model import TextObject

QT_POINTS_PER_INCH = 72
DEFAULT_LOGICAL_DPI = 96


def editor_font_for_text_object(text_object: TextObject) -> QFont:
    """Return the inline editor font matching the rendered text style."""
    return _editor_font(text_object, font_size=text_object.font_size)


def editor_font_for_text_object_at_scale(
    text_object: TextObject,
    *,
    scale: float,
) -> QFont:
    """Return the inline editor font scaled for the widget preview."""
    return _editor_font(
        text_object,
        font_size=qt_point_size_for_document_points(text_object.font_size, scale=scale),
    )


def qt_point_size_for_document_points(
    font_size: float,
    *,
    scale: float = 1,
    logical_dpi: float = DEFAULT_LOGICAL_DPI,
) -> float:
    """Convert document points to a Qt point size for the current view scale."""
    return max(1, font_size * scale * QT_POINTS_PER_INCH / logical_dpi)


def _editor_font(text_object: TextObject, *, font_size: float) -> QFont:
    """Build a Qt font for text editing and canvas-side measurements."""
    font = QFont(text_object.font_family)
    font.setPointSizeF(font_size)
    font.setBold(text_object.bold)
    font.setItalic(text_object.italic)
    font.setUnderline(text_object.underline)
    return font
