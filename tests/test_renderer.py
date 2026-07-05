from pathlib import Path

from label_pad.model import ImageObject, LabelDocument, ObjectGeometry, TextObject
from label_pad.renderer import Renderer


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
