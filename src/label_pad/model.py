"""Minimal label document data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias
from uuid import uuid4


@dataclass(frozen=True)
class ObjectGeometry:
    """Shared object position and selection state."""

    id: str = field(default_factory=lambda: uuid4().hex)
    x: float = 0
    y: float = 0
    rotation: float = 0
    selected: bool = False


@dataclass(frozen=True)
class TextObject:
    """Text placed on a label."""

    geometry: ObjectGeometry = field(default_factory=ObjectGeometry)
    text: str = ""
    font_family: str = "Arial"
    font_size: float = 12
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class ImageObject:
    """Image placed on a label."""

    geometry: ObjectGeometry = field(default_factory=ObjectGeometry)
    image_path: Path = Path()
    display_width: float = 0
    display_height: float = 0
    keep_aspect_ratio: bool = True


DocumentObject: TypeAlias = TextObject | ImageObject


@dataclass
class LabelDocument:
    """A simple in-memory label document."""

    profile_name: str
    objects: list[DocumentObject] = field(default_factory=list)

    def add_object(self, label_object: DocumentObject) -> DocumentObject:
        """Append an object to the document and return it."""
        if self.find_by_id(label_object.geometry.id) is not None:
            raise ValueError(f"duplicate object id: {label_object.geometry.id}")
        self.objects.append(label_object)
        return label_object

    def remove_object(self, object_id: str) -> DocumentObject | None:
        """Remove an object by id and return it if present."""
        for index, label_object in enumerate(self.objects):
            if label_object.geometry.id == object_id:
                return self.objects.pop(index)
        return None

    def clear(self) -> None:
        """Remove all objects from the document."""
        self.objects.clear()

    def find_by_id(self, object_id: str) -> DocumentObject | None:
        """Find an object by id."""
        for label_object in self.objects:
            if label_object.geometry.id == object_id:
                return label_object
        return None

    def selected_objects(self) -> list[DocumentObject]:
        """Return selected objects in document order."""
        return [
            label_object
            for label_object in self.objects
            if label_object.geometry.selected
        ]
