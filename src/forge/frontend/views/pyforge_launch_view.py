from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QHBoxLayout,
    QFrame,
)
from PySide6.QtCore import Signal
from ..assets.icon_map import get_pyforge_icon


class PyForgeLaunchView(QWidget):
    """The placeholder shown in the Debug side panel when no PyForge session is active."""

    launch_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        title = QLabel("PyForge Introspection")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")

        description = QLabel(
            "Run your Python application with live introspection capabilities. "
            "Modify variables, call functions, and script changes on the fly "
            "without restarting your process."
        )
        description.setWordWrap(True)
        description.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )

        self.launch_button = QPushButton("Launch with PyForge")
        self.launch_button.setIcon(get_pyforge_icon())
        self.launch_button.setToolTip(
            "Run the currently active Python file with the PyForge agent."
        )

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        help_layout = QHBoxLayout()
        self.docs_button = QPushButton("Documentation")
        self.tutorial_button = QPushButton("Interactive Tutorial")
        self.docs_button.setEnabled(False)
        self.tutorial_button.setEnabled(False)
        help_layout.addWidget(self.docs_button)
        help_layout.addWidget(self.tutorial_button)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(10)
        layout.addWidget(self.launch_button)

        layout.addStretch()
        layout.addWidget(line)
        layout.addLayout(help_layout)

        self.launch_button.clicked.connect(self.launch_requested)
