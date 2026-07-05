"""Label canvas widget."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, floor

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QFrame, QTextEdit, QWidget

from label_pad.model import DocumentObject, LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile
from label_pad.renderer import QtRenderContext, Renderer

TEXT_BOX_HORIZONTAL_PADDING = 3
TEXT_BOX_VERTICAL_PADDING = 3
TEXT_BOX_HIT_SLOP = 4
RESIZE_HANDLE_SIZE = 6
RESIZE_HANDLE_HIT_SLOP = 3
MIN_TEXT_BOX_WIDTH = 24
MIN_TEXT_BOX_HEIGHT = 10
MIN_EDITOR_WIDTH = 48
EDITOR_STYLE = """
QTextEdit {
    background: white;
    color: black;
    border: 1px solid #2f6fed;
    margin: 0;
    padding: 0;
    selection-background-color: #cfe3ff;
    selection-color: black;
}
"""


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
    return (widget_x - label_rect.x(), widget_y - label_rect.y())


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
    return (
        min(max(widget_x - label_rect.x(), 0), label_rect.width()),
        min(max(widget_y - label_rect.y(), 0), label_rect.height()),
    )


@dataclass(frozen=True)
class CanvasTextLayout:
    """Canvas-side text box metrics shared by hit testing, selection, and editing."""

    text_object: TextObject
    font: QFont
    box_rect: QRectF

    def editor_rect(self, label_rect: QRect) -> QRect:
        """Return an absolute editor rectangle clamped inside the label preview."""
        label_left = label_rect.x()
        label_top = label_rect.y()
        label_right = label_rect.x() + label_rect.width()
        label_bottom = label_rect.y() + label_rect.height()

        left = min(
            max(floor(label_left + self.box_rect.x()), label_left),
            max(label_left, label_right - 1),
        )
        top = min(
            max(floor(label_top + self.box_rect.y()), label_top),
            max(label_top, label_bottom - 1),
        )
        desired_width = max(MIN_EDITOR_WIDTH, ceil(self.box_rect.width()))
        desired_height = max(
            1,
            ceil(self.box_rect.height()),
            ceil(natural_text_box_height(self.text_object, self.box_rect.width())),
        )
        width = min(desired_width, max(1, label_right - left))
        height = min(desired_height, max(1, label_bottom - top))
        return QRect(left, top, width, height)


def editor_font_for_text_object(text_object: TextObject) -> QFont:
    """Return the inline editor font matching the rendered text style."""
    font = QFont(text_object.font_family)
    font.setPointSizeF(text_object.font_size)
    font.setBold(text_object.bold)
    font.setItalic(text_object.italic)
    return font


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


def measured_text_box_size(text_object: TextObject) -> tuple[float, float]:
    """Return a sane padded box size for text using the canvas render font."""
    return (
        natural_text_box_auto_width(text_object),
        natural_text_box_height(
            text_object,
            natural_text_box_auto_width(text_object),
        ),
    )


def natural_text_box_auto_width(
    text_object: TextObject,
    max_width: float | None = None,
) -> float:
    """Return the unwrapped width needed for explicit text lines."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    text_width = max(
        metrics.horizontalAdvance(line or " ")
        for line in (text_object.text or " ").split("\n")
    )
    width = text_width + TEXT_BOX_HORIZONTAL_PADDING * 2
    if max_width is not None:
        width = min(width, max(1, max_width))
    return width


def natural_text_box_minimum_width(text_object: TextObject) -> float:
    """Return the minimum width that avoids breaking unbreakable words."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    words = [
        word
        for line in (text_object.text or " ").split("\n")
        for word in line.split()
    ]
    text_width = max(
        [metrics.horizontalAdvance(word) for word in words]
        + [metrics.horizontalAdvance(" ")]
    )
    return max(MIN_TEXT_BOX_WIDTH, text_width + TEXT_BOX_HORIZONTAL_PADDING * 2)


def natural_text_box_height(text_object: TextObject, width: float) -> float:
    """Return the content-aware minimum box height for current text/font/wrap."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    inner_width = max(1, width - TEXT_BOX_HORIZONTAL_PADDING * 2)
    line_count = len(
        _wrapped_canvas_lines(
            text=text_object.text or " ",
            metrics=metrics,
            width=inner_width,
            wrap=text_object.wrap,
        )
    )
    return line_count * metrics.lineSpacing() + TEXT_BOX_VERTICAL_PADDING * 2


