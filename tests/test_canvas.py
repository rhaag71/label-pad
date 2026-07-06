import os
from dataclasses import replace
from math import floor

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from label_pad.canvas import (
    EDITOR_STYLE,
    TEXT_BOX_HORIZONTAL_PADDING,
    TEXT_BOX_VERTICAL_PADDING,
    LabelCanvas,
    _InlineTextEditor,
    canvas_text_layout,
    editor_font_for_text_object,
    editor_font_for_text_object_at_scale,
    hit_test_text_object,
    hit_test_text_resize_handle,
    label_coordinates_from_widget,
    label_size_points,
    measured_text_box_size,
    natural_text_box_auto_width,
    natural_text_box_height,
    natural_text_box_minimum_width,
    preview_rect,
    preview_scale,
    text_object_bounds,
    text_object_hit_rect,
    text_object_resize_handle_rect,
    update_text_object,
)
from label_pad.model import LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile
from label_pad.text_fonts import qt_point_size_for_document_points

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapplication():
    return QApplication.instance() or QApplication([])


def replace_text_object(text_object: TextObject, text: str) -> TextObject:
    return replace(text_object, text=text)


def widget_point(
    *,
    profile: LabelProfile,
    width: int,
    height: int,
    x: float,
    y: float,
) -> tuple[float, float]:
    rect = preview_rect(width=width, height=height, profile=profile)
    scale = preview_scale(width=width, height=height, profile=profile)
    return (rect.x() + x * scale, rect.y() + y * scale)


def mouse_event_at(
    profile: LabelProfile,
    *,
    x: float,
    y: float,
    width: int = 248,
    height: int = 400,
) -> "FakeMouseEvent":
    widget_x, widget_y = widget_point(
        profile=profile,
        width=width,
        height=height,
        x=x,
        y=y,
    )
    return FakeMouseEvent(x=widget_x, y=widget_y)


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


def test_label_coordinates_from_widget_converts_inside_point_to_label_point() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )

    coordinates = label_coordinates_from_widget(
        widget_x=74,
        widget_y=180,
        width=248,
        height=400,
        profile=profile,
    )

    assert coordinates == pytest.approx((70.8661417, 42.5196850))


def test_label_coordinates_from_widget_returns_none_outside_label() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )

    coordinates = label_coordinates_from_widget(
        widget_x=23,
        widget_y=180,
        width=248,
        height=400,
        profile=profile,
    )

    assert coordinates is None


def test_preview_scale_changes_with_widget_size_without_changing_geometry() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30, width=40, height=20),
            text="Text",
        )
    )

    small_scale = preview_scale(width=248, height=400, profile=profile)
    large_scale = preview_scale(width=448, height=400, profile=profile)

    assert large_scale > small_scale
    assert text_object.geometry.x == 50
    assert text_object.geometry.y == 30
    assert text_object.geometry.width == 40
    assert text_object.geometry.height == 20


def test_text_object_bounds_use_object_geometry_box() -> None:
    text_object = TextObject(
        geometry=ObjectGeometry(x=10, y=30, width=80, height=24),
        text="Text",
        font_size=12,
    )

    left, top, width, height = text_object_bounds(text_object)

    assert left == 10
    assert top == 30
    assert width == 80
    assert height == 24


def test_text_object_bounds_are_reasonably_tight_to_visible_text() -> None:
    text_object = TextObject(
        geometry=ObjectGeometry(x=10, y=30),
        text="Text",
        font_size=14,
    )

    _, _, width, height = text_object_bounds(text_object)

    assert width < len(text_object.text) * text_object.font_size
    assert height > text_object.font_size


def test_text_object_bounds_come_from_shared_canvas_text_layout() -> None:
    text_object = TextObject(
        geometry=ObjectGeometry(x=10, y=30),
        text="Text",
        font_size=14,
    )
    layout_rect = canvas_text_layout(text_object).box_rect

    assert text_object_bounds(text_object) == (
        layout_rect.x(),
        layout_rect.y(),
        layout_rect.width(),
        layout_rect.height(),
    )


def test_canvas_text_layout_editor_rect_expands_right_from_text_anchor() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=profile,
    )
    scale = preview_scale(width=248, height=400, profile=profile)
    text_object = TextObject(
        geometry=ObjectGeometry(x=50, y=30),
        text="Text",
        font_size=12,
    )

    short_rect = canvas_text_layout(text_object).editor_rect(label_rect, scale)
    long_rect = canvas_text_layout(
        replace_text_object(text_object, "A much longer text value")
    ).editor_rect(label_rect, scale)

    assert long_rect.x() == short_rect.x()
    assert long_rect.width() > short_rect.width()


