from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal
from ...assets.icon_map import get_stop_icon


class SessionInfoPanel(QFrame):
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SessionInfoContainer")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("#SessionInfoContainer { border-top: 1px solid #444; }")
        self.setMaximumHeight(180)

        session_layout = QVBoxLayout(self)
        session_layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("PyForge Session")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")

        self.script_label = QLabel("<b>Script:</b> <i>unknown</i>")
        self.pid_label = QLabel("<b>PID:</b> <i>waiting...</i>")
        self.uptime_label = QLabel("<b>Uptime:</b> 00:00:00")

        self.stop_button = QPushButton("Stop PyForge Session")
        self.stop_button.setIcon(get_stop_icon())

        session_layout.addWidget(title)
        session_layout.addWidget(self.script_label)
        session_layout.addWidget(self.pid_label)
        session_layout.addWidget(self.uptime_label)
        session_layout.addStretch()
        session_layout.addWidget(self.stop_button)

        self.stop_button.clicked.connect(self.stop_requested)
