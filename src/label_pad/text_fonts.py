"""Canvas-side text font helpers."""

from __future__ import annotations

from PySide6.QtGui import QFont

from label_pad.model import TextObject


def editor_font_for_text_object(text_object: TextObject) -> QFont:
    """Return the inline editor font matching the rendered text style."""
    return _editor_font(text_object, font_size=text_object.font_size)


def editor_font_for_text_object_at_scale(
    text_object: TextObject,
    *,
    scale: float,
) -> QFont:
    """Return the inline editor font scaled to widget preview pixels."""
    return _editor_font(text_object, font_size=max(1, text_object.font_size * scale))


def _editor_font(text_object: TextObject, *, font_size: float) -> QFont:
    """Build a Qt font for text editing and canvas-side measurements."""
    font = QFont(text_object.font_family)
    font.setPointSizeF(font_size)
    font.setBold(text_object.bold)
    font.setItalic(text_object.italic)
    font.setUnderline(text_object.underline)
    return font
