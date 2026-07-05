from label_pad.main_window import (
    MainWindow,
    is_likely_thermal_printer,
    ordered_printer_names,
    seeded_document,
)
from label_pad.model import LabelDocument, TextObject
from label_pad.profiles import LabelProfile


def test_seeded_document_contains_known_good_text() -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )

    document = seeded_document(profile)

    assert document.profile_name == "Test"
    assert len(document.objects) == 1
    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.text == "Known Good"
    assert text_object.geometry.x == 8
    assert text_object.geometry.y == 18


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
