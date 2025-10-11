from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QDialogButtonBox,
    QComboBox,
)
from PySide6.QtCore import Signal, Slot


class AddHookDialog(QDialog):
    """Dialog to select a new hook to add to the master script."""

    hook_selected = Signal(str)

    def __init__(self, available_hooks: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Hook Definition")
        self.setMinimumWidth(450)
        self.hook_data = available_hooks

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        info = QLabel(
            "Select a hook to add its function definition to the master script."
        )
        info.setWordWrap(True)

        self.hook_combo = QComboBox()
        self.hook_combo.addItems(sorted(self.hook_data.keys()))

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #888; margin-top: 5px;")

        form_layout.addRow(info)
        form_layout.addRow("Available Hooks:", self.hook_combo)
        form_layout.addRow("", self.description_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        layout.addLayout(form_layout)
        layout.addWidget(button_box)

        self.hook_combo.currentTextChanged.connect(self.on_hook_changed)
        self.on_hook_changed(self.hook_combo.currentText())

    @Slot(str)
    def on_hook_changed(self, hook_name: str):
        """Updates the description label when the combo box selection changes."""
        if hook_name in self.hook_data:
            self.description_label.setText(
                self.hook_data[hook_name].get("docstring", "No description available.")
            )

    def on_accept(self):
        self.hook_selected.emit(self.hook_combo.currentText())
        self.accept()
