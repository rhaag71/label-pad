"""Label canvas widget."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, floor

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from label_pad.model import DocumentObject, LabelDocument, ObjectGeometry, TextObject
from label_pad.profiles import LabelProfile
from label_pad.renderer import QtRenderContext, Renderer

TEXT_BOX_HORIZONTAL_PADDING = 3
TEXT_BOX_VERTICAL_PADDING = 2
MIN_EDITOR_WIDTH = 48
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
        desired_height = max(1, ceil(self.box_rect.height()))
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


def measured_text_box_size(text_object: TextObject) -> tuple[float, float]:
    """Return a sane padded box size for text using the canvas render font."""
    font = editor_font_for_text_object(text_object)
    metrics = QFontMetricsF(font)
    text = text_object.text or " "
    text_width = max(metrics.horizontalAdvance(text), metrics.horizontalAdvance(" "))
    text_height = metrics.ascent() + metrics.descent()
    return (
        text_width + TEXT_BOX_HORIZONTAL_PADDING * 2,
        text_height + TEXT_BOX_VERTICAL_PADDING * 2,
    )


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
        box_rect = canvas_text_layout(label_object).box_rect
        if box_rect.contains(x, y):
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
        editor.setGeometry(
            canvas_text_layout(
                _with_measured_text_box(replace(label_object, text=editor.text()))
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
                width, height = measured_text_box_size(
                    replace(label_object, text=editor.text())
                )
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


def _with_measured_text_box(text_object: TextObject) -> TextObject:
    width, height = measured_text_box_size(text_object)
    return replace(
        text_object,
        geometry=replace(text_object.geometry, width=width, height=height),
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
