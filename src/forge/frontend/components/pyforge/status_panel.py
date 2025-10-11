from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFormLayout
from PySide6.QtCore import Signal
from pathlib import Path


class PyForgeStatusPanel(QWidget):
    """The panel shown in the Debug side panel when a PyForge session is active."""

    disconnect_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        title = QLabel("PyForge Session Active")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")

        form_layout = QFormLayout()
        self.pid_label = QLabel("N/A")
        self.script_label = QLabel("N/A")

        form_layout.addRow("Process ID:", self.pid_label)
        form_layout.addRow("Target Script:", self.script_label)

        self.disconnect_button = QPushButton("Disconnect Session")
        self.disconnect_button.setStyleSheet("background-color: #BF616A;")

        layout.addWidget(title)
        layout.addLayout(form_layout)
        layout.addWidget(self.disconnect_button)
        layout.addStretch()

        self.disconnect_button.clicked.connect(self.disconnect_requested)

    def set_session_info(self, pid, script):
        self.pid_label.setText(str(pid))
        self.script_label.setText(Path(script).name)
        self.script_label.setToolTip(script)
