"""Canvas coordinate and preview geometry helpers."""

from __future__ import annotations

from PySide6.QtCore import QRect

from label_pad.profiles import LabelProfile

POINTS_PER_MM = 72 / 25.4


def preview_rect(
    *,
    width: int,
    height: int,
    profile: LabelProfile,
    margin: int = 24,
) -> QRect:
    """Return the centered label preview rectangle for the widget size."""
    available_width = max(1, width - margin * 2)
    available_height = max(1, height - margin * 2)
    aspect = profile.label_width_mm / profile.label_height_mm

    canvas_width = available_width
    canvas_height = int(canvas_width / aspect)
    if canvas_height > available_height:
        canvas_height = available_height
        canvas_width = int(canvas_height * aspect)

    x = (width - canvas_width) // 2
    y = (height - canvas_height) // 2
    return QRect(x, y, canvas_width, canvas_height)


def label_size_points(profile: LabelProfile) -> tuple[float, float]:
    """Return label document size in PDF points."""
    return (
        profile.label_width_mm * POINTS_PER_MM,
        profile.label_height_mm * POINTS_PER_MM,
    )


def preview_scale(
    *,
    width: int,
    height: int,
    profile: LabelProfile,
    margin: int = 24,
) -> float:
    """Return widget-pixel scale for one document point in the preview."""
    label_rect = preview_rect(
        width=width,
        height=height,
        profile=profile,
        margin=margin,
    )
    label_width, label_height = label_size_points(profile)
    return min(label_rect.width() / label_width, label_rect.height() / label_height)


def label_coordinates_from_widget(
    *,
    widget_x: float,
    widget_y: float,
    width: int,
    height: int,
    profile: LabelProfile,
    margin: int = 24,
) -> tuple[float, float] | None:
    """Return label-local coordinates for a widget point inside the preview."""
    label_rect = preview_rect(
        width=width,
        height=height,
        profile=profile,
        margin=margin,
    )
    if not label_rect.contains(int(widget_x), int(widget_y)):
        return None
    scale = preview_scale(
        width=width,
        height=height,
        profile=profile,
        margin=margin,
    )
    return (
        (widget_x - label_rect.x()) / scale,
        (widget_y - label_rect.y()) / scale,
    )


def clamped_label_coordinates_from_widget(
    *,
    widget_x: float,
    widget_y: float,
    width: int,
    height: int,
    profile: LabelProfile,
    margin: int = 24,
) -> tuple[float, float]:
    """Return label-local coordinates clamped to the visible preview."""
    label_rect = preview_rect(
        width=width,
        height=height,
        profile=profile,
        margin=margin,
    )
    scale = preview_scale(
        width=width,
        height=height,
        profile=profile,
        margin=margin,
    )
    label_width, label_height = label_size_points(profile)
    return (
        min(max((widget_x - label_rect.x()) / scale, 0), label_width),
        min(max((widget_y - label_rect.y()) / scale, 0), label_height),
    )