def test_canvas_text_layout_editor_rect_clamps_width_inside_label() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=profile,
    )
    scale = preview_scale(width=248, height=400, profile=profile)
    text_object = TextObject(
        geometry=ObjectGeometry(x=190, y=30),
        text="Text",
        font_size=12,
    )

    editor_rect = canvas_text_layout(
        replace_text_object(text_object, "A much longer text value")
    ).editor_rect(label_rect, scale)

    assert editor_rect.x() == floor(label_rect.x() + 190 * scale)
    assert editor_rect.x() + editor_rect.width() == label_rect.x() + label_rect.width()


def test_canvas_text_layout_editor_rect_keeps_left_edge_fixed_for_long_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=profile,
    )
    scale = preview_scale(width=248, height=400, profile=profile)
    text_object = TextObject(
        geometry=ObjectGeometry(x=50, y=30),
        text="Text",
        font_size=12,
    )

    editor_rect = canvas_text_layout(
        replace_text_object(text_object, "A" * 200)
    ).editor_rect(label_rect, scale)

    assert editor_rect.x() == floor(label_rect.x() + 50 * scale)
    assert editor_rect.x() + editor_rect.width() == label_rect.x() + label_rect.width()


def test_text_box_padding_is_balanced() -> None:
    assert TEXT_BOX_HORIZONTAL_PADDING == TEXT_BOX_VERTICAL_PADDING


def test_editor_font_matches_text_object_style() -> None:
    text_object = TextObject(
        text="Text",
        font_family="Courier New",
        font_size=18.5,
        bold=True,
        italic=True,
    )

    font = editor_font_for_text_object(text_object)

    assert font.family() == "Courier New"
    assert font.pointSizeF() == 18.5
    assert font.bold() is True
    assert font.italic() is True


def test_editor_font_helpers_do_not_recurse() -> None:
    text_object = TextObject(text="Text", font_size=14)

    unscaled_font = editor_font_for_text_object(text_object)
    scaled_font = editor_font_for_text_object_at_scale(text_object, scale=2)

    assert unscaled_font.pointSizeF() == 14
    assert scaled_font.pointSizeF() == qt_point_size_for_document_points(
        14,
        scale=2,
    )


def test_qt_point_size_for_document_points_stays_screen_sized() -> None:
    assert qt_point_size_for_document_points(14, scale=1) == 14
    assert qt_point_size_for_document_points(14, scale=2) == 14
    assert qt_point_size_for_document_points(14, scale=0.5) == 14


def test_editor_font_at_scale_preserves_text_object_style() -> None:
    text_object = TextObject(
        text="Text",
        font_family="Courier New",
        font_size=14,
        bold=False,
        italic=True,
        underline=True,
    )

    font = editor_font_for_text_object_at_scale(text_object, scale=3)

    assert font.family() == "Courier New"
    assert font.pointSizeF() == qt_point_size_for_document_points(14, scale=3)
    assert font.bold() is False
    assert font.italic() is True
    assert font.underline() is True


def test_editor_scaled_font_matches_counter_scaled_preview_render() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    text_object = TextObject(text="Text", font_size=14)
    scale = preview_scale(width=248, height=400, profile=profile)

    editor_font = editor_font_for_text_object_at_scale(text_object, scale=scale)

    assert text_object.font_size == 14
    assert editor_font.pointSizeF() == pytest.approx(
        qt_point_size_for_document_points(14, scale=scale)
    )


def test_editor_and_preview_effective_font_pixels_match() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    text_object = TextObject(text="Text", font_size=14)
    scale = preview_scale(width=248, height=400, profile=profile)
    renderer_font_size = 14 / scale
    editor_font = editor_font_for_text_object_at_scale(text_object, scale=scale)

    assert editor_font.pointSizeF() == pytest.approx(
        renderer_font_size * scale
    )


def test_hit_test_text_object_returns_topmost_matching_text() -> None:
    document = LabelDocument(profile_name="Wide")
    first = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="first", x=10, y=20, width=20, height=20),
            text="First",
            font_size=12,
        )
    )
    second = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="second", x=12, y=20, width=20, height=20),
            text="Second",
            font_size=12,
        )
    )

    assert hit_test_text_object(document, x=13, y=25) is second
    assert hit_test_text_object(document, x=7, y=25) is first
    assert hit_test_text_object(document, x=100, y=100) is None


