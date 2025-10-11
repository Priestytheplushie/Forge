from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
)
from PySide6.QtCore import Slot
import re


class TemplateDialog(QDialog):
    def __init__(self, template_content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Template")
        self.setMinimumWidth(400)

        self.placeholders = re.findall(r"\{\{([A-Z_]+)\}\}", template_content)
        self.editors = {}
        self.results = {}

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        for placeholder in self.placeholders:
            label_text = placeholder.replace("_", " ").title()
            editor = QLineEdit()
            form_layout.addRow(QLabel(f"{label_text}:"), editor)
            self.editors[placeholder] = editor

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        for editor in self.editors.values():
            editor.textChanged.connect(self._validate)

        self._validate()

    @Slot()
    def _validate(self):
        all_filled = all(editor.text().strip() for editor in self.editors.values())
        self.ok_button.setEnabled(all_filled)

    def on_accept(self):
        for placeholder, editor in self.editors.items():
            self.results[placeholder] = editor.text().strip()
        self.accept()
