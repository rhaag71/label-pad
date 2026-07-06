import base64
import re
import zlib

from label_pad.model import LabelDocument, ObjectGeometry, TextObject
from label_pad.pdf_export import export_pdf, page_size_points
from label_pad.profiles import LabelProfile


def test_export_pdf_writes_valid_pdf_for_empty_document(tmp_path) -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)

    output_path = export_pdf(tmp_path / "labels.pdf", profile, document)

    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF-")
    assert _media_box(output_path.read_bytes()) == (
        0.0,
        0.0,
        283.4646,
        141.7323,
    )


def test_page_size_points_uses_profile_physical_size() -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=101.6,
        page_height_mm=152.4,
        label_width_mm=101.6,
        label_height_mm=152.4,
        columns=1,
        rows=1,
    )

    width, height = page_size_points(profile)

    assert round(width, 4) == 288
    assert round(height, 4) == 432


def test_export_pdf_routes_document_through_renderer_and_pdf_context(
    tmp_path,
    monkeypatch,
) -> None:
    profile = LabelProfile(
        name="Test",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(x=12, y=18),
            text="Hello",
        )
    )
    calls = []
    context_calls = []

    class RecordingPdfRenderContext:
        def __init__(self, pdf, page_height) -> None:
            self.pdf = pdf
            self.page_height = page_height
            context_calls.append((pdf, page_height))

    class RecordingRenderer:
        def render(self, rendered_document, context) -> None:
            calls.append((rendered_document, context))

    monkeypatch.setattr(
        "label_pad.pdf_export.PdfRenderContext",
        RecordingPdfRenderContext,
    )
    monkeypatch.setattr("label_pad.pdf_export.Renderer", RecordingRenderer)

    output_path = export_pdf(tmp_path / "labels.pdf", profile, document)

    assert output_path.exists()
    assert calls
    rendered_document, context = calls[0]
    assert rendered_document is document
    assert rendered_document.objects == [text_object]
    assert isinstance(context, RecordingPdfRenderContext)
    assert context_calls
    assert round(context.page_height, 4) == 141.7323


def test_export_pdf_with_text_document_contains_visible_text_content(tmp_path) -> None:
    profile = LabelProfile(
        name="Rollo 2 x 1",
        page_width_mm=50.8,
        page_height_mm=25.4,
        label_width_mm=50.8,
        label_height_mm=25.4,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(x=8, y=18),
            text="Known Good",
        )
    )

    output_path = export_pdf(tmp_path / "labels.pdf", profile, document)
    content = b"\n".join(_decoded_streams(output_path.read_bytes()))

    assert b"0 0 0 rg" in content
    assert b"1 0 0 1 10 38 cm" in content
    assert b"/F1 14 Tf" in content
    assert b"(Known Good) Tj" in content


def _media_box(pdf_data: bytes) -> tuple[float, float, float, float]:
    match = re.search(
        rb"/MediaBox\s*\[\s*"
        rb"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)"
        rb"\s*\]",
        pdf_data,
    )
    assert match is not None
    return tuple(round(float(value), 4) for value in match.groups())


def _decoded_streams(pdf_data: bytes) -> list[bytes]:
    streams = re.findall(rb"stream\r?\n(.*?)endstream", pdf_data, re.DOTALL)
    decoded_streams = []
    for stream in streams:
        encoded = stream.strip()
        try:
            decoded_streams.append(
                zlib.decompress(base64.a85decode(encoded, adobe=True))
            )
        except (ValueError, zlib.error):
            continue
    return decoded_streams
