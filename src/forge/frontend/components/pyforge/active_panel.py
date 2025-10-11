from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Signal, QTimer, QTime, QElapsedTimer
from pathlib import Path

from .object_browser import ObjectBrowser
from .metrics_panel import MetricsPanel
from .session_panel import SessionPanel
from .audit_log_panel import AuditLogPanel
from ...assets.icon_map import get_status_icon, get_audit_log_icon


class PyForgeActivePanel(QWidget):
    """The panel shown in the Debug side view when a PyForge session is active."""

    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.tab_widget = QTabWidget()

        self.session_panel = SessionPanel(self)
        self.metrics_panel = MetricsPanel(self)
        self.object_browser = ObjectBrowser(self)

        self.audit_log_panel = AuditLogPanel(None, self)

        self.tab_widget.addTab(self.session_panel, get_status_icon("sliders"), "")
        self.tab_widget.setTabToolTip(0, "Session")

        self.tab_widget.addTab(self.metrics_panel, get_status_icon("activity"), "")
        self.tab_widget.setTabToolTip(1, "Metrics")

        self.tab_widget.addTab(self.object_browser, get_status_icon("database"), "")
        self.tab_widget.setTabToolTip(2, "Object Browser")

        self.tab_widget.addTab(self.audit_log_panel, get_audit_log_icon(), "")
        self.tab_widget.setTabToolTip(3, "Audit Log")

        main_layout.addWidget(self.tab_widget)

        self.session_panel.stop_requested.connect(self.stop_requested)

        self.uptime_timer = QTimer(self)
        self.uptime_timer.setInterval(1000)
        self.uptime_timer.timeout.connect(self.update_uptime)
        self.session_start_timer = QElapsedTimer()

    def set_controller(self, controller):
        """Assigns the controller to child widgets that need it."""
        self.audit_log_panel.pyforge_controller = controller

    def set_session_info(self, script_name: str, pid: int = -1):
        self.session_panel.script_label.setText(f"<b>Script:</b> {script_name}")
        if pid != -1:
            self.session_panel.pid_label.setText(f"<b>PID:</b> {pid}")
        else:
            self.session_panel.pid_label.setText("<b>PID:</b> <i>retrieving...</i>")

        self.session_start_timer.start()
        self.uptime_timer.start()
        self.update_uptime()

    def clear_session_info(self):
        self.session_panel.script_label.setText("<b>Script:</b> <i>unknown</i>")
        self.session_panel.pid_label.setText("<b>PID:</b> <i>N/A</i>")
        self.session_panel.uptime_label.setText("<b>Uptime:</b> 00:00:00")
        self.uptime_timer.stop()
        self.audit_log_panel.clear_log()

    def update_uptime(self):
        if self.uptime_timer.isActive():
            elapsed_ms = self.session_start_timer.elapsed()
            uptime = QTime(0, 0, 0).addMSecs(elapsed_ms)
            self.session_panel.uptime_label.setText(
                f"<b>Uptime:</b> {uptime.toString('HH:mm:ss')}"
            )
