from pathlib import Path

from label_pad.model import ImageObject, LabelDocument, ObjectGeometry, TextObject
from label_pad.renderer import (
    TEXT_BOX_HORIZONTAL_PADDING,
    TEXT_BOX_VERTICAL_PADDING,
    PdfRenderContext,
    Renderer,
)


class RecordingRenderContext:
    def __init__(self) -> None:
        self.calls = []

    def draw_text(self, **kwargs) -> None:
        self.calls.append(("text", kwargs))

    def draw_image(self, **kwargs) -> None:
        self.calls.append(("image", kwargs))

    def draw_rectangle(self, **kwargs) -> None:
        self.calls.append(("rectangle", kwargs))


def test_renderer_draws_document_objects_in_order() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(x=1, y=2, width=80, height=24, rotation=15),
            text="Hello",
            font_family="Helvetica",
            font_size=18,
            bold=True,
            italic=False,
            underline=True,
            alignment="center",
        )
    )
    document.add_object(
        ImageObject(
            geometry=ObjectGeometry(x=3, y=4, rotation=30),
            image_path=Path("logo.png"),
            display_width=50,
            display_height=60,
            keep_aspect_ratio=True,
        )
    )
    context = RecordingRenderContext()

    Renderer().render(document, context)

    assert context.calls == [
        (
            "text",
            {
                "x": 1,
                "y": 2,
                "text": "Hello",
                "font_family": "Helvetica",
                "font_size": 18,
                "bold": True,
                "italic": False,
                "underline": True,
                "width": 80,
                "height": 24,
                "wrap": True,
                "alignment": "center",
                "text_color": "black",
                "rotation": 15,
            },
        ),
        (
            "image",
            {
                "x": 3,
                "y": 4,
                "image_path": Path("logo.png"),
                "display_width": 50,
                "display_height": 60,
                "keep_aspect_ratio": True,
                "rotation": 30,
            },
        ),
    ]


def test_renderer_ignores_empty_documents() -> None:
    context = RecordingRenderContext()

    Renderer().render(LabelDocument(profile_name="4 x 6 Shipping Label"), context)

    assert context.calls == []


class RecordingPdfCanvas:
    def __init__(self) -> None:
        self.calls = []

    def saveState(self) -> None:  # noqa: N802
        self.calls.append(("saveState",))

    def translate(self, x, y) -> None:
        self.calls.append(("translate", x, y))

    def rotate(self, rotation) -> None:
        self.calls.append(("rotate", rotation))

    def setFont(self, font_name, font_size) -> None:  # noqa: N802
        self.calls.append(("setFont", font_name, font_size))

    def setFillColorRGB(self, red, green, blue) -> None:  # noqa: N802
        self.calls.append(("setFillColorRGB", red, green, blue))

    def drawString(self, x, y, text) -> None:  # noqa: N802
        self.calls.append(("drawString", x, y, text))

    def line(self, x1, y1, x2, y2) -> None:
        self.calls.append(("line", x1, y1, x2, y2))

    def beginText(self, x, y) -> "RecordingPdfText":  # noqa: N802
        self.calls.append(("beginText", x, y))
        return RecordingPdfText(self.calls)

    def drawText(self, text_object) -> None:  # noqa: N802
        self.calls.append(("drawText", text_object.lines))

    def drawImage(self, *args, **kwargs) -> None:  # noqa: N802
        self.calls.append(("drawImage", args, kwargs))

    def rect(self, x, y, width, height) -> None:
        self.calls.append(("rect", x, y, width, height))

    def restoreState(self) -> None:  # noqa: N802
        self.calls.append(("restoreState",))


class RecordingPdfText:
    def __init__(self, calls) -> None:
        self.calls = calls
        self.lines = []

    def setFont(self, font_name, font_size) -> None:  # noqa: N802
        self.calls.append(("text.setFont", font_name, font_size))

    def setLeading(self, leading) -> None:  # noqa: N802
        self.calls.append(("text.setLeading", leading))

    def textLine(self, text) -> None:  # noqa: N802
        self.lines.append(text)


