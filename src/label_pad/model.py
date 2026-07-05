"""Minimal label document data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TextObject:
    """Text placed on a label."""

    text: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class ImageObject:
    """Image placed on a label."""

    path: Path
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass
class LabelDocument:
    """A simple in-memory label document."""

    profile_name: str
    text_objects: list[TextObject] = field(default_factory=list)
    image_objects: list[ImageObject] = field(default_factory=list)
