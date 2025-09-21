from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Slot, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QColor
from pathlib import Path

from .terminal_bridge import TerminalBridge
from ....backend.terminal_backend import TerminalBackend


class TerminalInstance(QWidget):
    """A self-contained widget that hosts a single terminal session."""

    name_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_frontend_ready = False
        self.is_backend_started = False
        self._pending_workspace_path = None
        self.display_name = "shell"
        self._command_queue = []

        self.backend = TerminalBackend(self)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        profile = QWebEngineProfile.defaultProfile()
        self.web_view = QWebEngineView()
        page = QWebEnginePage(profile, self)
        page.setBackgroundColor(QColor("transparent"))
        self.web_view.setPage(page)
        self.layout().addWidget(self.web_view)
        self.bridge = TerminalBridge(self)
        self.channel = QWebChannel(self.web_view.page())
        self.web_view.page().setWebChannel(self.channel)
        self.channel.registerObject("bridge", self.bridge)

        self.bridge.js_ready.connect(self._on_frontend_ready)
        self.bridge.start_backend_requested.connect(self._start_backend_with_size)
        self.bridge.resize_requested.connect(self.backend.set_pty_size)
        self.bridge.data_to_backend.connect(self.backend.write_to_pty)
        self.backend.data_for_frontend.connect(self.write_to_terminal)
        self.backend.process_detected.connect(self.on_process_detected)

        html_file_path = Path(__file__).resolve().parent / "web" / "terminal.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_file_path)))

    def start_session(self, workspace_path: str):
        if self.is_backend_started:
            self.shutdown()

        self.is_backend_started = False
        self._pending_workspace_path = workspace_path

        if self.is_frontend_ready:
            self.web_view.page().runJavaScript("clear_terminal();")
            self.web_view.page().runJavaScript("request_initial_size();")

    def send_command(self, command: str):
        """Queues a command to be sent to the terminal, ensuring it's sent only after the backend is ready."""
        if self.is_backend_started:
            self.backend.write_to_pty(command)
        else:
            self._command_queue.append(command)

    def shutdown(self):
        self.backend.close()
        self.is_backend_started = False

    @Slot(str)
    def on_process_detected(self, name: str):
        if self.display_name != name:
            self.display_name = name
            self.name_changed.emit(self.display_name)

    @Slot()
    def _on_frontend_ready(self):
        self.is_frontend_ready = True
        if self._pending_workspace_path and not self.is_backend_started:
            self.web_view.page().runJavaScript("clear_terminal();")
            self.web_view.page().runJavaScript("request_initial_size();")

    @Slot(int, int)
    def _start_backend_with_size(self, cols: int, rows: int):
        if self.is_backend_started:
            return
        if not self._pending_workspace_path:
            return
        if cols > 0 and rows > 0:
            path_to_start = self._pending_workspace_path
            self._pending_workspace_path = None
            self.is_backend_started = True
            self.backend.start_pty_process(path_to_start, cols, rows)
            self.display_name = self.backend.get_shell_name()
            self.name_changed.emit(self.display_name)

            for cmd in self._command_queue:
                self.backend.write_to_pty(cmd)
            self._command_queue.clear()

    @Slot(str)
    def write_to_terminal(self, data: str):
        if self.is_frontend_ready:
            escaped_data = (
                data.replace("\\", "\\\\")
                .replace("`", "\\`")
                .replace("\r", "\\r")
                .replace("\n", "\\n")
            )
            self.web_view.page().runJavaScript(f"write_to_terminal(`{escaped_data}`);")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_frontend_ready and self.is_backend_started:
            self.web_view.page().runJavaScript("resize_terminal()")
