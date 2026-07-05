from label_pad.canvas import preview_rect
from label_pad.profiles import LabelProfile


def test_preview_rect_preserves_profile_aspect_ratio_when_width_limited() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )

    rect = preview_rect(width=248, height=400, profile=profile)

    assert rect.x() == 24
    assert rect.y() == 150
    assert rect.width() == 200
    assert rect.height() == 100


def test_preview_rect_preserves_profile_aspect_ratio_when_height_limited() -> None:
    profile = LabelProfile(
        name="Tall",
        page_width_mm=50,
        page_height_mm=100,
        label_width_mm=50,
        label_height_mm=100,
        columns=1,
        rows=1,
    )

    rect = preview_rect(width=400, height=248, profile=profile)

    assert rect.x() == 150
    assert rect.y() == 24
    assert rect.width() == 100
    assert rect.height() == 200