def test_hit_test_uses_full_text_box_geometry() -> None:
    document = LabelDocument(profile_name="Wide")
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=20, width=80, height=24),
            text="Text",
            font_size=12,
        )
    )

    assert hit_test_text_object(document, x=85, y=40) is text_object


def test_hit_test_allows_small_slop_outside_visible_text_box() -> None:
    document = LabelDocument(profile_name="Wide")
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=20, width=80, height=24),
            text="Text",
            font_size=12,
        )
    )
    visible_rect = canvas_text_layout(text_object).box_rect
    hit_rect = text_object_hit_rect(text_object)

    assert visible_rect.contains(92, 42) is False
    assert hit_rect.contains(92, 42) is True
    assert hit_test_text_object(document, x=92, y=42) is text_object


def test_resize_handle_hit_test_requires_selected_text_box() -> None:
    document = LabelDocument(profile_name="Wide")
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=10,
                y=20,
                width=80,
                height=24,
                selected=True,
            ),
            text="Text",
        )
    )
    handle_rect = text_object_resize_handle_rect(text_object)

    assert (
        hit_test_text_resize_handle(
            document,
            x=handle_rect.center().x(),
            y=handle_rect.center().y(),
        )
        is text_object
    )

    unselected_document = LabelDocument(profile_name="Wide")
    unselected_document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=20, width=80, height=24),
            text="Text",
        )
    )

    assert (
        hit_test_text_resize_handle(
            unselected_document,
            x=handle_rect.center().x(),
            y=handle_rect.center().y(),
        )
        is None
    )


def test_update_text_object_replaces_text_content() -> None:
    document = LabelDocument(profile_name="Wide")
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=30, selected=True),
            text="Old",
        )
    )

    updated_object = update_text_object(document, "text", "New")

    assert updated_object is document.objects[0]
    assert updated_object is not text_object
    assert updated_object.text == "New"
    assert updated_object.geometry == text_object.geometry


def test_update_text_object_can_update_box_size() -> None:
    document = LabelDocument(profile_name="Wide")
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=30, width=20, height=10),
            text="Old",
        )
    )

    updated_object = update_text_object(
        document,
        "text",
        "New",
        width=50,
        height=18,
    )

    assert updated_object is not None
    assert updated_object.geometry.width == 50
    assert updated_object.geometry.height == 18


def test_single_click_empty_label_clears_selection_without_creating_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = FakeMouseEvent(x=200, y=200)

    LabelCanvas.mousePressEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.selected_objects() == []
    assert canvas.edit_started_with is None
    assert canvas.update_count == 1
    assert canvas.focused
    assert event.accepted
    assert not event.ignored


def test_single_click_existing_text_selects_without_creating_object() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=51, y=35)

    LabelCanvas.mousePressEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.selected_objects() == [
        document.find_by_id(text_object.geometry.id)
    ]
    assert document.objects[0].geometry.selected is True
    assert canvas.edit_started_with is None
    assert canvas.focused
    assert canvas.update_count == 1
    assert event.accepted


def test_single_click_existing_text_does_not_change_geometry() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=80,
                height=24,
            ),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=55, y=35)

    LabelCanvas.mousePressEvent(canvas, event)

    assert document.objects[0].geometry.x == 50
    assert document.objects[0].geometry.y == 30
    assert document.objects[0].geometry.width == 80
    assert document.objects[0].geometry.height == 24
    assert document.objects[0].geometry.selected is True


def test_drag_starts_when_pressing_existing_text_box() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30, width=40, height=20),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=51, y=35)

    LabelCanvas.mousePressEvent(canvas, event)

    assert canvas._drag_state is not None
    assert canvas._drag_state.object_id == text_object.geometry.id
    assert canvas._drag_state.start_pointer_x == pytest.approx(51)
    assert canvas._drag_state.start_pointer_y == pytest.approx(35)
    assert event.accepted


def test_drag_move_updates_selected_text_geometry_and_preserves_size() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, width=40, height=20),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=51, y=35))
    move_event = mouse_event_at(profile, x=71, y=55)
    LabelCanvas.mouseMoveEvent(canvas, move_event)

    moved_object = document.find_by_id("text")
    assert isinstance(moved_object, TextObject)
    assert moved_object.geometry.x == pytest.approx(70)
    assert moved_object.geometry.y == pytest.approx(50)
    assert moved_object.geometry.width == 40
    assert moved_object.geometry.height == 20
    assert moved_object.geometry.selected is True
    assert canvas.update_count == 2
    assert move_event.accepted


