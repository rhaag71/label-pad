"""Label canvas widget."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from label_pad.canvas_editor import EDITOR_STYLE, InlineTextEditor
from label_pad.canvas_geometry import (
    clamped_label_coordinates_from_widget,
    label_coordinates_from_widget,
    label_size_points,
    preview_rect,
    preview_scale,
)
from label_pad.canvas_hit_testing import (
    hit_test_text_object,
    hit_test_text_resize_handle,
    text_object_hit_rect,
    text_object_resize_handle_rect,
)
from label_pad.canvas_objects import (
    move_document_object,
    resize_document_object,
    select_document_object,
    update_text_object,
)
from label_pad.model import LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile
from label_pad.renderer import QtRenderContext, Renderer
from label_pad.text_fonts import (
    editor_font_for_text_object,
    editor_font_for_text_object_at_scale,
)
from label_pad.text_layout import (
    MIN_TEXT_BOX_HEIGHT,
    MIN_TEXT_BOX_WIDTH,
    TEXT_BOX_HORIZONTAL_PADDING,
    TEXT_BOX_VERTICAL_PADDING,
    canvas_text_layout,
    measured_text_box_size,
    natural_text_box_auto_width,
    natural_text_box_height,
    natural_text_box_minimum_width,
    text_object_bounds,
    with_live_editor_text_box,
)

_InlineTextEditor = InlineTextEditor

_HELPER_REEXPORTS = (
    TEXT_BOX_HORIZONTAL_PADDING,
    TEXT_BOX_VERTICAL_PADDING,
    text_object_bounds,
    text_object_hit_rect,
)

@dataclass(frozen=True)
class DragState:
    """Transient canvas drag state for moving a selected object box."""

    object_id: str
    start_pointer_x: float
    start_pointer_y: float
    start_object_x: float
    start_object_y: float
    object_width: float
    object_height: float


@dataclass(frozen=True)
class ResizeState:
    """Transient canvas resize state for the bottom-right object handle."""

    object_id: str
    start_pointer_x: float
    start_pointer_y: float
    start_width: float
    start_height: float
    object_x: float
    object_y: float


class LabelCanvas(QWidget):
    """White preview surface with box selection and inline text editing.

    Box selection is the normal canvas state used for future move/delete behavior.
    Text editing is an exclusive state owned by the inline QLineEdit.
    """

    def __init__(
        self,
        profile: LabelProfile,
        document: LabelDocument,
        renderer: Renderer | None = None,
        selection_changed_callback=None,
    ) -> None:
        super().__init__()
        self._profile = profile
        self._document = document
        self._renderer = renderer or Renderer()
        self._selection_changed_callback = selection_changed_callback
        # Text editing state is separate from document box selection.
        self._text_editor = None
        self._editing_object_id = None
        self._editing_created_object_id = None
        self._resizing_text_editor = False
        self._drag_state = None
        self._resize_state = None
        self.setMinimumSize(320, 220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def set_profile(self, profile: LabelProfile, document: LabelDocument) -> None:
        self._profile = profile
        self._document = document
        self.update()

    def clear(self) -> None:
        self._document.clear()
        self._notify_selection_changed()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag_state = None
        self._resize_state = None
        if self._text_editor is not None:
            self._finish_text_edit(commit=True)
        self.setFocus()
        coordinates = label_coordinates_from_widget(
            widget_x=event.position().x(),
            widget_y=event.position().y(),
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        if coordinates is None:
            select_document_object(self._document, None)
            self._notify_selection_changed()
            self.update()
            event.accept()
            return

        x, y = coordinates
        resized_object = hit_test_text_resize_handle(self._document, x=x, y=y)
        if resized_object is not None:
            select_document_object(self._document, resized_object.geometry.id)
            self._notify_selection_changed()
            self._resize_state = _resize_state_for_text_object(
                text_object=resized_object,
                pointer_x=x,
                pointer_y=y,
            )
            self.update()
            event.accept()
            return

        selected_object = hit_test_text_object(self._document, x=x, y=y)
        if selected_object is None:
            select_document_object(self._document, None)
        else:
            select_document_object(self._document, selected_object.geometry.id)
            self._drag_state = _drag_state_for_text_object(
                text_object=selected_object,
                pointer_x=x,
                pointer_y=y,
            )
        self._notify_selection_changed()
        self.update()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._text_editor is not None:
            event.ignore()
            return
        if self._drag_state is None and self._resize_state is None:
            self._update_hover_cursor(event)
            event.ignore()
            return

        pointer_x, pointer_y = clamped_label_coordinates_from_widget(
            widget_x=event.position().x(),
            widget_y=event.position().y(),
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        label_width, label_height = label_size_points(self._profile)
        if self._resize_state is not None:
            label_object = self._document.find_by_id(self._resize_state.object_id)
            if not isinstance(label_object, TextObject):
                event.ignore()
                return
            width, height = _resized_object_size(
                resize_state=self._resize_state,
                text_object=label_object,
                pointer_x=pointer_x,
                pointer_y=pointer_y,
                label_width=label_width,
                label_height=label_height,
            )
            resize_document_object(
                self._document,
                self._resize_state.object_id,
                width=width,
                height=height,
            )
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.update()
            event.accept()
            return

        x, y = _dragged_object_position(
            drag_state=self._drag_state,
            pointer_x=pointer_x,
            pointer_y=pointer_y,
            label_width=label_width,
            label_height=label_height,
        )
        move_document_object(self._document, self._drag_state.object_id, x=x, y=y)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_state is None and self._resize_state is None:
            event.ignore()
            return
        self._drag_state = None
        self._resize_state = None
        self._update_hover_cursor(event)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._drag_state = None
        self._resize_state = None
        if self._text_editor is not None:
            self._finish_text_edit(commit=True)
            event.accept()
            return
        coordinates = label_coordinates_from_widget(
            widget_x=event.position().x(),
            widget_y=event.position().y(),
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        if coordinates is None:
            event.ignore()
            return

        x, y = coordinates
        selected_object = hit_test_text_object(self._document, x=x, y=y)
        if selected_object is None:
            width, height = _new_text_box_size(self._document)
            selected_object = self._document.create_text(
                x,
                y,
                width=width,
                height=height,
            )
            created = True
        else:
            select_document_object(self._document, selected_object.geometry.id)
            self._notify_selection_changed()
            created = False
        self._start_text_edit(selected_object, created=created)
        self._notify_selection_changed()
        self.update()
        event.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._text_editor is not None:
            event.ignore()
            return

        if event.key() != Qt.Key.Key_Delete:
            event.ignore()
            return

        selected_objects = self._document.selected_objects()
        if not selected_objects:
            event.ignore()
            return

        for label_object in selected_objects:
            self._document.remove_object(label_object.geometry.id)
        self.update()
        event.accept()

    def _notify_selection_changed(self) -> None:
        if self._selection_changed_callback is not None:
            self._selection_changed_callback()

    def _update_hover_cursor(self, event) -> None:
        coordinates = label_coordinates_from_widget(
            widget_x=event.position().x(),
            widget_y=event.position().y(),
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        if coordinates is None:
            self.unsetCursor()
            return

        x, y = coordinates
        resized_object = hit_test_text_resize_handle(self._document, x=x, y=y)
        if resized_object is not None:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            return

        hovered_object = hit_test_text_object(self._document, x=x, y=y)
        if hovered_object is not None and hovered_object.geometry.selected:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def _start_text_edit(self, text_object: TextObject, *, created: bool) -> None:
        """Start exclusive inline text editing for a TextObject."""
        self._finish_text_edit(commit=True)
        self._editing_object_id = text_object.geometry.id
        self._editing_created_object_id = (
            text_object.geometry.id if created else None
        )
        self._text_editor = InlineTextEditor(self._cancel_text_edit, self)
        self._text_editor.set_commit_callback(
            lambda: self._finish_text_edit(commit=True)
        )
        self._text_editor.setFrame(False)
        self._text_editor.setStyleSheet(EDITOR_STYLE)
        self._text_editor.setContentsMargins(0, 0, 0, 0)
        self._text_editor.setTextMargins(0, 0, 0, 0)
        self._text_editor.setAlignment(
            _qt_text_alignment(text_object.alignment)
            | Qt.AlignmentFlag.AlignVCenter
        )
        self._text_editor.setFont(editor_font_for_text_object(text_object))
        self._text_editor.setText(text_object.text)
        self._text_editor.textChanged.connect(self._resize_text_editor)

        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        scale = preview_scale(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        self._text_editor.setFont(
            editor_font_for_text_object_at_scale(text_object, scale=scale)
        )
        self._text_editor.setGeometry(
            canvas_text_layout(text_object).editor_rect(label_rect, scale)
        )
        self._text_editor.selectAll()
        self._text_editor.show()
        self._text_editor.setFocus()

    def refresh_active_editor(self) -> None:
        """Apply current TextObject formatting to the active inline editor."""
        editor = self._text_editor
        object_id = self._editing_object_id
        if editor is None or object_id is None:
            return
        label_object = self._document.find_by_id(object_id)
        if not isinstance(label_object, TextObject):
            return
        editor.setAlignment(
            _qt_text_alignment(label_object.alignment)
            | Qt.AlignmentFlag.AlignVCenter
        )
        self._resize_text_editor()

    def _resize_text_editor(self) -> None:
        if getattr(self, "_resizing_text_editor", False):
            return
        editor = self._text_editor
        object_id = self._editing_object_id
        if editor is None or object_id is None:
            return
        self._resizing_text_editor = True
        try:
            label_object = self._document.find_by_id(object_id)
            if not isinstance(label_object, TextObject):
                return
            label_rect = preview_rect(
                width=self.width(),
                height=self.height(),
                profile=self._profile,
            )
            scale = preview_scale(
                width=self.width(),
                height=self.height(),
                profile=self._profile,
            )
            label_width, _ = label_size_points(self._profile)
            max_width = max(1, label_width - label_object.geometry.x)
            editor.setAlignment(
                _qt_text_alignment(label_object.alignment)
                | Qt.AlignmentFlag.AlignVCenter
            )
            editor.setFont(
                editor_font_for_text_object_at_scale(label_object, scale=scale)
            )
            editor.setGeometry(
                canvas_text_layout(
                    with_live_editor_text_box(
                        replace(label_object, text=editor.text()),
                        max_width=max_width,
                    )
                ).editor_rect(label_rect, scale)
            )
        finally:
            self._resizing_text_editor = False

    def _cancel_text_edit(self) -> None:
        self._finish_text_edit(commit=False)

    def _finish_text_edit(self, *, commit: bool) -> None:
        editor = self._text_editor
        object_id = self._editing_object_id
        created_object_id = self._editing_created_object_id
        if editor is None or object_id is None:
            return

        self._text_editor = None
        self._editing_object_id = None
        self._editing_created_object_id = None
        if commit:
            label_object = self._document.find_by_id(object_id)
            if isinstance(label_object, TextObject):
                label_width, label_height = label_size_points(self._profile)
                max_width = max(1, label_width - label_object.geometry.x)
                max_height = max(1, label_height - label_object.geometry.y)
                updated_object = replace(label_object, text=editor.text())
                width = (
                    natural_text_box_auto_width(updated_object, max_width=max_width)
                    if label_object.auto_size
                    else label_object.geometry.width
                )
                if width <= 0:
                    width = natural_text_box_auto_width(
                        updated_object,
                        max_width=max_width,
                    )
                width = min(width, max_width)
                natural_height = natural_text_box_height(updated_object, width)
                height = (
                    natural_height
                    if label_object.auto_size
                    else max(label_object.geometry.height, natural_height)
                )
                height = min(height, max_height)
                update_text_object(
                    self._document,
                    object_id,
                    editor.text(),
                    width=width,
                    height=height,
                )
        elif object_id == created_object_id:
            self._document.remove_object(object_id)
        editor.deleteLater()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawRect(label_rect)

        painter.save()
        painter.setClipRect(label_rect)
        painter.translate(label_rect.topLeft())
        scale = preview_scale(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        painter.scale(scale, scale)
        self._renderer.render(
            self._paint_document(),
            QtRenderContext(painter, font_scale=1 / scale),
        )
        painter.setPen(QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for label_object in self._document.selected_objects():
            if not isinstance(label_object, TextObject):
                continue
            painter.drawRect(canvas_text_layout(label_object).box_rect)
            painter.fillRect(
                text_object_resize_handle_rect(label_object),
                Qt.GlobalColor.white,
            )
            painter.drawRect(text_object_resize_handle_rect(label_object))
        painter.restore()

    def _paint_document(self) -> LabelDocument:
        """Return the canvas document view while inline editing is active."""
        if self._editing_object_id is None:
            return self._document
        return LabelDocument(
            profile_name=self._document.profile_name,
            objects=[
                label_object
                for label_object in self._document.objects
                if label_object.geometry.id != self._editing_object_id
            ],
            defaults=self._document.defaults,
        )


def _new_text_box_size(document: LabelDocument) -> tuple[float, float]:
    defaults = document.defaults
    text_object = TextObject(
        geometry=ObjectGeometry(),
        text="Text",
        font_family=defaults.font_family,
        font_size=defaults.font_size,
        bold=defaults.bold,
        italic=defaults.italic,
        underline=defaults.underline,
        wrap=defaults.wrap,
        alignment=defaults.alignment,
        text_color=defaults.text_color,
    )
    return measured_text_box_size(text_object)


def _qt_text_alignment(alignment: str) -> Qt.AlignmentFlag:
    if alignment == "center":
        return Qt.AlignmentFlag.AlignHCenter
    if alignment == "right":
        return Qt.AlignmentFlag.AlignRight
    return Qt.AlignmentFlag.AlignLeft


def _drag_state_for_text_object(
    *,
    text_object: TextObject,
    pointer_x: float,
    pointer_y: float,
) -> DragState:
    layout = canvas_text_layout(text_object)
    return DragState(
        object_id=text_object.geometry.id,
        start_pointer_x=pointer_x,
        start_pointer_y=pointer_y,
        start_object_x=text_object.geometry.x,
        start_object_y=text_object.geometry.y,
        object_width=layout.box_rect.width(),
        object_height=layout.box_rect.height(),
    )


def _resize_state_for_text_object(
    *,
    text_object: TextObject,
    pointer_x: float,
    pointer_y: float,
) -> ResizeState:
    layout = canvas_text_layout(text_object)
    return ResizeState(
        object_id=text_object.geometry.id,
        start_pointer_x=pointer_x,
        start_pointer_y=pointer_y,
        start_width=layout.box_rect.width(),
        start_height=layout.box_rect.height(),
        object_x=text_object.geometry.x,
        object_y=text_object.geometry.y,
    )


def _dragged_object_position(
    *,
    drag_state: DragState,
    pointer_x: float,
    pointer_y: float,
    label_width: float,
    label_height: float,
) -> tuple[float, float]:
    x = drag_state.start_object_x + pointer_x - drag_state.start_pointer_x
    y = drag_state.start_object_y + pointer_y - drag_state.start_pointer_y
    return (
        min(max(x, 0), max(0, label_width - drag_state.object_width)),
        min(max(y, 0), max(0, label_height - drag_state.object_height)),
    )


def _resized_object_size(
    *,
    resize_state: ResizeState,
    text_object: TextObject,
    pointer_x: float,
    pointer_y: float,
    label_width: float,
    label_height: float,
) -> tuple[float, float]:
    width = resize_state.start_width + pointer_x - resize_state.start_pointer_x
    height = resize_state.start_height + pointer_y - resize_state.start_pointer_y
    max_width = max(MIN_TEXT_BOX_WIDTH, label_width - resize_state.object_x)
    max_height = max(MIN_TEXT_BOX_HEIGHT, label_height - resize_state.object_y)
    min_width = min(max_width, natural_text_box_minimum_width(text_object))
    width = min(max(width, min_width), max_width)
    natural_height = natural_text_box_height(text_object, width)
    min_height = min(max_height, max(MIN_TEXT_BOX_HEIGHT, natural_height))
    return (
        width,
        min(max(height, min_height), max_height),
    )
