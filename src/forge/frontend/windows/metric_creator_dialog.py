from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QComboBox,
    QPlainTextEdit,
)
from PySide6.QtCore import Signal, Slot


class MetricCreatorDialog(QDialog):
    """Dialog to create a new custom metric for the master script."""

    create_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Custom Metric")
        self.setMinimumWidth(450)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Active Players")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Value", "Graph"])
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText("e.g., %, ms (optional)")
        self.code_edit = QPlainTextEdit()
        self.code_edit.setPlaceholderText("return len(pf.find('Player'))")

        form_layout.addRow("Metric Name:", self.name_edit)
        form_layout.addRow("Display Type:", self.type_combo)
        form_layout.addRow("Unit:", self.unit_edit)
        form_layout.addRow("Value Code:", self.code_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Create Metric")
        self.ok_button.setEnabled(False)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        self.name_edit.textChanged.connect(self._validate)
        self.code_edit.textChanged.connect(self._validate)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

    @Slot()
    def _validate(self):
        is_valid = bool(
            self.name_edit.text().strip() and self.code_edit.toPlainText().strip()
        )
        self.ok_button.setEnabled(is_valid)

    def on_accept(self):
        metric_data = {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentText().lower(),
            "unit": self.unit_edit.text().strip(),
            "code": self.code_edit.toPlainText().strip(),
        }
        self.create_requested.emit(metric_data)
        self.accept()
