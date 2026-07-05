import os
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from label_pad.canvas import (
    LabelCanvas,
    canvas_text_layout,
    editor_font_for_text_object,
    hit_test_text_object,
    label_coordinates_from_widget,
    measured_text_box_size,
    preview_rect,
    text_object_bounds,
    update_text_object,
)
from label_pad.model import LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapplication():
    return QApplication.instance() or QApplication([])


def replace_text_object(text_object: TextObject, text: str) -> TextObject:
    return replace(text_object, text=text)


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

    assert coordinates == (50, 30)


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
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=LabelProfile(
            name="Wide",
            page_width_mm=100,
            page_height_mm=50,
            label_width_mm=100,
            label_height_mm=50,
            columns=1,
            rows=1,
        ),
    )
    text_object = TextObject(
        geometry=ObjectGeometry(x=50, y=30),
        text="Text",
        font_size=12,
    )

    short_rect = canvas_text_layout(text_object).editor_rect(label_rect)
    long_rect = canvas_text_layout(
        replace_text_object(text_object, "A much longer text value")
    ).editor_rect(label_rect)

    assert long_rect.x() == short_rect.x()
    assert long_rect.width() > short_rect.width()


def test_canvas_text_layout_editor_rect_clamps_width_inside_label() -> None:
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=LabelProfile(
            name="Wide",
            page_width_mm=100,
            page_height_mm=50,
            label_width_mm=100,
            label_height_mm=50,
            columns=1,
            rows=1,
        ),
    )
    text_object = TextObject(
        geometry=ObjectGeometry(x=190, y=30),
        text="Text",
        font_size=12,
    )

    editor_rect = canvas_text_layout(
        replace_text_object(text_object, "A much longer text value")
    ).editor_rect(label_rect)

    assert editor_rect.x() == label_rect.x() + 190
    assert editor_rect.x() + editor_rect.width() == label_rect.x() + label_rect.width()


def test_canvas_text_layout_editor_rect_keeps_left_edge_fixed_for_long_text() -> None:
    label_rect = preview_rect(
        width=248,
        height=400,
        profile=LabelProfile(
            name="Wide",
            page_width_mm=100,
            page_height_mm=50,
            label_width_mm=100,
            label_height_mm=50,
            columns=1,
            rows=1,
        ),
    )
    text_object = TextObject(
        geometry=ObjectGeometry(x=50, y=30),
        text="Text",
        font_size=12,
    )

    editor_rect = canvas_text_layout(
        replace_text_object(text_object, "A" * 200)
    ).editor_rect(label_rect)

    assert editor_rect.x() == label_rect.x() + 50
    assert editor_rect.x() + editor_rect.width() == label_rect.x() + label_rect.width()


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
    assert hit_test_text_object(document, x=10, y=25) is first
    assert hit_test_text_object(document, x=100, y=100) is None


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
    event = FakeMouseEvent(x=75, y=185)

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
    event = FakeMouseEvent(x=75, y=185)

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
    event = FakeMouseEvent(x=75, y=185)

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
    event = FakeMouseEvent(x=74, y=180)

    LabelCanvas.mouseDoubleClickEvent(canvas, event)

    assert len(document.objects) == 1
    text_object = document.objects[0]
    assert isinstance(text_object, TextObject)
    assert text_object.text == "Text"
    assert text_object.geometry.x == 50
    assert text_object.geometry.y == 30
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

    LabelCanvas.mousePressEvent(canvas, FakeMouseEvent(x=74, y=180))
    LabelCanvas.mouseDoubleClickEvent(canvas, FakeMouseEvent(x=74, y=180))

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
    assert (
        document.objects[0].geometry.width,
        document.objects[0].geometry.height,
    ) == measured_text_box_size(document.objects[0])
    assert canvas._text_editor is None
    assert canvas._editing_object_id is None
    assert canvas.update_count == 1


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
        self._text_editor = None
        self._editing_object_id = None
        self._editing_created_object_id = None

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def update(self) -> None:
        self.update_count += 1

    def setFocus(self) -> None:  # noqa: N802
        self.focused = True

    def _finish_text_edit(self, *, commit) -> None:
        LabelCanvas._finish_text_edit(self, commit=commit)

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

    def text(self) -> str:
        return self._text

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
