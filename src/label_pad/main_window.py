"""Main application window."""

from __future__ import annotations

import tempfile

from PySide6.QtGui import QAction, QKeySequence, QShortcut
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

from label_pad.canvas import LabelCanvas
from label_pad.model import LabelDocument
from label_pad.pdf_export import export_pdf
from label_pad.printing import print_pdf
from label_pad.profiles import LabelProfile, default_profile_index, load_profiles

THERMAL_PRINTER_KEYWORDS = (
    "rollo",
    "thermal",
    "label",
    "citizen",
    "zebra",
    "dymo",
)

BROTHER_THERMAL_KEYWORDS = ("ql", "td", "pt", "label", "thermal")


def is_likely_thermal_printer(printer_name: str) -> bool:
    """Return whether a printer name looks like a thermal label printer."""
    normalized_name = printer_name.casefold()
    if any(keyword in normalized_name for keyword in THERMAL_PRINTER_KEYWORDS):
        return True
    return "brother" in normalized_name and any(
        keyword in normalized_name for keyword in BROTHER_THERMAL_KEYWORDS
    )


def ordered_printer_names(printer_names: list[str]) -> list[str]:
    """Return printers with likely thermal label printers first."""
    return sorted(
        printer_names,
        key=lambda printer_name: (
            not is_likely_thermal_printer(printer_name),
            printer_names.index(printer_name),
        ),
    )


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Label Pad")

        self._profiles = load_profiles()
        self._profile_combo = QComboBox()
        for profile in self._profiles:
            self._profile_combo.addItem(profile.name, profile)
        self._profile_combo.setCurrentIndex(default_profile_index(self._profiles))
        self._document = LabelDocument(profile_name=self.current_profile.name)

        self._printer_combo = QComboBox()
        self._load_printers()

        self._canvas = LabelCanvas(self.current_profile, self._document)
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
        printer_names = [printer.printerName() for printer in printers]
        for printer_name in ordered_printer_names(printer_names):
            self._printer_combo.addItem(printer_name)
        if not printers:
            self._printer_combo.addItem("System default")

    def _profile_changed(self) -> None:
        self._document = LabelDocument(profile_name=self.current_profile.name)
        self._canvas.set_profile(self.current_profile, self._document)

    def print_label(self) -> None:
        printer_name = self._printer_combo.currentText()
        if printer_name == "System default":
            printer_name = None

        with tempfile.NamedTemporaryFile(
            prefix="label-pad-",
            suffix=".pdf",
            delete=False,
        ) as output_file:
            output_path = output_file.name
        export_pdf(output_path, self.current_profile, self._document)
        try:
            print_pdf(
                output_path,
                printer_name,
                page_size=self.current_profile.cups_page_size,
            )
        except Exception as exc:  # pragma: no cover - GUI feedback path
            QMessageBox.warning(self, "Print failed", str(exc))
