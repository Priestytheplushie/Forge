from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QColor
from pathlib import Path
import os

from .terminal_bridge import TerminalBridge
from ....backend.terminal_backend import TerminalBackend


class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_frontend_ready = False
        self.is_backend_started = False
        self._pending_workspace_path = None

        print("[TerminalWidget] __init__")
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

        html_file_path = Path(__file__).resolve().parent / "web" / "terminal.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_file_path)))

    def start_session(self, workspace_path: str):
        print(
            f"[TerminalWidget] Received request to start session for '{workspace_path}'"
        )
        if self.is_backend_started:
            print("[TerminalWidget] Existing session found. Shutting down...")
            self.shutdown()

        self.is_backend_started = False
        self._pending_workspace_path = workspace_path

        if self.is_frontend_ready:
            print(
                "[TerminalWidget] Frontend is ready, clearing display and requesting size."
            )
            self.web_view.page().runJavaScript("clear_terminal();")
            self.web_view.page().runJavaScript("request_initial_size();")
        else:
            print("[TerminalWidget] Frontend not yet ready. New session is queued.")

    def shutdown(self):
        print("[TerminalWidget] Shutdown requested.")
        self.backend.close()
        self.is_backend_started = False

    @Slot()
    def _on_frontend_ready(self):
        self.is_frontend_ready = True
        print("[TerminalWidget] EVENT: Frontend is ready (_on_frontend_ready).")
        if self._pending_workspace_path and not self.is_backend_started:
            print(
                "[TerminalWidget] A start request is pending. Requesting size from JS."
            )
            self.web_view.page().runJavaScript("clear_terminal();")
            self.web_view.page().runJavaScript("request_initial_size();")
        else:
            print(
                "[TerminalWidget] Frontend is ready, but no start request is pending."
            )

    @Slot(int, int)
    def _start_backend_with_size(self, cols: int, rows: int):
        print(
            f"[TerminalWidget] SLOT: _start_backend_with_size received size: {cols}x{rows}"
        )
        if self.is_backend_started:
            return
        if not self._pending_workspace_path:
            return
        if cols > 0 and rows > 0:
            path_to_start = self._pending_workspace_path
            self._pending_workspace_path = None
            print(f"[TerminalWidget] Size is valid. Starting backend process...")
            self.is_backend_started = True
            self.backend.start_pty_process(path_to_start, cols, rows)
        else:
            print(
                f"[TerminalWidget] ERROR: Received invalid size from JavaScript signal."
            )

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
            self.web_view.page().runJavaScript("resize_terminal")
