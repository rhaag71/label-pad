from label_pad.main_window import (
    MainWindow,
    _is_practical_label_font,
    is_likely_thermal_printer,
    ordered_printer_names,
)
from label_pad.model import LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile


def test_likely_thermal_printer_matching_is_case_insensitive() -> None:
    assert is_likely_thermal_printer("Rollo Printer")
    assert is_likely_thermal_printer("ZEBRA-LP2844")
    assert is_likely_thermal_printer("Brother QL-800")
    assert is_likely_thermal_printer("Brother TD-4550DNWB")
    assert is_likely_thermal_printer("Brother PT-P900")
    assert not is_likely_thermal_printer("Office LaserJet")
    assert not is_likely_thermal_printer("Brother Laser")


def test_ordered_printer_names_places_likely_thermal_printers_first() -> None:
    printer_names = [
        "Office LaserJet",
        "Rollo Printer",
        "Kitchen Inkjet",
        "Zebra Label",
        "Brother Laser",
        "Brother QL-800",
    ]

    assert ordered_printer_names(printer_names) == [
        "Rollo Printer",
        "Zebra Label",
        "Brother QL-800",
        "Office LaserJet",
        "Kitchen Inkjet",
        "Brother Laser",
    ]


def test_rollo_is_ordered_before_non_thermal_printers() -> None:
    assert ordered_printer_names(["Office LaserJet", "Rollo X1038"]) == [
        "Rollo X1038",
        "Office LaserJet",
    ]


def test_profile_change_replaces_preview_with_empty_document() -> None:
    profile = LabelProfile(
        name="Rollo 2 x 1",
        page_width_mm=50.8,
        page_height_mm=25.4,
        label_width_mm=50.8,
        label_height_mm=25.4,
        columns=1,
        rows=1,
    )
    old_document = LabelDocument(profile_name="Old")
    old_document.add_object(TextObject(text="Existing"))
    profile_changes = []

    class FakeProfileCombo:
        def currentData(self):
            return profile

    class FakeCanvas:
        def set_profile(self, changed_profile, changed_document) -> None:
            profile_changes.append((changed_profile, changed_document))

    window = MainWindow.__new__(MainWindow)
    window._profile_combo = FakeProfileCombo()
    window._canvas = FakeCanvas()
    window._document = old_document

    MainWindow._profile_changed(window)

    assert window._document.profile_name == profile.name
    assert window._document.objects == []
    assert profile_changes == [(profile, window._document)]


def test_print_label_exports_the_active_preview_document(tmp_path, monkeypatch) -> None:
    profile = LabelProfile(
        name="Rollo 2 x 1",
        page_width_mm=50.8,
        page_height_mm=25.4,
        label_width_mm=50.8,
        label_height_mm=25.4,
        columns=1,
        rows=1,
        cups_page_size="2x1",
    )
    document = LabelDocument(profile_name=profile.name)
    exported = []
    printed = []

    class FakeProfileCombo:
        def currentData(self):
            return profile

    class FakePrinterCombo:
        def currentText(self):
            return "Rollo_X1038"

    class FakeTemporaryFile:
        name = str(tmp_path / "label.pdf")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

    def fake_export_pdf(path, exported_profile, exported_document) -> None:
        exported.append((path, exported_profile, exported_document))

    def fake_print_pdf(path, printer_name, page_size=None) -> None:
        printed.append((path, printer_name, page_size))

    monkeypatch.setattr(
        "label_pad.main_window.tempfile.NamedTemporaryFile",
        lambda **kwargs: FakeTemporaryFile(),
    )
    monkeypatch.setattr("label_pad.main_window.export_pdf", fake_export_pdf)
    monkeypatch.setattr("label_pad.main_window.print_pdf", fake_print_pdf)

    window = MainWindow.__new__(MainWindow)
    window._profile_combo = FakeProfileCombo()
    window._printer_combo = FakePrinterCombo()
    window._document = document

    MainWindow.print_label(window)

    assert exported == [(str(tmp_path / "label.pdf"), profile, document)]
    assert printed == [(str(tmp_path / "label.pdf"), "Rollo_X1038", "2x1")]


def test_format_toolbar_updates_selected_text_object() -> None:
    document = LabelDocument(profile_name="Test")
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                width=80,
                height=24,
                selected=True,
            )
        )
    )
    canvas = FakeCanvas()
    window = _format_window(document=document, canvas=canvas)
    window._font_family_combo.current_family = "Courier New"
    window._font_size_spin.current_value = 18
    window._bold_button.checked = True
    window._italic_button.checked = True
    window._underline_button.checked = True
    window._wrap_button.checked = False
    window._alignment_combo.current_data = "center"

    MainWindow._format_changed(window)

    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.font_family == "Courier New"
    assert text_object.font_size == 18
    assert text_object.bold is True
    assert text_object.italic is True
    assert text_object.underline is True
    assert text_object.wrap is False
    assert text_object.alignment == "center"
    assert text_object.geometry.width == 80
    assert text_object.geometry.height == 24
    assert canvas.refresh_count == 1
    assert canvas.update_count == 1


