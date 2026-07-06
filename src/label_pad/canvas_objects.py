"""Canvas document object mutation helpers."""

from __future__ import annotations

from dataclasses import replace

from label_pad.model import DocumentObject, LabelDocument, TextObject


def select_document_object(document: LabelDocument, object_id: str | None) -> None:
    """Set box selection to one object by id, or clear box selection."""
    document.objects = [
        _with_selected(label_object, label_object.geometry.id == object_id)
        for label_object in document.objects
    ]


def update_text_object(
    document: LabelDocument,
    object_id: str,
    text: str,
    width: float | None = None,
    height: float | None = None,
) -> TextObject | None:
    """Replace a text object's content and return the updated object."""
    for index, label_object in enumerate(document.objects):
        if label_object.geometry.id != object_id:
            continue
        if not isinstance(label_object, TextObject):
            return None
        geometry = label_object.geometry
        if width is not None and height is not None:
            geometry = replace(geometry, width=width, height=height)
        updated_object = replace(label_object, geometry=geometry, text=text)
        document.objects[index] = updated_object
        return updated_object
    return None


def move_document_object(
    document: LabelDocument,
    object_id: str,
    *,
    x: float,
    y: float,
) -> DocumentObject | None:
    """Move a document object by updating shared geometry position."""
    for index, label_object in enumerate(document.objects):
        if label_object.geometry.id != object_id:
            continue
        updated_object = replace(
            label_object,
            geometry=replace(label_object.geometry, x=x, y=y),
        )
        document.objects[index] = updated_object
        return updated_object
    return None


def resize_document_object(
    document: LabelDocument,
    object_id: str,
    *,
    width: float,
    height: float,
) -> DocumentObject | None:
    """Resize a document object by updating shared geometry size."""
    for index, label_object in enumerate(document.objects):
        if label_object.geometry.id != object_id:
            continue
        if isinstance(label_object, TextObject):
            label_object = replace(label_object, auto_size=False)
        updated_object = replace(
            label_object,
            geometry=replace(label_object.geometry, width=width, height=height),
        )
        document.objects[index] = updated_object
        return updated_object
    return None


def _with_selected(label_object: DocumentObject, selected: bool) -> DocumentObject:
    if label_object.geometry.selected is selected:
        return label_object
    return replace(
        label_object,
        geometry=replace(label_object.geometry, selected=selected),
    )