def test_drag_can_start_from_padded_area_inside_selected_box() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=90,
                height=28,
                selected=True,
            ),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=126, y=52))
    move_event = mouse_event_at(profile, x=136, y=62)
    LabelCanvas.mouseMoveEvent(canvas, move_event)

    moved_object = document.find_by_id("text")
    assert isinstance(moved_object, TextObject)
    assert moved_object.geometry.x == pytest.approx(60)
    assert moved_object.geometry.y == pytest.approx(40)
    assert moved_object.geometry.width == 90
    assert moved_object.geometry.height == 28
    assert move_event.accepted


def test_drag_release_finishes_drag_without_changing_geometry() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, width=40, height=20),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=51, y=35))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=71, y=55))
    release_event = mouse_event_at(profile, x=71, y=55)
    LabelCanvas.mouseReleaseEvent(canvas, release_event)

    moved_object = document.find_by_id("text")
    assert isinstance(moved_object, TextObject)
    assert moved_object.geometry.x == pytest.approx(70)
    assert moved_object.geometry.y == pytest.approx(50)
    assert canvas._drag_state is None
    assert release_event.accepted


def test_drag_move_clamps_text_box_inside_label_bounds() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=170, y=80, width=40, height=30),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=190, y=95))
    LabelCanvas.mouseMoveEvent(canvas, FakeMouseEvent(x=500, y=500))

    moved_object = document.find_by_id("text")
    assert isinstance(moved_object, TextObject)
    label_width, label_height = label_size_points(profile)
    assert moved_object.geometry.x == label_width - 40
    assert moved_object.geometry.y == label_height - 30
    assert moved_object.geometry.width == 40
    assert moved_object.geometry.height == 30


def test_resize_handle_drag_updates_size_without_moving_origin() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=40,
                height=20,
                selected=True,
            ),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=87, y=47))
    move_event = mouse_event_at(profile, x=107, y=62)
    LabelCanvas.mouseMoveEvent(canvas, move_event)

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert resized_object.geometry.x == 50
    assert resized_object.geometry.y == 30
    assert resized_object.geometry.width == pytest.approx(60)
    assert resized_object.geometry.height == pytest.approx(35)
    assert resized_object.geometry.selected is True
    assert resized_object.auto_size is False
    assert canvas._drag_state is None
    assert canvas._resize_state is not None
    assert move_event.accepted


def test_resize_handle_drag_enforces_minimum_size() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=40,
                height=20,
                selected=True,
            ),
            text="X",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=87, y=47))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=-5, y=-5))

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert resized_object.geometry.x == 50
    assert resized_object.geometry.y == 30
    assert resized_object.geometry.width == natural_text_box_minimum_width(
        resized_object
    )
    assert resized_object.geometry.height == natural_text_box_height(
        resized_object,
        resized_object.geometry.width,
    )


def test_resize_handle_drag_enforces_longest_word_minimum_width() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=120,
                height=24,
                selected=True,
            ),
            text="Short Supercalifragilistic",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=167, y=56))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=-5, y=-5))

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert resized_object.geometry.x == 50
    assert resized_object.geometry.width == min(
        label_size_points(profile)[0] - 50,
        natural_text_box_minimum_width(resized_object),
    )
    assert resized_object.geometry.height == min(
        70,
        natural_text_box_height(
            resized_object,
            resized_object.geometry.width,
        ),
    )


def test_resize_handle_clamps_long_word_minimum_to_remaining_label_width() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=170,
                y=30,
                width=30,
                height=24,
                selected=True,
            ),
            text="Supercalifragilistic",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=197, y=56))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=-5, y=-5))

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert natural_text_box_minimum_width(resized_object) > 30
    assert resized_object.geometry.x == 170
    label_width, _ = label_size_points(profile)
    assert resized_object.geometry.width == label_width - 170
    assert resized_object.geometry.x + resized_object.geometry.width == label_width


def test_resize_narrower_increases_live_minimum_height_for_wrapped_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=100,
                height=20,
                selected=True,
            ),
            text="Alpha Beta",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=147, y=52))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=87, y=-5))

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert resized_object.geometry.width == natural_text_box_minimum_width(
        resized_object
    )
    assert resized_object.geometry.height == natural_text_box_height(
        resized_object,
        resized_object.geometry.width,
    )


