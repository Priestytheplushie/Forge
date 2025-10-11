from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPlainTextEdit,
    QDialogButtonBox,
    QLabel,
)
from PySide6.QtCore import Signal, Slot


class SnippetEditorDialog(QDialog):
    """A mini-editor for adding top-level code to the master script."""

    snippet_saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Global Scope Snippet")

        layout = QVBoxLayout(self)

        info = QLabel(
            "Enter Python code to run in the global scope of the master script."
        )
        info.setWordWrap(True)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("e.g., pf.log('My custom startup message')")

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(info)
        layout.addWidget(self.editor)
        layout.addWidget(button_box)

    def on_accept(self):
        self.snippet_saved.emit(self.editor.toPlainText())
        self.accept()
