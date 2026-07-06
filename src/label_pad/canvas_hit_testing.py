"""Canvas text object hit testing helpers."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from label_pad.model import LabelDocument, TextObject
from label_pad.text_layout import canvas_text_layout

TEXT_BOX_HIT_SLOP = 4
RESIZE_HANDLE_SIZE = 6
RESIZE_HANDLE_HIT_SLOP = 3


def text_object_hit_rect(text_object: TextObject) -> QRectF:
    """Return the forgiving interaction bounds without changing visible geometry."""
    return canvas_text_layout(text_object).box_rect.adjusted(
        -TEXT_BOX_HIT_SLOP,
        -TEXT_BOX_HIT_SLOP,
        TEXT_BOX_HIT_SLOP,
        TEXT_BOX_HIT_SLOP,
    )


def text_object_resize_handle_rect(text_object: TextObject) -> QRectF:
    """Return the visible bottom-right resize handle for a text object."""
    box_rect = canvas_text_layout(text_object).box_rect
    return QRectF(
        box_rect.right() - RESIZE_HANDLE_SIZE,
        box_rect.bottom() - RESIZE_HANDLE_SIZE,
        RESIZE_HANDLE_SIZE,
        RESIZE_HANDLE_SIZE,
    )


def text_object_resize_handle_hit_rect(text_object: TextObject) -> QRectF:
    """Return the forgiving hit bounds for the visible resize handle."""
    return text_object_resize_handle_rect(text_object).adjusted(
        -RESIZE_HANDLE_HIT_SLOP,
        -RESIZE_HANDLE_HIT_SLOP,
        RESIZE_HANDLE_HIT_SLOP,
        RESIZE_HANDLE_HIT_SLOP,
    )


def hit_test_text_resize_handle(
    document: LabelDocument,
    *,
    x: float,
    y: float,
) -> TextObject | None:
    """Return the topmost selected text object whose resize handle contains a point."""
    for label_object in reversed(document.selected_objects()):
        if not isinstance(label_object, TextObject):
            continue
        if text_object_resize_handle_hit_rect(label_object).contains(x, y):
            return label_object
    return None


def hit_test_text_object(
    document: LabelDocument,
    *,
    x: float,
    y: float,
) -> TextObject | None:
    """Return the topmost text object whose estimated bounds contain a point."""
    for label_object in reversed(document.objects):
        if not isinstance(label_object, TextObject):
            continue
        if text_object_hit_rect(label_object).contains(x, y):
            return label_object
    return None
