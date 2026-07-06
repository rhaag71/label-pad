"""Shared canvas-side text box layout helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, floor

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from label_pad.model import ObjectGeometry, TextObject
from label_pad.text_fonts import editor_font_for_text_object

MIN_TEXT_BOX_WIDTH = 24
MIN_TEXT_BOX_HEIGHT = 10
MIN_EDITOR_WIDTH = 48
TEXT_BOX_HORIZONTAL_PADDING = 1
TEXT_BOX_VERTICAL_PADDING = 1


@dataclass(frozen=True)
class CanvasTextLayout:
    """Canvas-side text box metrics shared by hit testing, selection, and editing."""

    text_object: TextObject
    font: QFont
    box_rect: QRectF

    def editor_rect(self, label_rect: QRect, scale: float) -> QRect:
        """Return an absolute editor rectangle clamped inside the label preview."""
        label_left = label_rect.x()
        label_top = label_rect.y()
        label_right = label_rect.x() + label_rect.width()
        label_bottom = label_rect.y() + label_rect.height()

        left = min(
            max(floor(label_left + self.box_rect.x() * scale), label_left),
            max(label_left, label_right - 1),
        )
        top = min(
            max(floor(label_top + self.box_rect.y() * scale), label_top),
            max(label_top, label_bottom - 1),
        )
        desired_width = max(MIN_EDITOR_WIDTH, ceil(self.box_rect.width() * scale))
        desired_height = max(
            1,
            ceil(self.box_rect.height() * scale),
            ceil(
                natural_text_box_height(
                    self.text_object,
                    self.box_rect.width(),
                )
                * scale
            ),
        )
        width = min(desired_width, max(1, label_right - left))
        height = min(desired_height, max(1, label_bottom - top))
        return QRect(left, top, width, height)


def measured_text_box_size(text_object: TextObject) -> tuple[float, float]:
    """Return a sane padded box size for text using the canvas render font."""
    return (
        natural_text_box_auto_width(text_object),
        natural_text_box_height(
            text_object,
            natural_text_box_auto_width(text_object),
        ),
    )


def natural_text_box_auto_width(
    text_object: TextObject,
    max_width: float | None = None,
) -> float:
    """Return the unwrapped width needed for explicit text lines."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    text_width = max(
        metrics.horizontalAdvance(line or " ")
        for line in (text_object.text or " ").split("\n")
    )
    width = text_width + TEXT_BOX_HORIZONTAL_PADDING * 2
    if max_width is not None:
        width = min(width, max(1, max_width))
    return width


def natural_text_box_minimum_width(text_object: TextObject) -> float:
    """Return the minimum width that avoids breaking unbreakable words."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    words = [
        word
        for line in (text_object.text or " ").split("\n")
        for word in line.split()
    ]
    text_width = max(
        [metrics.horizontalAdvance(word) for word in words]
        + [metrics.horizontalAdvance(" ")]
    )
    return max(MIN_TEXT_BOX_WIDTH, text_width + TEXT_BOX_HORIZONTAL_PADDING * 2)


def natural_text_box_height(text_object: TextObject, width: float) -> float:
    """Return the content-aware minimum box height for current text/font/wrap."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    inner_width = max(1, width - TEXT_BOX_HORIZONTAL_PADDING * 2)
    line_count = len(
        _wrapped_canvas_lines(
            text=text_object.text or " ",
            metrics=metrics,
            width=inner_width,
            wrap=text_object.wrap,
        )
    )
    return line_count * metrics.lineSpacing() + TEXT_BOX_VERTICAL_PADDING * 2


def canvas_text_layout(text_object: TextObject) -> CanvasTextLayout:
    """Return canvas text box layout backed by object geometry."""
    font = editor_font_for_text_object(text_object)
    width = text_object.geometry.width
    height = text_object.geometry.height
    if width <= 0 or height <= 0:
        width, height = measured_text_box_size(text_object)
    box_rect = QRectF(
        text_object.geometry.x,
        text_object.geometry.y,
        width,
        height,
    )
    return CanvasTextLayout(
        text_object=text_object,
        font=font,
        box_rect=box_rect,
    )


def text_object_bounds(text_object: TextObject) -> tuple[float, float, float, float]:
    """Return the shared padded text box bounds in label coordinates."""
    rect = canvas_text_layout(text_object).box_rect
    return (rect.x(), rect.y(), rect.width(), rect.height())


def clamped_text_box_size(
    text_object: TextObject,
    *,
    requested_width: float,
    requested_height: float,
    label_width: float,
    label_height: float,
    respect_minimum_width: bool = True,
) -> tuple[float, float]:
    """Return text box size constrained to content needs and label bounds."""
    max_width = max(1, label_width - text_object.geometry.x)
    max_height = max(1, label_height - text_object.geometry.y)
    min_width = (
        min(max_width, natural_text_box_minimum_width(text_object))
        if respect_minimum_width
        else min(max_width, MIN_TEXT_BOX_WIDTH)
    )
    width = min(max(requested_width, min_width), max_width)
    natural_height = natural_text_box_height(text_object, width)
    min_height = min(max_height, max(MIN_TEXT_BOX_HEIGHT, natural_height))
    height = min(max(requested_height, min_height), max_height)
    return width, height


def with_live_editor_text_box(
    text_object: TextObject,
    *,
    max_width: float | None = None,
) -> TextObject:
    """Return transient geometry for the active inline editor."""
    if text_object.auto_size:
        width = natural_text_box_auto_width(text_object, max_width=max_width)
        height = natural_text_box_height(text_object, width)
        return replace(
            text_object,
            geometry=replace(text_object.geometry, width=width, height=height),
        )
    return with_minimum_text_box_height(text_object)


def with_minimum_text_box_height(text_object: TextObject) -> TextObject:
    """Return transient geometry tall enough for current text content."""
    width = text_object.geometry.width
    if width <= 0:
        width, _ = measured_text_box_size(text_object)
    height = max(
        text_object.geometry.height,
        natural_text_box_height(text_object, width),
    )
    return replace(
        text_object,
        geometry=replace(text_object.geometry, width=width, height=height),
    )


def with_measured_text_box(text_object: TextObject) -> TextObject:
    """Return transient geometry using measured text width and current height."""
    width, height = measured_text_box_size(text_object)
    if text_object.geometry.height > 0:
        height = text_object.geometry.height
    return replace(
        text_object,
        geometry=replace(text_object.geometry, width=width, height=height),
    )


def measured_default_text_object(text_object: TextObject) -> TextObject:
    """Return a transient text object with measured default geometry."""
    width, height = measured_text_box_size(text_object)
    return replace(
        text_object,
        geometry=ObjectGeometry(
            x=text_object.geometry.x,
            y=text_object.geometry.y,
            width=width,
            height=height,
            rotation=text_object.geometry.rotation,
            selected=text_object.geometry.selected,
        ),
    )


def _wrapped_canvas_lines(
    *,
    text: str,
    metrics: QFontMetricsF,
    width: float,
    wrap: bool,
) -> list[str]:
    lines: list[str] = []
    paragraphs = text.split("\n") or [""]
    for paragraph in paragraphs:
        if not wrap:
            lines.append(paragraph)
            continue
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = word if current == "" else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = _fit_canvas_word(word, metrics, width, lines)
        lines.append(current)
    return lines


def _fit_canvas_word(
    word: str,
    metrics: QFontMetricsF,
    width: float,
    lines: list[str],
) -> str:
    current = ""
    for character in word:
        candidate = current + character
        if current and metrics.horizontalAdvance(candidate) > width:
            lines.append(current)
            current = character
        else:
            current = candidate
    return current