def test_resize_wider_can_reduce_live_minimum_height_for_wrapped_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=10,
                width=40,
                height=80,
                selected=True,
            ),
            text="Alpha Beta Gamma Delta",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=87, y=87))
    LabelCanvas.mouseMoveEvent(canvas, mouse_event_at(profile, x=147, y=2))

    resized_object = document.find_by_id("text")
    assert isinstance(resized_object, TextObject)
    assert resized_object.geometry.width == 100
    assert resized_object.geometry.height == natural_text_box_height(
        resized_object,
        100,
    )


def test_hover_over_selected_text_box_uses_move_cursor() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=90,
                height=28,
                selected=True,
            ),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=126, y=52)

    LabelCanvas.mouseMoveEvent(canvas, event)

    assert canvas.cursor_shape == Qt.CursorShape.OpenHandCursor
    assert event.ignored


def test_single_click_empty_label_commits_active_edit_and_creates_nothing() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Committed")
    canvas._editing_object_id = text_object.geometry.id
    event = FakeMouseEvent(x=200, y=200)

    LabelCanvas.mousePressEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.objects[0].text == "Committed"
    assert document.selected_objects() == []
    assert canvas._text_editor is None
    assert canvas.update_count == 2
    assert event.accepted


def test_double_click_existing_text_starts_editing_without_creating_object() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=51, y=35)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.objects[0].geometry.selected is True
    assert canvas.edit_started_with == text_object
    assert canvas.edit_started_created is False
    assert canvas.update_count == 1
    assert event.accepted
    assert not event.ignored


def test_double_click_selected_text_starts_editing() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=51, y=35)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.selected_objects() == [text_object]
    assert canvas.edit_started_with == text_object
    assert canvas.edit_started_created is False
    assert canvas.update_count == 1
    assert event.accepted
    assert not event.ignored


def test_double_click_empty_label_creates_text_and_starts_editing() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=50, y=30)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    assert len(document.objects) == 1
    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.text == "Text"
    assert text_object.geometry.x == pytest.approx(50)
    assert text_object.geometry.y == pytest.approx(30)
    assert (
        text_object.geometry.width,
        text_object.geometry.height,
    ) == measured_text_box_size(text_object)
    assert text_object.geometry.selected is True
    assert canvas.edit_started_with == text_object
    assert canvas.edit_started_created is True
    assert canvas.update_count == 1
    assert event.accepted
    assert not event.ignored


def test_double_click_empty_label_can_place_text_near_edge() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = mouse_event_at(profile, x=2, y=2)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.geometry.x == pytest.approx(2)
    assert text_object.geometry.y == pytest.approx(2)


def test_double_click_after_initial_empty_press_creates_one_text_object() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    LabelCanvas.mousePressEvent(canvas, mouse_event_at(profile, x=50, y=30))
    LabelCanvas.mouseDoubleClickEvent(canvas, mouse_event_at(profile, x=50, y=30))

    assert len(document.objects) == 1
    assert canvas.edit_started_with == document.objects[0]
    assert canvas.edit_started_created is True
    assert canvas.update_count == 2


def test_double_click_empty_label_while_editing_commits_without_creating_text() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Committed")
    canvas._editing_object_id = text_object.geometry.id
    event = FakeMouseEvent(x=200, y=200)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    assert len(document.objects) == 1
    assert document.objects[0].text == "Committed"
    assert canvas._text_editor is None
    assert canvas.update_count == 1
    assert event.accepted
    assert not event.ignored


def test_inline_editor_enter_inserts_newline_without_committing() -> None:
    committed = []
    editor = _InlineTextEditor(lambda: None, None)
    editor.set_commit_callback(lambda: committed.append(editor.text()))
    editor.setText("Line")
    editor.moveCursor(QTextCursor.MoveOperation.End)
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
        "\n",
    )

    editor.keyPressEvent(event)

    assert committed == []
    assert editor.text() == "Line\n"


def test_inline_editor_shift_enter_inserts_newline() -> None:
    committed = []
    editor = _InlineTextEditor(lambda: None, None)
    editor.set_commit_callback(lambda: committed.append(editor.text()))
    editor.setText("Line")
    editor.moveCursor(QTextCursor.MoveOperation.End)
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
        "\n",
    )

    editor.keyPressEvent(event)

    assert committed == []
    assert editor.text() == "Line\n"


