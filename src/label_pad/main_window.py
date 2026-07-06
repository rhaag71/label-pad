"""Main application window."""

from __future__ import annotations

import tempfile
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from label_pad.canvas import LabelCanvas
from label_pad.model import LabelDocument, TextObject
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


def _format_button(text: str) -> QToolButton:
    button = QToolButton()
    button.setText(text)
    button.setCheckable(True)
    button.setMinimumSize(44, 32)
    return button


def _is_practical_label_font(family: str) -> bool:
    normalized = family.casefold()
    excluded = (
        "symbol",
        "emoji",
        "ding",
        "wing",
        "webdings",
        "math",
        "music",
        "noto color",
        "cjk",
        "arabic",
        "hebrew",
        "thai",
        "devanagari",
        "bengali",
        "tibetan",
        "khmer",
        "lao",
        "myanmar",
        "ethiopic",
    )
    return not any(keyword in normalized for keyword in excluded)


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
        self._syncing_format_toolbar = False

        self._printer_combo = QComboBox()
        self._load_printers()

        self._canvas = LabelCanvas(
            self.current_profile,
            self._document,
            selection_changed_callback=self._sync_format_toolbar,
        )
        self._clear_button = QPushButton("Clear")
        self._print_button = QPushButton("Print")
        self._font_family_combo = QComboBox()
        self._load_font_families()
        self._font_family_combo.setMinimumHeight(32)
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 96)
        self._font_size_spin.setMinimumSize(64, 32)
        self._bold_button = _format_button("B")
        self._italic_button = _format_button("I")
        self._underline_button = _format_button("U")
        self._wrap_button = _format_button("Wrap")
        self._alignment_combo = QComboBox()
        self._alignment_combo.addItem("Left", "left")
        self._alignment_combo.addItem("Center", "center")
        self._alignment_combo.addItem("Right", "right")
        self._alignment_combo.setMinimumHeight(32)

        self._profile_combo.currentIndexChanged.connect(self._profile_changed)
        self._clear_button.clicked.connect(self._canvas.clear)
        self._print_button.clicked.connect(self.print_label)
        self._font_family_combo.currentTextChanged.connect(self._format_changed)
        self._font_size_spin.valueChanged.connect(self._format_changed)
        self._bold_button.toggled.connect(self._format_changed)
        self._italic_button.toggled.connect(self._format_changed)
        self._underline_button.toggled.connect(self._format_changed)
        self._wrap_button.toggled.connect(self._format_changed)
        self._alignment_combo.currentIndexChanged.connect(self._format_changed)

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

        format_toolbar = QHBoxLayout()
        format_toolbar.addWidget(QLabel("Font"))
        format_toolbar.addWidget(self._font_family_combo, 1)
        format_toolbar.addWidget(QLabel("Size"))
        format_toolbar.addWidget(self._font_size_spin)
        format_toolbar.addWidget(self._bold_button)
        format_toolbar.addWidget(self._italic_button)
        format_toolbar.addWidget(self._underline_button)
        format_toolbar.addWidget(self._wrap_button)
        format_toolbar.addWidget(QLabel("Align"))
        format_toolbar.addWidget(self._alignment_combo)

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addLayout(format_toolbar)
        layout.addWidget(self._canvas, 1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.resize(760, 520)
        self._sync_format_toolbar()

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

    def _load_font_families(self) -> None:
        font_database = QFontDatabase()
        families = set(
            font_database.families(QFontDatabase.WritingSystem.Latin)
        )
        preferred = [
            "Helvetica",
            "Arial",
            "Liberation Sans",
            "DejaVu Sans",
            "DejaVu Serif",
            "Liberation Serif",
            "Liberation Mono",
            "DejaVu Sans Mono",
            "Courier New",
            "Monospace",
        ]
        practical_fonts = [
            family
            for family in sorted(families)
            if _is_practical_label_font(family)
        ]
        for family in preferred + practical_fonts:
            if self._font_family_combo.findText(family) == -1:
                self._add_font_family(family)

    def _add_font_family(self, family: str) -> None:
        self._font_family_combo.addItem(family)
        index = self._font_family_combo.findText(family)
        self._font_family_combo.setItemData(
            index,
            QFont(family),
            Qt.ItemDataRole.FontRole,
        )

    def _profile_changed(self) -> None:
        self._document = LabelDocument(profile_name=self.current_profile.name)
        self._canvas.set_profile(self.current_profile, self._document)
        self._sync_format_toolbar()

    def _selected_text_object(self) -> TextObject | None:
        selected_objects = self._document.selected_objects()
        if len(selected_objects) != 1:
            return None
        selected_object = selected_objects[0]
        if isinstance(selected_object, TextObject):
            return selected_object
        return None

    def _format_source(self):
        return self._selected_text_object() or self._document.defaults

    def _sync_format_toolbar(self) -> None:
        if not hasattr(self, "_font_family_combo"):
            return
        source = self._format_source()
        self._syncing_format_toolbar = True
        try:
            if self._font_family_combo.findText(source.font_family) == -1:
                self._add_font_family(source.font_family)
            self._font_family_combo.setCurrentText(source.font_family)
            self._font_size_spin.setValue(round(source.font_size))
            self._bold_button.setChecked(source.bold)
            self._italic_button.setChecked(source.italic)
            self._underline_button.setChecked(source.underline)
            self._wrap_button.setChecked(source.wrap)
            self._wrap_button.setText("Wrap" if source.wrap else "No Wrap")
            alignment_index = self._alignment_combo.findData(source.alignment)
            self._alignment_combo.setCurrentIndex(max(0, alignment_index))
        finally:
            self._syncing_format_toolbar = False

    def _format_changed(self, *args) -> None:
        if self._syncing_format_toolbar:
            return
        updates = {
            "font_family": self._font_family_combo.currentText(),
            "font_size": float(self._font_size_spin.value()),
            "bold": self._bold_button.isChecked(),
            "italic": self._italic_button.isChecked(),
            "underline": self._underline_button.isChecked(),
            "wrap": self._wrap_button.isChecked(),
            "alignment": self._alignment_combo.currentData(),
        }
        selected_object = self._selected_text_object()
        if selected_object is None:
            self._document.defaults = replace(self._document.defaults, **updates)
        else:
            self._replace_text_object(selected_object.geometry.id, **updates)
        self._wrap_button.setText("Wrap" if updates["wrap"] else "No Wrap")
        if hasattr(self._canvas, "refresh_active_editor"):
            self._canvas.refresh_active_editor()
        self._canvas.update()

    def _replace_text_object(self, object_id: str, **updates) -> None:
        for index, label_object in enumerate(self._document.objects):
            if label_object.geometry.id != object_id:
                continue
            if isinstance(label_object, TextObject):
                self._document.objects[index] = replace(label_object, **updates)
            return

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
