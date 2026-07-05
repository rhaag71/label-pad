"""Main application window."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from label_pad.pdf_export import export_pdf
from label_pad.printing import print_pdf
from label_pad.profiles import LabelProfile, load_profiles


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


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Label Pad")

        self._profiles = load_profiles()
        self._profile_combo = QComboBox()
        for profile in self._profiles:
            self._profile_combo.addItem(profile.name, profile)

        self._printer_combo = QComboBox()
        self._load_printers()

        self._canvas = LabelCanvas(self.current_profile)
        self._clear_button = QPushButton("Clear")
        self._print_button = QPushButton("Print")

        self._profile_combo.currentIndexChanged.connect(self._profile_changed)
        self._clear_button.clicked.connect(self._canvas.clear)
        self._print_button.clicked.connect(self.print_label)

        print_action = QAction("Print", self)
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.triggered.connect(self.print_label)
        self.addAction(print_action)
        QShortcut(QKeySequence("Ctrl+P"), self, self.print_label)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Profile"))
        toolbar.addWidget(self._profile_combo, 1)
        toolbar.addWidget(QLabel("Printer"))
        toolbar.addWidget(self._printer_combo, 1)
        toolbar.addWidget(self._clear_button)
        toolbar.addWidget(self._print_button)

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self._canvas, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.resize(760, 520)

    @property
    def current_profile(self) -> LabelProfile:
        return self._profile_combo.currentData()

    def _load_printers(self) -> None:
        printers = QPrinterInfo.availablePrinters()
        for printer in printers:
            self._printer_combo.addItem(printer.printerName())
        if not printers:
            self._printer_combo.addItem("System default")

    def _profile_changed(self) -> None:
        self._canvas.set_profile(self.current_profile)

    def print_label(self) -> None:
        printer_name = self._printer_combo.currentText()
        if printer_name == "System default":
            printer_name = None

        output_path = Path(tempfile.gettempdir()) / "label-pad-output.pdf"
        export_pdf(output_path, self.current_profile)
        try:
            print_pdf(output_path, printer_name)
        except Exception as exc:  # pragma: no cover - GUI feedback path
            QMessageBox.warning(self, "Print failed", str(exc))
