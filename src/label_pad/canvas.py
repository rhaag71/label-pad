"""Label canvas widget."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from label_pad.model import DocumentObject, LabelDocument, TextObject
from label_pad.profiles import LabelProfile
from label_pad.renderer import QtRenderContext, Renderer

TEXT_WIDTH_FACTOR = 0.6
EDITOR_HORIZONTAL_PADDING = 2
EDITOR_VERTICAL_PADDING = 8
MIN_EDITOR_WIDTH = 48
MIN_EDITOR_HEIGHT = 24
EDITOR_STYLE = """
QLineEdit {
    background: white;
    color: black;
    border: none;
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


def text_object_bounds(text_object: TextObject) -> tuple[float, float, float, float]:
    """Return a simple text hit/render bounds estimate."""
    width = max(
        text_object.font_size,
        len(text_object.text) * text_object.font_size * TEXT_WIDTH_FACTOR,
    )
    height = text_object.font_size
    return (
        text_object.geometry.x,
        text_object.geometry.y - height,
        width,
        height,
    )


def inline_editor_geometry(
    *,
    label_rect: QRect,
    text_object: TextObject,
    content_width: int,
) -> QRect:
    """Return an editor rectangle anchored to text and clamped inside the label."""
    x, y, estimated_width, estimated_height = text_object_bounds(text_object)
    label_left = label_rect.x()
    label_top = label_rect.y()
    label_right = label_rect.x() + label_rect.width()
    label_bottom = label_rect.y() + label_rect.height()

    left = min(max(int(label_left + x), label_left), max(label_left, label_right - 1))
    top = min(
        max(int(label_top + y), label_top),
        max(label_top, label_bottom - MIN_EDITOR_HEIGHT),
    )
    desired_width = max(
        MIN_EDITOR_WIDTH,
        int(max(estimated_width, content_width) + EDITOR_HORIZONTAL_PADDING),
    )
    width = min(desired_width, max(1, label_right - left))
    height = min(
        max(MIN_EDITOR_HEIGHT, int(estimated_height + EDITOR_VERTICAL_PADDING)),
        max(1, label_bottom - top),
    )
    return QRect(left, top, width, height)


def editor_font_for_text_object(text_object: TextObject) -> QFont:
    """Return the inline editor font matching the rendered text style."""
    font = QFont(text_object.font_family)
    font.setPointSizeF(text_object.font_size)
    font.setBold(text_object.bold)
    font.setItalic(text_object.italic)
    return font


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
        left, top, width, height = text_object_bounds(label_object)
        if left <= x <= left + width and top <= y <= top + height:
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
) -> TextObject | None:
    """Replace a text object's content and return the updated object."""
    for index, label_object in enumerate(document.objects):
        if label_object.geometry.id != object_id:
            continue
        if not isinstance(label_object, TextObject):
            return None
        updated_object = replace(label_object, text=text)
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
        self.setMinimumSize(320, 220)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_profile(self, profile: LabelProfile, document: LabelDocument) -> None:
        self._profile = profile
        self._document = document
        self.update()

    def clear(self) -> None:
        self._document.clear()
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
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
        selected_object = hit_test_text_object(self._document, x=x, y=y)
        if selected_object is None:
            select_document_object(self._document, None)
        else:
            select_document_object(self._document, selected_object.geometry.id)
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
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
            selected_object = self._document.create_text(x, y)
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

    def _start_text_edit(self, text_object: TextObject, *, created: bool) -> None:
        """Start exclusive inline text editing for a TextObject."""
        self._finish_text_edit(commit=True)
        self._editing_object_id = text_object.geometry.id
        self._editing_created_object_id = (
            text_object.geometry.id if created else None
        )
        self._text_editor = _InlineTextEditor(self._cancel_text_edit, self)
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
        self._text_editor.returnPressed.connect(
            lambda: self._finish_text_edit(commit=True)
        )
        self._text_editor.editingFinished.connect(
            lambda: self._finish_text_edit(commit=True)
        )

        label_rect = preview_rect(
            width=self.width(),
            height=self.height(),
            profile=self._profile,
        )
        self._text_editor.setGeometry(
            inline_editor_geometry(
                label_rect=label_rect,
                text_object=text_object,
                content_width=self._text_editor_content_width(),
            )
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
        editor.setGeometry(
            inline_editor_geometry(
                label_rect=label_rect,
                text_object=replace(label_object, text=editor.text()),
                content_width=self._text_editor_content_width(),
            )
        )

    def _text_editor_content_width(self) -> int:
        if self._text_editor is None:
            return 0
        return self._text_editor.fontMetrics().horizontalAdvance(
            self._text_editor.text() or " "
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
            update_text_object(self._document, object_id, editor.text())
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
            x, y, width, height = text_object_bounds(label_object)
            painter.drawRect(QRectF(x, y, width, height))
        painter.restore()


def _with_selected(label_object: DocumentObject, selected: bool) -> DocumentObject:
    if label_object.geometry.selected is selected:
        return label_object
    return replace(
        label_object,
        geometry=replace(label_object.geometry, selected=selected),
    )


class _InlineTextEditor(QLineEdit):
    def __init__(self, cancel_callback, parent: QWidget) -> None:
        super().__init__(parent)
        self._cancel_callback = cancel_callback

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_callback()
            event.accept()
            return
        super().keyPressEvent(event)
