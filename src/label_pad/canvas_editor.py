"""Inline canvas text editor widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QTextEdit, QWidget

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


class InlineTextEditor(QTextEdit):
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

    def setTextMargins(  # noqa: N802
        self,
        left: int,  # noqa: ARG002
        top: int,  # noqa: ARG002
        right: int,  # noqa: ARG002
        bottom: int,  # noqa: ARG002
    ) -> None:
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
