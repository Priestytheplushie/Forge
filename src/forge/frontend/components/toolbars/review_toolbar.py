from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QLabel
from PySide6.QtCore import Signal

from ...assets.icon_map import get_status_icon


class ReviewToolbar(QWidget):
    """Toolbar for the Review Mode."""

    finish_review_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Review Mode</b>"))
        layout.addStretch()

        finish_button = QToolButton()
        finish_button.setText("Finish Review")
        finish_button.setToolTip("Exit Review Mode and discard any remaining changes.")
        finish_button.clicked.connect(self.finish_review_requested)
        layout.addWidget(finish_button)
