from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class ReviewPlaceholder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        title = QLabel("Review Hub")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")

        description = QLabel(
            "This is where you can approve changes from refactoring tools, "
            "AI agents, and code reviews."
        )
        description.setWordWrap(True)

        self.refactor_button = QPushButton("Run a Refactoring Tool...")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.refactor_button)
        layout.addStretch()