def canvas_text_layout(text_object: TextObject) -> CanvasTextLayout:
    """Return canvas text box layout backed by object geometry."""
    font = editor_font_for_text_object(text_object)
    width = text_object.geometry.width
    height = text_object.geometry.height
    if width <= 0 or height <= 0:
        width, height = measured_text_box_size(text_object)
    box_rect = QRectF(
        text_object.geometry.x,
        text_object.geometry.y,
        width,
        height,
    )
    return CanvasTextLayout(
        text_object=text_object,
        font=font,
        box_rect=box_rect,
    )


def text_object_bounds(text_object: TextObject) -> tuple[float, float, float, float]:
    """Return the shared padded text box bounds in label coordinates."""
    rect = canvas_text_layout(text_object).box_rect
    return (rect.x(), rect.y(), rect.width(), rect.height())


def text_object_hit_rect(text_object: TextObject) -> QRectF:
    """Return the forgiving interaction bounds without changing visible geometry."""
    return canvas_text_layout(text_object).box_rect.adjusted(
        -TEXT_BOX_HIT_SLOP,
        -TEXT_BOX_HIT_SLOP,
        TEXT_BOX_HIT_SLOP,
        TEXT_BOX_HIT_SLOP,
    )


def text_object_resize_handle_rect(text_object: TextObject) -> QRectF:
    """Return the visible bottom-right resize handle for a text object."""
    box_rect = canvas_text_layout(text_object).box_rect
    return QRectF(
        box_rect.right() - RESIZE_HANDLE_SIZE,
        box_rect.bottom() - RESIZE_HANDLE_SIZE,
        RESIZE_HANDLE_SIZE,
        RESIZE_HANDLE_SIZE,
    )


def text_object_resize_handle_hit_rect(text_object: TextObject) -> QRectF:
    """Return the forgiving hit bounds for the visible resize handle."""
    return text_object_resize_handle_rect(text_object).adjusted(
        -RESIZE_HANDLE_HIT_SLOP,
        -RESIZE_HANDLE_HIT_SLOP,
        RESIZE_HANDLE_HIT_SLOP,
        RESIZE_HANDLE_HIT_SLOP,
    )


def hit_test_text_resize_handle(
    document: LabelDocument,
    *,
    x: float,
    y: float,
) -> TextObject | None:
    """Return the topmost selected text object whose resize handle contains a point."""
    for label_object in reversed(document.selected_objects()):
        if not isinstance(label_object, TextObject):
            continue
        if text_object_resize_handle_hit_rect(label_object).contains(x, y):
            return label_object
    return None


def hit_test_text_object(
    document: LabelDocument,
    *,
    x: float,
    y: float,
) -> TextObject | None:
    """Return the topmost text object whose estimated bounds contain a point."""
    for label_object in reversed(document.objects):
        if not isinstance(label_object, TextObject):
            continue
        if text_object_hit_rect(label_object).contains(x, y):
            return label_object
    return None


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
    ) -> None:
        super().__init__()
        self._profile = profile
        self._document = document
        self._renderer = renderer or Renderer()
        # Text editing state is separate from document box selection.
        self._text_editor = None
        self._editing_object_id = None
        self._editing_created_object_id = None
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
            self.update()
            event.accept()
            return

        x, y = coordinates
        resized_object = hit_test_text_resize_handle(self._document, x=x, y=y)
        if resized_object is not None:
            select_document_object(self._document, resized_object.geometry.id)
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
        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
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
                label_width=label_rect.width(),
                label_height=label_rect.height(),
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
            label_width=label_rect.width(),
            label_height=label_rect.height(),
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
            created = False
        self._start_text_edit(selected_object, created=created)
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
        self._text_editor = _InlineTextEditor(self._cancel_text_edit, self)
        self._text_editor.set_commit_callback(
            lambda: self._finish_text_edit(commit=True)
        )
        self._text_editor.setFrame(False)
        self._text_editor.setStyleSheet(EDITOR_STYLE)
        self._text_editor.setContentsMargins(0, 0, 0, 0)
        self._text_editor.setTextMargins(0, 0, 0, 0)
        self._text_editor.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._text_editor.setFont(editor_font_for_text_object(text_object))
        self._text_editor.setText(text_object.text)
        self._text_editor.textChanged.connect(self._resize_text_editor)

        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        self._text_editor.setGeometry(
            canvas_text_layout(text_object).editor_rect(label_rect)
        )
        self._text_editor.selectAll()
        self._text_editor.show()
        self._text_editor.setFocus()

    def _resize_text_editor(self) -> None:
        editor = self._text_editor
        object_id = self._editing_object_id
        if editor is None or object_id is None:
            return
        label_object = self._document.find_by_id(object_id)
        if not isinstance(label_object, TextObject):
            return
        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        max_width = max(1, label_rect.width() - label_object.geometry.x)
        editor.setGeometry(
            canvas_text_layout(
                _with_live_editor_text_box(
                    replace(label_object, text=editor.text()),
                    max_width=max_width,
                )
            ).editor_rect(label_rect)
        )

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
                label_rect = preview_rect(
                    width=self.width(),
                    height=self.height(),
                    profile=self._profile,
                )
                max_width = max(1, label_rect.width() - label_object.geometry.x)
                max_height = max(1, label_rect.height() - label_object.geometry.y)
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
        self._renderer.render(self._document, QtRenderContext(painter))
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