def test_inline_editor_escape_cancels() -> None:
    cancelled = []
    editor = _InlineTextEditor(lambda: cancelled.append(True), None)
    editor.setText("Line")
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )

    editor.keyPressEvent(event)

    assert cancelled == [True]
    assert event.isAccepted()


def test_inline_editor_focus_out_commits_text() -> None:
    committed = []
    editor = _InlineTextEditor(lambda: None, None)
    editor.set_commit_callback(lambda: committed.append(editor.text()))
    editor.setText("Committed")
    event = QFocusEvent(QEvent.Type.FocusOut)

    editor.focusOutEvent(event)

    assert committed == ["Committed"]


def test_inline_editor_scrollbars_are_disabled() -> None:
    editor = _InlineTextEditor(lambda: None, None)

    assert (
        editor.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert editor.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_inline_editor_style_keeps_selection_outline_visible() -> None:
    assert "background: white" in EDITOR_STYLE
    assert "color: black" in EDITOR_STYLE
    assert "border: 1px solid #2f6fed" in EDITOR_STYLE


def test_resize_text_editor_auto_grows_new_text_box_width_while_typing() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.create_text(50, 30)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("A much longer single line value")
    canvas._editing_object_id = text_object.geometry.id

    LabelCanvas._resize_text_editor(canvas)

    assert canvas._text_editor.geometry is not None
    assert canvas._text_editor.geometry.width() > measured_text_box_size(
        text_object
    )[0]
    assert canvas._text_editor.geometry.right() <= 224


def test_resize_text_editor_does_not_recurse_while_typing() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.create_text(50, 30)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("")
    canvas._editing_object_id = text_object.geometry.id

    for text in ("A", "Ab", "Abc", "Abcd"):
        canvas._text_editor._text = text
        LabelCanvas._resize_text_editor(canvas)

    assert canvas._text_editor.geometry is not None


def test_resize_text_editor_ignores_reentrant_font_updates() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.create_text(50, 30)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)

    class ReentrantTextEditor(FakeTextEditor):
        def setFont(self, font) -> None:  # noqa: N802
            super().setFont(font)
            LabelCanvas._resize_text_editor(canvas)

    canvas._text_editor = ReentrantTextEditor("Typed")
    canvas._editing_object_id = text_object.geometry.id

    LabelCanvas._resize_text_editor(canvas)

    assert canvas._text_editor.geometry is not None
    assert canvas._resizing_text_editor is False


def test_paint_document_omits_active_editing_object_to_avoid_ghost_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    editing_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="editing", selected=True),
            text="Text",
        )
    )
    other_object = document.add_object(
        TextObject(geometry=ObjectGeometry(id="other"), text="Other")
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._editing_object_id = editing_object.geometry.id

    paint_document = LabelCanvas._paint_document(canvas)

    assert paint_document.objects == [other_object]
    assert document.objects == [editing_object, other_object]


def test_refresh_active_editor_applies_style_without_changing_geometry() -> None:
    profile = LabelProfile(
        name="Wide",
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
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=80,
                height=24,
                selected=True,
            ),
            text="Editing",
            font_family="Courier New",
            font_size=18,
            bold=True,
            italic=True,
            underline=True,
            alignment="right",
            auto_size=False,
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Editing")
    canvas._editing_object_id = text_object.geometry.id

    LabelCanvas.refresh_active_editor(canvas)

    scale = preview_scale(width=248, height=400, profile=profile)
    assert canvas._text_editor.font.family() == "Courier New"
    assert canvas._text_editor.font.pointSizeF() == pytest.approx(
        qt_point_size_for_document_points(18, scale=scale)
    )
    assert canvas._text_editor.font.bold() is True
    assert canvas._text_editor.font.italic() is True
    assert canvas._text_editor.font.underline() is True
    assert canvas._text_editor.alignment & Qt.AlignmentFlag.AlignRight
    assert document.objects[0].geometry.width == 80
    assert document.objects[0].geometry.height == 24


def test_finish_text_edit_commits_editor_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("New")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    assert document.objects[0].text == "New"
    assert document.objects[0].geometry.width == measured_text_box_size(
        document.objects[0]
    )[0]
    assert document.objects[0].geometry.height == natural_text_box_height(
        document.objects[0],
        document.objects[0].geometry.width,
    )
    assert canvas._text_editor is None
    assert canvas._editing_object_id is None
    assert canvas.update_count == 1


def test_finish_text_edit_preserves_text_style_fields() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
            font_family="Courier New",
            font_size=14,
            bold=False,
            italic=True,
            underline=True,
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("New")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.text == "New"
    assert text_object.font_family == "Courier New"
    assert text_object.font_size == 14
    assert text_object.bold is False
    assert text_object.italic is True
    assert text_object.underline is True


def test_finish_text_edit_preserves_explicit_newlines() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Line one\nLine two")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    assert document.objects[0].text == "Line one\nLine two"


def test_finish_text_edit_preserves_width_and_enforces_minimum_height() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=24,
                height=18,
                selected=True,
            ),
            text="Old",
            auto_size=False,
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("A much longer value")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    assert document.objects[0].geometry.width == 24
    assert document.objects[0].geometry.height == min(
        label_size_points(profile)[1] - 30,
        natural_text_box_height(
            document.objects[0],
            24,
        ),
    )


