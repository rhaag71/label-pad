"""Temporary plain-Qt font-size reference window for development."""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class FontSizeReference(QWidget):
    """Draw plain QPainter point-size samples without Label Pad rendering."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Qt Font Size Reference")
        self.resize(720, 420)

    def paintEvent(self, event) -> None:  # noqa: N802, ANN001
        super().paintEvent(event)

        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        left = 40.0
        top = 44.0
        dpi_x = float(painter.device().logicalDpiX())
        dpi_y = float(painter.device().logicalDpiY())

        painter.setPen(QPen(QColor("#666666"), 1))
        painter.drawText(
            QPointF(left, top - 14.0),
            f"1 inch reference: {dpi_x:.0f} x {dpi_y:.0f} logical pixels",
        )
        painter.drawRect(QRectF(left, top, dpi_x, dpi_y))

        y = top + dpi_y + 56.0
        for point_size in (10.0, 14.0, 18.0):
            font = QFont("Helvetica")
            font.setPointSizeF(point_size)
            metrics = QFontMetricsF(font)

            painter.setFont(font)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.drawText(
                QPointF(left, y),
                f"{point_size:g} pt Helvetica - The quick brown fox 0123456789",
            )

            painter.setPen(QPen(QColor("#cccccc"), 1))
            painter.drawLine(QPointF(left, y), QPointF(self.width() - left, y))
            y += metrics.lineSpacing() + 22.0

        painter.end()


def main() -> int:
    app = QApplication(sys.argv)
    window = FontSizeReference()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
