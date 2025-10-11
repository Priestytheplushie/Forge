from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QStackedWidget,
)
from PySide6.QtCore import Signal, Qt
from ...assets.icon_map import get_stop_icon, get_status_icon


class CreateMasterScriptWidget(QWidget):
    """Placeholder widget with a button to create the master script."""

    create_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        info = QLabel("<b>Automate and Extend the PyForge Agent</b>")
        info.setWordWrap(True)

        desc = QLabel(
            "A Master Script allows you to write Python code that runs inside the live agent to create custom metrics, "
            "hook into events, and build powerful debugging tools tailored to your project."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888;")

        button = QPushButton("Create Master Script")
        button.clicked.connect(self.create_requested)

        layout.addWidget(info)
        layout.addWidget(desc)
        layout.addSpacing(10)
        layout.addWidget(button)
        layout.addStretch()


class SessionPanel(QWidget):
    stop_requested = Signal()
    create_master_script_requested = Signal()
    refresh_master_script_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("PyForgePanelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.addWidget(QLabel("PyForge Live Session"))

        main_layout.addWidget(header)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.script_label = QLabel("<b>Script:</b> <i>unknown</i>")
        self.script_label.setWordWrap(True)
        self.pid_label = QLabel("<b>PID:</b> <i>waiting...</i>")
        self.uptime_label = QLabel("<b>Uptime:</b> 00:00:00")

        master_script_header = QHBoxLayout()
        master_script_label = QLabel("Master Script Manager")
        master_script_label.setStyleSheet("font-weight: bold;")
        self.help_button = QPushButton("?")
        self.help_button.setFixedSize(20, 20)
        self.help_button.setToolTip("Learn about the Master Script Manager")

        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(get_status_icon("refresh-cw"))
        self.refresh_button.setFixedSize(20, 20)
        self.refresh_button.setToolTip("Save master.pfscript and Refresh View")

        master_script_header.addWidget(master_script_label)
        master_script_header.addStretch()
        master_script_header.addWidget(self.refresh_button)
        master_script_header.addWidget(self.help_button)

        self.stack = QStackedWidget()
        self.create_script_widget = CreateMasterScriptWidget()
        from .master_script_manager import MasterScriptManager

        self.master_script_manager = MasterScriptManager(self)
        self.stack.addWidget(self.create_script_widget)
        self.stack.addWidget(self.master_script_manager)

        self.stop_button = QPushButton("Stop PyForge Session")
        self.stop_button.setIcon(get_stop_icon())

        content_layout.addWidget(self.script_label)
        content_layout.addWidget(self.pid_label)
        content_layout.addWidget(self.uptime_label)
        content_layout.addSpacing(15)
        content_layout.addLayout(master_script_header)
        content_layout.addWidget(self.stack)
        content_layout.addWidget(self.stop_button)

        main_layout.addWidget(content_widget)

        self.stop_button.clicked.connect(self.stop_requested)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.create_script_widget.create_requested.connect(
            self.create_master_script_requested
        )
        self.refresh_button.clicked.connect(self.refresh_master_script_requested)

    def show_manager(self, show: bool):
        self.stack.setCurrentWidget(
            self.master_script_manager if show else self.create_script_widget
        )

    def show_help_dialog(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Master Script Manager")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(
            "The <b>Master Script Manager</b> provides a visual way to interact with your <code>master.pfscript</code> file.<br><br>"
            "<ul>"
            "<li><b>Hooks:</b> Attach modular <code>.pfscript</code> files (Event Scripts) to run when agent events occur.</li>"
            "<li><b>Custom Metrics:</b> Define new metrics that will appear in the Metrics panel.</li>"
            "<li><b>Global Scope:</b> Add code that runs once when the master script is loaded.</li>"
            "</ul>"
            "Double-click any item to jump to its definition in the text editor. Right-click for more options, including adding items from templates."
        )
        msg_box.exec()
