from pathlib import Path

import pytest

from label_pad.model import (
    DocumentDefaults,
    ImageObject,
    LabelDocument,
    ObjectGeometry,
    TextObject,
)


def test_document_starts_with_empty_ordered_object_list() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")

    assert document.objects == []
    assert document.defaults == DocumentDefaults()


def test_text_object_defaults_and_fields() -> None:
    text_object = TextObject(
        geometry=ObjectGeometry(x=10, y=20),
        text="Ship to",
        font_family="Helvetica",
        font_size=14,
        bold=True,
        italic=True,
    )

    assert text_object.geometry.id
    assert text_object.geometry.x == 10
    assert text_object.geometry.y == 20
    assert text_object.geometry.rotation == 0
    assert text_object.geometry.selected is False
    assert text_object.text == "Ship to"
    assert text_object.font_family == "Helvetica"
    assert text_object.font_size == 14
    assert text_object.bold is True
    assert text_object.italic is True


def test_create_text_adds_default_text_object_and_returns_it() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")

    text_object = document.create_text(10, 20)

    assert document.objects == [text_object]
    assert text_object.geometry.x == 10
    assert text_object.geometry.y == 20
    assert text_object.geometry.selected is True
    assert text_object.text == "Text"
    assert text_object.font_family == "Helvetica"
    assert text_object.font_size == 14
    assert text_object.bold is False
    assert text_object.italic is False


def test_create_text_accepts_text_value() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")

    text_object = document.create_text(10, 20, text="Ship to")

    assert text_object.text == "Ship to"


def test_create_text_uses_document_defaults() -> None:
    defaults = DocumentDefaults(
        font_family="Arial",
        font_size=12,
        bold=True,
        italic=True,
    )
    document = LabelDocument(
        profile_name="4 x 6 Shipping Label",
        defaults=defaults,
    )

    text_object = document.create_text(10, 20)

    assert text_object.font_family == "Arial"
    assert text_object.font_size == 12
    assert text_object.bold is True
    assert text_object.italic is True


def test_create_text_deselects_existing_objects_and_selects_new_text() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    old_text = document.add_object(
        TextObject(geometry=ObjectGeometry(id="old", selected=True))
    )

    new_text = document.create_text(10, 20)

    assert document.objects[0].geometry.selected is False
    assert new_text.geometry.selected is True
    assert document.selected_objects() == [new_text]
    assert document.find_by_id(old_text.geometry.id) is document.objects[0]


def test_image_object_defaults_and_fields() -> None:
    image_object = ImageObject(
        geometry=ObjectGeometry(x=5, y=6, rotation=90, selected=True),
        image_path=Path("logo.png"),
        display_width=40,
        display_height=30,
        keep_aspect_ratio=False,
    )

    assert image_object.geometry.id
    assert image_object.geometry.x == 5
    assert image_object.geometry.y == 6
    assert image_object.geometry.rotation == 90
    assert image_object.geometry.selected is True
    assert image_object.image_path == Path("logo.png")
    assert image_object.display_width == 40
    assert image_object.display_height == 30
    assert image_object.keep_aspect_ratio is False


def test_object_ids_are_unique_by_default() -> None:
    first = TextObject()
    second = TextObject()

    assert first.geometry.id != second.geometry.id


def test_add_object_appends_and_returns_object() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    first = TextObject(geometry=ObjectGeometry(x=1, y=2), text="First")
    second = ImageObject(
        geometry=ObjectGeometry(x=3, y=4),
        image_path=Path("image.png"),
    )

    returned = document.add_object(first)
    document.add_object(second)

    assert returned is first
    assert document.objects == [first, second]


def test_add_object_rejects_duplicate_ids() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    first = TextObject(geometry=ObjectGeometry(id="same-id", x=1, y=2))
    second = ImageObject(geometry=ObjectGeometry(id="same-id", x=3, y=4))

    document.add_object(first)

    with pytest.raises(ValueError, match="duplicate object id: same-id"):
        document.add_object(second)


def test_find_by_id_returns_matching_object_or_none() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    first = document.add_object(
        TextObject(geometry=ObjectGeometry(id="first", x=1, y=2))
    )
    document.add_object(ImageObject(geometry=ObjectGeometry(id="second", x=3, y=4)))

    assert document.find_by_id("first") is first
    assert document.find_by_id("missing") is None


def test_remove_object_removes_matching_object_and_preserves_order() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    first = document.add_object(
        TextObject(geometry=ObjectGeometry(id="first", x=1, y=2))
    )
    second = document.add_object(
        TextObject(geometry=ObjectGeometry(id="second", x=3, y=4))
    )
    third = document.add_object(
        TextObject(geometry=ObjectGeometry(id="third", x=5, y=6))
    )

    removed = document.remove_object("second")

    assert removed is second
    assert document.objects == [first, third]


def test_remove_object_returns_none_for_missing_id() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    text_object = document.add_object(
        TextObject(geometry=ObjectGeometry(id="first", x=1, y=2))
    )

    assert document.remove_object("missing") is None
    assert document.objects == [text_object]


def test_clear_removes_all_objects() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    document.add_object(TextObject(geometry=ObjectGeometry(x=1, y=2)))
    document.add_object(ImageObject(geometry=ObjectGeometry(x=3, y=4)))

    document.clear()

    assert document.objects == []


def test_selected_objects_returns_selected_objects_in_document_order() -> None:
    document = LabelDocument(profile_name="4 x 6 Shipping Label")
    first = document.add_object(
        TextObject(geometry=ObjectGeometry(id="first", x=1, y=2, selected=True))
    )
    document.add_object(
        TextObject(geometry=ObjectGeometry(id="second", x=3, y=4, selected=False))
    )
    third = document.add_object(
        ImageObject(geometry=ObjectGeometry(id="third", x=5, y=6, selected=True))
    )

    assert document.selected_objects() == [first, third]