def test_format_toolbar_updates_document_defaults_without_selection() -> None:
    document = LabelDocument(profile_name="Test")
    canvas = FakeCanvas()
    window = _format_window(document=document, canvas=canvas)
    window._font_family_combo.current_family = "Arial"
    window._font_size_spin.current_value = 16
    window._bold_button.checked = True
    window._italic_button.checked = False
    window._underline_button.checked = True
    window._wrap_button.checked = True
    window._alignment_combo.current_data = "right"

    MainWindow._format_changed(window)
    text_object = document.create_text(10, 20)

    assert document.defaults.font_family == "Arial"
    assert document.defaults.font_size == 16
    assert document.defaults.bold is True
    assert document.defaults.underline is True
    assert document.defaults.alignment == "right"
    assert text_object.font_family == "Arial"
    assert text_object.font_size == 16
    assert text_object.bold is True
    assert text_object.underline is True
    assert text_object.alignment == "right"
    assert canvas.update_count == 1


def test_format_toolbar_reflects_selected_text_object() -> None:
    document = LabelDocument(profile_name="Test")
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", selected=True),
            font_family="Courier New",
            font_size=20,
            bold=True,
            italic=True,
            underline=True,
            wrap=False,
            alignment="right",
        )
    )
    window = _format_window(document=document, canvas=FakeCanvas())

    MainWindow._sync_format_toolbar(window)

    assert window._font_family_combo.current_family == "Courier New"
    assert window._font_size_spin.current_value == 20
    assert window._bold_button.checked is True
    assert window._italic_button.checked is True
    assert window._underline_button.checked is True
    assert window._wrap_button.checked is False
    assert window._alignment_combo.current_data == "right"


def test_format_toolbar_reflects_document_defaults_without_selection() -> None:
    document = LabelDocument(profile_name="Test")
    document.defaults = document.defaults.__class__(
        font_family="Arial",
        font_size=16,
        bold=True,
        italic=False,
        underline=True,
        wrap=False,
        alignment="center",
    )
    window = _format_window(document=document, canvas=FakeCanvas())

    MainWindow._sync_format_toolbar(window)

    assert window._font_family_combo.current_family == "Arial"
    assert window._font_size_spin.current_value == 16
    assert window._bold_button.checked is True
    assert window._underline_button.checked is True
    assert window._wrap_button.checked is False
    assert window._wrap_button.text == "No Wrap"
    assert window._alignment_combo.current_data == "center"


def test_practical_font_filter_removes_symbol_fonts() -> None:
    assert _is_practical_label_font("Helvetica") is True
    assert _is_practical_label_font("DejaVu Sans Mono") is True
    assert _is_practical_label_font("Noto Color Emoji") is False
    assert _is_practical_label_font("Symbol") is False


class FakeCanvas:
    def __init__(self) -> None:
        self.update_count = 0
        self.refresh_count = 0

    def refresh_active_editor(self) -> None:
        self.refresh_count += 1

    def update(self) -> None:
        self.update_count += 1


class FakeFont:
    def __init__(self, family: str) -> None:
        self._family = family

    def family(self) -> str:
        return self._family


class FakeFontCombo:
    def __init__(self) -> None:
        self.current_family = "Helvetica"
        self.items = ["Helvetica"]

    def currentText(self) -> str:  # noqa: N802
        return self.current_family

    def findText(self, text: str) -> int:  # noqa: N802
        try:
            return self.items.index(text)
        except ValueError:
            return -1

    def addItem(self, text: str) -> None:  # noqa: N802
        self.items.append(text)

    def setCurrentText(self, text: str) -> None:  # noqa: N802
        self.current_family = text

    def setItemData(self, index: int, value, role) -> None:  # noqa: N802, ARG002
        return


class FakeSpin:
    def __init__(self) -> None:
        self.current_value = 14

    def setValue(self, value: int) -> None:  # noqa: N802
        self.current_value = value

    def value(self) -> int:
        return self.current_value


class FakeButton:
    def __init__(self) -> None:
        self.checked = False
        self.text = ""

    def isChecked(self) -> bool:  # noqa: N802
        return self.checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        self.checked = checked

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text


class FakeAlignmentCombo:
    def __init__(self) -> None:
        self.current_data = "left"

    def currentData(self):
        return self.current_data

    def findData(self, value) -> int:  # noqa: N802
        return {"left": 0, "center": 1, "right": 2}.get(value, -1)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self.current_data = ["left", "center", "right"][index]


def _format_window(*, document: LabelDocument, canvas: FakeCanvas):
    window = MainWindow.__new__(MainWindow)
    window._document = document
    window._canvas = canvas
    window._syncing_format_toolbar = False
    window._font_family_combo = FakeFontCombo()
    window._font_size_spin = FakeSpin()
    window._bold_button = FakeButton()
    window._italic_button = FakeButton()
    window._underline_button = FakeButton()
    window._wrap_button = FakeButton()
    window._alignment_combo = FakeAlignmentCombo()
    return window
