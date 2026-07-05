"""Label canvas widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from label_pad.profiles import LabelProfile


class LabelCanvas(QWidget):
    """White preview surface with the active label's physical aspect ratio."""

    def __init__(self, profile: LabelProfile) -> None:
        super().__init__()
        self._profile = profile
        self.setMinimumSize(320, 220)

    def set_profile(self, profile: LabelProfile) -> None:
        self._profile = profile
        self.update()

    def clear(self) -> None:
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        margin = 24
        available_width = max(1, self.width() - margin * 2)
        available_height = max(1, self.height() - margin * 2)
        aspect = self._profile.label_width_mm / self._profile.label_height_mm

        canvas_width = available_width
        canvas_height = int(canvas_width / aspect)
        if canvas_height > available_height:
            canvas_height = available_height
            canvas_width = int(canvas_height * aspect)

        x = (self.width() - canvas_width) // 2
        y = (self.height() - canvas_height) // 2
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(x, y, canvas_width, canvas_height)
