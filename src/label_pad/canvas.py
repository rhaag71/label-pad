"""Canvas primitives for arranging labels."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """A two-dimensional point."""

    x: float
    y: float