def _with_selected(label_object: DocumentObject, selected: bool) -> DocumentObject:
    if label_object.geometry.selected is selected:
        return label_object
    return replace(
        label_object,
        geometry=replace(label_object.geometry, selected=selected),
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
    )
    return measured_text_box_size(text_object)


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


def _with_measured_text_box(text_object: TextObject) -> TextObject:
    width, height = measured_text_box_size(text_object)
    if text_object.geometry.height > 0:
        height = text_object.geometry.height
    return replace(
        text_object,
        geometry=replace(text_object.geometry, width=width, height=height),
    )


def _with_live_editor_text_box(
    text_object: TextObject,
    *,
    max_width: float | None = None,
) -> TextObject:
    if text_object.auto_size:
        width = natural_text_box_auto_width(text_object, max_width=max_width)
        height = natural_text_box_height(text_object, width)
        return replace(
            text_object,
            geometry=replace(text_object.geometry, width=width, height=height),
        )
    return _with_minimum_text_box_height(text_object)


def _with_minimum_text_box_height(text_object: TextObject) -> TextObject:
    width = text_object.geometry.width
    if width <= 0:
        width, _ = measured_text_box_size(text_object)
    height = max(
        text_object.geometry.height,
        natural_text_box_height(text_object, width),
    )
    return replace(
        text_object,
        geometry=replace(text_object.geometry, width=width, height=height),
    )


def _wrapped_canvas_lines(
    *,
    text: str,
    metrics: QFontMetricsF,
    width: float,
    wrap: bool,
) -> list[str]:
    lines: list[str] = []
    paragraphs = text.split("\n") or [""]
    for paragraph in paragraphs:
        if not wrap:
            lines.append(paragraph)
            continue
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = word if current == "" else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = _fit_canvas_word(word, metrics, width, lines)
        lines.append(current)
    return lines


def _fit_canvas_word(
    word: str,
    metrics: QFontMetricsF,
    width: float,
    lines: list[str],
) -> str:
    current = ""
    for character in word:
        candidate = current + character
        if current and metrics.horizontalAdvance(candidate) > width:
            lines.append(current)
            current = character
        else:
            current = candidate
    return current


class _InlineTextEditor(QTextEdit):
    def __init__(self, cancel_callback, parent: QWidget) -> None:
        super().__init__(parent)
        self._cancel_callback = cancel_callback
        self._commit_callback = None
        self._finished = False
        self.setAcceptRichText(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def set_commit_callback(self, commit_callback) -> None:
        self._commit_callback = commit_callback

    def setFrame(self, enabled: bool) -> None:  # noqa: N802
        shape = QFrame.Shape.StyledPanel if enabled else QFrame.Shape.NoFrame
        self.setFrameShape(shape)

    def setTextMargins(self, left: int, top: int, right: int, bottom: int) -> None:  # noqa: N802, ARG002
        self.document().setDocumentMargin(0)

    def setText(self, text: str) -> None:  # noqa: N802
        self.setPlainText(text)

    def text(self) -> str:
        return self.toPlainText()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._finished = True
            self._cancel_callback()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self._finished:
            return
        self._finished = True
        if self._commit_callback is not None:
            self._commit_callback()
