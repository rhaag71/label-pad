"""Document rendering contexts and renderer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPixmap
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from label_pad.model import ImageObject, LabelDocument, TextObject
from label_pad.text_layout import (
    TEXT_BOX_HORIZONTAL_PADDING,
    TEXT_BOX_VERTICAL_PADDING,
)


class RenderContext(ABC):
    """Abstract drawing target used by the document renderer."""

    @abstractmethod
    def draw_text(
        self,
        *,
        x: float,
        y: float,
        text: str,
        font_family: str,
        font_size: float,
        bold: bool,
        italic: bool,
        underline: bool,
        width: float = 0,
        height: float = 0,
        wrap: bool = False,
        alignment: str = "left",
        text_color: str = "black",
        rotation: float = 0,
    ) -> None:
        """Draw text."""

    @abstractmethod
    def draw_image(
        self,
        *,
        x: float,
        y: float,
        image_path: Path,
        display_width: float,
        display_height: float,
        keep_aspect_ratio: bool,
        rotation: float = 0,
    ) -> None:
        """Draw an image."""

    @abstractmethod
    def draw_rectangle(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float = 0,
    ) -> None:
        """Draw a rectangle."""


class QtRenderContext(RenderContext):
    """Qt painter-backed render context."""

    def __init__(self, painter: QPainter) -> None:
        self._painter = painter

    def draw_text(
        self,
        *,
        x: float,
        y: float,
        text: str,
        font_family: str,
        font_size: float,
        bold: bool,
        italic: bool,
        underline: bool,
        width: float = 0,
        height: float = 0,
        wrap: bool = False,
        alignment: str = "left",
        text_color: str = "black",
        rotation: float = 0,
    ) -> None:
        self._painter.save()
        self._painter.translate(x, y)
        self._painter.rotate(rotation)
        font = QFont(font_family)
        font.setPointSizeF(font_size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)
        self._painter.setFont(font)
        self._painter.setPen(Qt.GlobalColor.black)
        if width > 0 and height > 0:
            text_flags = _qt_alignment_flag(alignment) | Qt.AlignmentFlag.AlignTop
            if wrap:
                text_flags |= Qt.TextFlag.TextWordWrap
            self._painter.drawText(
                QRectF(
                    TEXT_BOX_HORIZONTAL_PADDING,
                    TEXT_BOX_VERTICAL_PADDING,
                    max(1, width - TEXT_BOX_HORIZONTAL_PADDING * 2),
                    max(1, height - TEXT_BOX_VERTICAL_PADDING * 2),
                ),
                text_flags,
                text,
            )
        else:
            self._painter.drawText(
                TEXT_BOX_HORIZONTAL_PADDING,
                TEXT_BOX_VERTICAL_PADDING + QFontMetricsF(font).ascent(),
                text,
            )
        self._painter.restore()

    def draw_image(
        self,
        *,
        x: float,
        y: float,
        image_path: Path,
        display_width: float,
        display_height: float,
        keep_aspect_ratio: bool,
        rotation: float = 0,
    ) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return

        self._painter.save()
        self._painter.translate(x, y)
        self._painter.rotate(rotation)
        target = QRectF(0, 0, display_width, display_height)
        if keep_aspect_ratio:
            pixmap = pixmap.scaled(
                int(display_width),
                int(display_height),
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
            )
            target = QRectF(0, 0, pixmap.width(), pixmap.height())
        self._painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        self._painter.restore()

    def draw_rectangle(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float = 0,
    ) -> None:
        self._painter.save()
        self._painter.translate(x, y)
        self._painter.rotate(rotation)
        self._painter.drawRect(QRectF(0, 0, width, height))
        self._painter.restore()


class PdfRenderContext(RenderContext):
    """ReportLab canvas-backed render context."""

    def __init__(self, pdf: Canvas, page_height: float) -> None:
        self._pdf = pdf
        self._page_height = page_height

    def draw_text(
        self,
        *,
        x: float,
        y: float,
        text: str,
        font_family: str,
        font_size: float,
        bold: bool,
        italic: bool,
        underline: bool,
        width: float = 0,
        height: float = 0,
        wrap: bool = False,
        alignment: str = "left",
        text_color: str = "black",
        rotation: float = 0,
    ) -> None:
        self._pdf.saveState()
        font_name = _pdf_font_name(font_family, bold, italic)
        if width > 0 and height > 0:
            self._draw_box_text(
                x=x,
                y=y,
                text=text,
                font_name=font_name,
                font_size=font_size,
                underline=underline,
                width=width,
                height=height,
                wrap=wrap,
                alignment=alignment,
                rotation=rotation,
            )
            self._pdf.restoreState()
            return

        self._pdf.translate(
            x + TEXT_BOX_HORIZONTAL_PADDING,
            self._top_to_bottom_y(
                y + TEXT_BOX_VERTICAL_PADDING,
                font_size,
            ),
        )
        self._pdf.rotate(rotation)
        self._pdf.setFillColorRGB(0, 0, 0)
        self._pdf.setFont(font_name, font_size)
        self._pdf.drawString(0, 0, text)
        if underline:
            self._draw_pdf_underline(
                x=0,
                y=-1,
                width=_pdf_text_width(text, font_name, font_size),
            )
        self._pdf.restoreState()

    def _draw_box_text(
        self,
        *,
        x: float,
        y: float,
        text: str,
        font_name: str,
        font_size: float,
        underline: bool,
        width: float,
        height: float,
        wrap: bool,
        alignment: str,
        rotation: float,
    ) -> None:
        self._pdf.translate(x, self._page_height - y)
        self._pdf.rotate(rotation)
        self._pdf.setFillColorRGB(0, 0, 0)
        self._pdf.setFont(font_name, font_size)
        inner_width = max(1, width - TEXT_BOX_HORIZONTAL_PADDING * 2)
        inner_height = max(1, height - TEXT_BOX_VERTICAL_PADDING * 2)
        line_height = font_size * 1.2
        lines = _wrap_pdf_text(
            text=text,
            font_name=font_name,
            font_size=font_size,
            width=inner_width,
            wrap=wrap,
        )
        max_lines = max(1, int(inner_height // line_height))
        y_position = -TEXT_BOX_VERTICAL_PADDING - font_size
        for line in lines[:max_lines]:
            line_width = _pdf_text_width(line, font_name, font_size)
            x_position = TEXT_BOX_HORIZONTAL_PADDING + _alignment_offset(
                alignment,
                inner_width,
                line_width,
            )
            self._pdf.drawString(x_position, y_position, line)
            if underline:
                self._draw_pdf_underline(
                    x=x_position,
                    y=y_position - 1,
                    width=line_width,
                )
            y_position -= line_height

    def _draw_pdf_underline(self, *, x: float, y: float, width: float) -> None:
        if hasattr(self._pdf, "line"):
            self._pdf.line(x, y, x + width, y)

    def draw_image(
        self,
        *,
        x: float,
        y: float,
        image_path: Path,
        display_width: float,
        display_height: float,
        keep_aspect_ratio: bool,
        rotation: float = 0,
    ) -> None:
        self._pdf.saveState()
        self._pdf.translate(x, self._top_to_bottom_y(y, display_height))
        self._pdf.rotate(rotation)
        self._pdf.drawImage(
            str(image_path),
            0,
            0,
            width=display_width,
            height=display_height,
            preserveAspectRatio=keep_aspect_ratio,
            mask="auto",
        )
        self._pdf.restoreState()

    def draw_rectangle(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float = 0,
    ) -> None:
        self._pdf.saveState()
        self._pdf.translate(x, self._top_to_bottom_y(y, height))
        self._pdf.rotate(rotation)
        self._pdf.rect(0, 0, width, height)
        self._pdf.restoreState()

    def _top_to_bottom_y(self, y: float, object_height: float) -> float:
        return self._page_height - y - object_height


class Renderer:
    """Render a label document to a drawing context."""

    def render(self, document: LabelDocument, context: RenderContext) -> None:
        """Render document objects in document order."""
        for label_object in document.objects:
            geometry = label_object.geometry
            if isinstance(label_object, TextObject):
                context.draw_text(
                    x=geometry.x,
                    y=geometry.y,
                    text=label_object.text,
                    font_family=label_object.font_family,
                    font_size=label_object.font_size,
                    bold=label_object.bold,
                    italic=label_object.italic,
                    underline=label_object.underline,
                    width=geometry.width,
                    height=geometry.height,
                    wrap=label_object.wrap,
                    alignment=label_object.alignment,
                    text_color=label_object.text_color,
                    rotation=geometry.rotation,
                )
            elif isinstance(label_object, ImageObject):
                context.draw_image(
                    x=geometry.x,
                    y=geometry.y,
                    image_path=label_object.image_path,
                    display_width=label_object.display_width,
                    display_height=label_object.display_height,
                    keep_aspect_ratio=label_object.keep_aspect_ratio,
                    rotation=geometry.rotation,
                )


def _pdf_font_name(font_family: str, bold: bool, italic: bool) -> str:
    if font_family.lower() not in {"arial", "helvetica"}:
        if font_family in pdfmetrics.getRegisteredFontNames():
            return font_family
        return _helvetica_font_name(bold=bold, italic=italic)
    return _helvetica_font_name(bold=bold, italic=italic)


def _helvetica_font_name(*, bold: bool, italic: bool) -> str:
    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def _qt_alignment_flag(alignment: str) -> Qt.AlignmentFlag:
    if alignment == "center":
        return Qt.AlignmentFlag.AlignHCenter
    if alignment == "right":
        return Qt.AlignmentFlag.AlignRight
    return Qt.AlignmentFlag.AlignLeft


def _alignment_offset(alignment: str, width: float, text_width: float) -> float:
    if alignment == "center":
        return max(0, (width - text_width) / 2)
    if alignment == "right":
        return max(0, width - text_width)
    return 0


def _wrap_pdf_text(
    *,
    text: str,
    font_name: str,
    font_size: float,
    width: float,
    wrap: bool = True,
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
            if _pdf_text_width(candidate, font_name, font_size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = _fit_pdf_word(word, font_name, font_size, width, lines)
        lines.append(current)
    return lines


def _fit_pdf_word(
    word: str,
    font_name: str,
    font_size: float,
    width: float,
    lines: list[str],
) -> str:
    current = ""
    for character in word:
        candidate = current + character
        if current and _pdf_text_width(candidate, font_name, font_size) > width:
            lines.append(current)
            current = character
        else:
            current = candidate
    return current


def _pdf_text_width(text: str, font_name: str, font_size: float) -> float:
    return pdfmetrics.stringWidth(text, font_name, font_size)