def test_pdf_render_context_converts_text_top_left_y_to_pdf_baseline() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known Good",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=False,
    )

    translated_call = (
        "translate",
        8 + TEXT_BOX_HORIZONTAL_PADDING,
        72 - 18 - TEXT_BOX_VERTICAL_PADDING - 12,
    )
    assert translated_call in pdf.calls
    assert 0 <= translated_call[2] <= 72
    assert ("setFillColorRGB", 0, 0, 0) in pdf.calls
    assert ("setFont", "Helvetica", 12) in pdf.calls
    assert ("drawString", 0, 0, "Known Good") in pdf.calls


def test_pdf_render_context_falls_back_for_unsupported_font_family() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known Good",
        font_family="Annapurna SIL",
        font_size=12,
        bold=True,
        italic=True,
        underline=False,
    )

    assert ("setFont", "Helvetica-BoldOblique", 12) in pdf.calls
    assert ("drawString", 0, 0, "Known Good") in pdf.calls


def test_pdf_render_context_wraps_text_inside_box() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known Good",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=False,
        width=52,
        height=40,
        wrap=True,
    )

    assert ("translate", 8, 54) in pdf.calls
    assert ("setFont", "Helvetica", 12) in pdf.calls
    assert ("drawString", TEXT_BOX_HORIZONTAL_PADDING, -13, "Known") in pdf.calls
    assert ("drawString", TEXT_BOX_HORIZONTAL_PADDING, -27.4, "Good") in pdf.calls


def test_pdf_render_context_renders_text_black() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known Good",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=False,
        width=80,
        height=24,
        wrap=True,
    )

    assert ("setFillColorRGB", 0, 0, 0) in pdf.calls


def test_pdf_render_context_underlines_text() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=True,
    )

    assert any(call[0] == "line" for call in pdf.calls)


def test_pdf_render_context_aligns_wrapped_text() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Known",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=False,
        width=100,
        height=30,
        wrap=True,
        alignment="center",
    )

    draw_calls = [call for call in pdf.calls if call[0] == "drawString"]
    assert draw_calls
    assert draw_calls[0][1] > TEXT_BOX_HORIZONTAL_PADDING


def test_pdf_render_context_preserves_explicit_newlines_when_wrapping() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_text(
        x=8,
        y=18,
        text="Alpha\nBeta Gamma",
        font_family="Arial",
        font_size=12,
        bold=False,
        italic=False,
        underline=False,
        width=100,
        height=40,
        wrap=True,
    )

    assert ("drawString", TEXT_BOX_HORIZONTAL_PADDING, -13, "Alpha") in pdf.calls
    assert ("drawString", TEXT_BOX_HORIZONTAL_PADDING, -27.4, "Beta Gamma") in pdf.calls


def test_pdf_render_context_converts_image_top_left_y_to_pdf_bottom_left() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)

    context.draw_image(
        x=8,
        y=18,
        image_path=Path("image.png"),
        display_width=20,
        display_height=10,
        keep_aspect_ratio=True,
    )

    assert ("translate", 8, 44) in pdf.calls


def test_renderer_dispatches_text_object_to_pdf_render_context() -> None:
    pdf = RecordingPdfCanvas()
    context = PdfRenderContext(pdf, page_height=72)
    document = LabelDocument(profile_name="Rollo 2 x 1")
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(x=8, y=18),
            text="Known Good",
        )
    )

    Renderer().render(document, context)

    assert (
        "translate",
        8 + TEXT_BOX_HORIZONTAL_PADDING,
        72 - 18 - TEXT_BOX_VERTICAL_PADDING - 14,
    ) in pdf.calls
    assert ("setFillColorRGB", 0, 0, 0) in pdf.calls
    assert ("drawString", 0, 0, "Known Good") in pdf.calls