def test_finish_text_edit_auto_sized_text_grows_to_unwrapped_text_width() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("A much longer single line value")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    updated_object = document.objects[0]
    assert updated_object.geometry.width == natural_text_box_auto_width(
        updated_object,
        max_width=label_size_points(profile)[0] - 50,
    )
    assert updated_object.geometry.height == natural_text_box_height(
        updated_object,
        updated_object.geometry.width,
    )


def test_finish_text_edit_clamps_long_auto_sized_text_to_label_bounds() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=150, y=30, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("This is a very long line of label text")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    updated_object = document.objects[0]
    assert updated_object.geometry.x == 150
    assert updated_object.geometry.y == 30
    label_width, _ = label_size_points(profile)
    assert updated_object.geometry.width == label_width - 150
    assert updated_object.geometry.x + updated_object.geometry.width == label_width
    assert text_object_resize_handle_rect(updated_object).right() <= label_width


def test_finish_text_edit_keeps_resize_handle_inside_label_after_tall_wrap() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=150, y=85, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor(
        "This text wraps into more lines than the remaining label height can show"
    )
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    updated_object = document.objects[0]
    label_width, label_height = label_size_points(profile)
    assert text_object_resize_handle_rect(updated_object).right() <= label_width
    assert text_object_resize_handle_rect(updated_object).bottom() <= label_height


def test_resized_text_box_wraps_at_user_width_after_edit() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(
                id="text",
                x=50,
                y=30,
                width=50,
                height=18,
                selected=True,
            ),
            text="Old",
            auto_size=False,
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Alpha Beta Gamma")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    updated_object = document.objects[0]
    assert updated_object.geometry.width == 50
    assert updated_object.geometry.height == min(
        label_size_points(profile)[1] - 30,
        natural_text_box_height(
            updated_object,
            50,
        ),
    )


def test_hit_slop_does_not_inflate_object_geometry() -> None:
    document = LabelDocument(profile_name="Wide")
    text_object = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=10, y=20, width=80, height=24),
            text="Text",
        )
    )
    visible_bounds = text_object_bounds(text_object)
    hit_rect = text_object_hit_rect(text_object)

    assert hit_rect.width() > visible_bounds[2]
    assert hit_rect.height() > visible_bounds[3]
    assert text_object.geometry.width == 80
    assert text_object.geometry.height == 24


def test_finish_text_edit_preserves_shifted_number_symbols() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    special_text = "! @ # $ % ^ & * ( )"
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor(special_text)
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=True)

    assert document.objects[0].text == special_text


def test_finish_text_edit_cancel_preserves_old_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Old",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("New")
    canvas._editing_object_id = "text"

    LabelCanvas._finish_text_edit(canvas, commit=False)

    assert document.objects[0].text == "Old"
    assert canvas._text_editor is None
    assert canvas._editing_object_id is None
    assert canvas.update_count == 1


def test_finish_text_edit_cancel_removes_new_default_text() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.create_text(50, 30)
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("New")
    canvas._editing_object_id = text_object.geometry.id
    canvas._editing_created_object_id = text_object.geometry.id

    LabelCanvas._finish_text_edit(canvas, commit=False)

    assert document.objects == []
    assert canvas._text_editor is None
    assert canvas._editing_object_id is None
    assert canvas._editing_created_object_id is None
    assert canvas.update_count == 1


