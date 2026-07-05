from pathlib import Path

from label_pad.model import ImageObject, LabelDocument, ObjectGeometry, TextObject
from label_pad.renderer import PdfRenderContext, Renderer


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
            geometry=ObjectGeometry(x=1, y=2, rotation=15),
            text="Hello",
            font_family="Helvetica",
            font_size=18,
            bold=True,
            italic=False,
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

    def drawImage(self, *args, **kwargs) -> None:  # noqa: N802
        self.calls.append(("drawImage", args, kwargs))

    def rect(self, x, y, width, height) -> None:
        self.calls.append(("rect", x, y, width, height))

    def restoreState(self) -> None:  # noqa: N802
        self.calls.append(("restoreState",))


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
    )

    translated_call = ("translate", 8, 42)
    assert translated_call in pdf.calls
    assert 0 <= translated_call[2] <= 72
    assert ("setFillColorRGB", 0, 0, 0) in pdf.calls
    assert ("drawString", 0, 0, "Known Good") in pdf.calls


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

    assert ("translate", 8, 42) in pdf.calls
    assert ("setFillColorRGB", 0, 0, 0) in pdf.calls
    assert ("drawString", 0, 0, "Known Good") in pdf.calls
