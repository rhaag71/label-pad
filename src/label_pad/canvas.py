"""Label canvas widget."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from label_pad.model import LabelDocument
from label_pad.profiles import LabelProfile
from label_pad.renderer import QtRenderContext, Renderer


def preview_rect(
    *,
    width: int,
    height: int,
    profile: LabelProfile,
    margin: int = 24,
) -> QRect:
    """Return the centered label preview rectangle for the widget size."""
    available_width = max(1, width - margin * 2)
    available_height = max(1, height - margin * 2)
    aspect = profile.label_width_mm / profile.label_height_mm

    canvas_width = available_width
    canvas_height = int(canvas_width / aspect)
    if canvas_height > available_height:
        canvas_height = available_height
        canvas_width = int(canvas_height * aspect)

    x = (width - canvas_width) // 2
    y = (height - canvas_height) // 2
    return QRect(x, y, canvas_width, canvas_height)


class LabelCanvas(QWidget):
    """White preview surface with the active label's physical aspect ratio."""

    def __init__(
        self,
        profile: LabelProfile,
        document: LabelDocument,
        renderer: Renderer | None = None,
    ) -> None:
        super().__init__()
        self._profile = profile
        self._document = document
        self._renderer = renderer or Renderer()
        self.setMinimumSize(320, 220)

    def set_profile(self, profile: LabelProfile, document: LabelDocument) -> None:
        self._profile = profile
        self._document = document
        self.update()

    def clear(self) -> None:
        self._document.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(label_rect)

        painter.save()
        painter.setClipRect(label_rect)
        painter.translate(label_rect.topLeft())
        self._renderer.render(self._document, QtRenderContext(painter))
        painter.restore()
