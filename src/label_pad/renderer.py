"""Document rendering contexts and renderer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPixmap
from reportlab.pdfgen.canvas import Canvas

from label_pad.model import ImageObject, LabelDocument, TextObject


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
        rotation: float = 0,
    ) -> None:
        self._painter.save()
        self._painter.translate(x, y)
        self._painter.rotate(rotation)
        font = QFont(font_family, int(font_size))
        font.setBold(bold)
        font.setItalic(italic)
        self._painter.setFont(font)
        self._painter.drawText(0, 0, text)
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
        rotation: float = 0,
    ) -> None:
        self._pdf.saveState()
        self._pdf.translate(x, self._top_to_bottom_y(y, font_size))
        self._pdf.rotate(rotation)
        self._pdf.setFillColorRGB(0, 0, 0)
        self._pdf.setFont(_pdf_font_name(font_family, bold, italic), font_size)
        self._pdf.drawString(0, 0, text)
        self._pdf.restoreState()

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
        return font_family
    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"