def test_single_click_outside_label_clears_selection() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="text", x=50, y=30, selected=True),
            text="Text",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = FakeMouseEvent(x=23, y=180)

    LabelCanvas.mousePressEvent(canvas, event)

    assert document.selected_objects() == []
    assert document.objects[0].geometry.selected is False
    assert canvas.update_count == 1
    assert event.accepted


def test_delete_removes_selected_text_objects_and_updates() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="selected", selected=True),
            text="Selected",
        )
    )
    unselected = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="unselected"),
            text="Unselected",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = FakeKeyEvent(Qt.Key.Key_Delete)

    LabelCanvas.keyPressEvent(canvas, event)

    assert document.objects == [unselected]
    assert canvas.update_count == 1
    assert event.accepted
    assert not event.ignored


def test_delete_without_selection_does_nothing() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    text_object = document.add_object(TextObject(text="Text"))
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    event = FakeKeyEvent(Qt.Key.Key_Delete)

    LabelCanvas.keyPressEvent(canvas, event)

    assert document.objects == [text_object]
    assert canvas.update_count == 0
    assert event.ignored
    assert not event.accepted


def test_delete_while_editing_does_not_remove_selected_object() -> None:
    profile = LabelProfile(
        name="Wide",
        page_width_mm=100,
        page_height_mm=50,
        label_width_mm=100,
        label_height_mm=50,
        columns=1,
        rows=1,
    )
    document = LabelDocument(profile_name=profile.name)
    selected = document.add_object(
        TextObject(
            geometry=ObjectGeometry(id="selected", selected=True),
            text="Selected",
        )
    )
    canvas = FakeCanvas(profile=profile, document=document, width=248, height=400)
    canvas._text_editor = FakeTextEditor("Editing")
    canvas._editing_object_id = selected.geometry.id
    event = FakeKeyEvent(Qt.Key.Key_Delete)

    LabelCanvas.keyPressEvent(canvas, event)

    assert document.objects == [selected]
    assert canvas.update_count == 0
    assert event.ignored
    assert not event.accepted


class FakeCanvas:
    def __init__(
        self,
        *,
        profile: LabelProfile,
        document: LabelDocument,
        width: int,
        height: int,
    ) -> None:
        self._profile = profile
        self._document = document
        self._width = width
        self._height = height
        self.update_count = 0
        self.focused = False
        self.edit_started_with = None
        self.edit_started_created = None
        self.selection_change_count = 0
        self.cursor_shape = None
        self._text_editor = None
        self._editing_object_id = None
        self._editing_created_object_id = None
        self._drag_state = None
        self._resize_state = None

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def update(self) -> None:
        self.update_count += 1

    def setFocus(self) -> None:  # noqa: N802
        self.focused = True

    def setCursor(self, cursor_shape) -> None:  # noqa: N802
        self.cursor_shape = cursor_shape

    def unsetCursor(self) -> None:  # noqa: N802
        self.cursor_shape = None

    def _finish_text_edit(self, *, commit) -> None:
        LabelCanvas._finish_text_edit(self, commit=commit)

    def _resize_text_editor(self) -> None:
        LabelCanvas._resize_text_editor(self)

    def _update_hover_cursor(self, event) -> None:
        LabelCanvas._update_hover_cursor(self, event)

    def _notify_selection_changed(self) -> None:
        self.selection_change_count += 1

    def _start_text_edit(self, text_object, *, created) -> None:
        self.edit_started_with = text_object
        self.edit_started_created = created


class FakeMouseEvent:
    def __init__(self, *, x: float, y: float) -> None:
        self._position = FakePosition(x=x, y=y)
        self.accepted = False
        self.ignored = False

    def position(self):
        return self._position

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


class FakeKeyEvent:
    def __init__(self, key) -> None:
        self._key = key
        self.accepted = False
        self.ignored = False

    def key(self):
        return self._key

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


class FakeTextEditor:
    def __init__(self, text: str) -> None:
        self._text = text
        self.deleted = False
        self.geometry = None
        self.alignment = None

    def text(self) -> str:
        return self._text

    def setGeometry(self, geometry) -> None:  # noqa: N802
        self.geometry = geometry

    def setFont(self, font) -> None:  # noqa: N802
        self.font = font

    def setAlignment(self, alignment) -> None:  # noqa: N802
        self.alignment = alignment

    def deleteLater(self) -> None:  # noqa: N802
        self.deleted = True


class FakePosition:
    def __init__(self, *, x: float, y: float) -> None:
        self._x = x
        self._y = y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y
