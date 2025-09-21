from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox


class ActionConfirmationDialog(QDialog):
    """A generic confirmation dialog for potentially destructive actions."""

    def __init__(self, title: str, message: str, action_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.action_button = button_box.addButton(
            action_text, QDialogButtonBox.ButtonRole.AcceptRole
        )

        layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
