from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QObject, Slot, QTimer, Signal, Qt
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QColor, QAction, QKeySequence
from pathlib import Path
import uuid
import json
import os

from .editor_bridge import EditorBridge


class EditorWidget(QWidget):
    text_changed = Signal()
    js_log_received = Signal(str)
    completion_requested = Signal(QObject, str, str, int, int)
    hover_requested = Signal(QObject, str, str, int, int)
    code_action_requested = Signal(QObject, str, str, list)
    cursor_position_changed = Signal(int, int)
    mark_as_resolved_requested = Signal(object)
    all_conflicts_resolved = Signal(object)

    def __init__(self, theme_data: dict, parent=None):
        super().__init__(parent)
        self.is_ready = False
        self._initial_content_queue = []
        self.pending_callbacks = {}
        self.metadata = {}
        self.theme_data = theme_data

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(100)
        self.resize_timer.timeout.connect(self._on_resize_timeout)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        profile = QWebEngineProfile.defaultProfile()
        self.web_view = QWebEngineView()
        page = QWebEnginePage(profile, self)
        page.setBackgroundColor(
            QColor(
                self.theme_data.get("colors", {}).get("editor.background", "#1e1e1e")
            )
        )
        self.web_view.setPage(page)
        self.layout().addWidget(self.web_view)
        self.bridge = EditorBridge(self)
        self.channel = QWebChannel(self.web_view.page())
        self.web_view.page().setWebChannel(self.channel)
        self.channel.registerObject("bridge", self.bridge)

        self.bridge._internal_web_channel_ready.connect(self._on_web_channel_ready)
        self.bridge.js_ready.connect(self._on_frontend_ready)
        self.bridge.text_received.connect(self._on_text_received)
        self.bridge.content_changed_signal.connect(self.text_changed)
        self.bridge.js_log_received.connect(self._on_js_log)
        self.bridge.model_ready.connect(self._on_model_ready)
        self.bridge.semantic_tokens_applied.connect(self._on_semantic_tokens_applied)
        self.bridge.cursor_position_changed.connect(self.cursor_position_changed)
        self.bridge.conflict_check_result.connect(self._on_conflict_check_result)
        self.bridge.all_conflicts_resolved_in_editor.connect(
            lambda: self.all_conflicts_resolved.emit(self)
        )

        self.bridge._completion_requested_from_js.connect(
            self._on_completion_requested_from_js
        )
        self.bridge._hover_requested_from_js.connect(self._on_hover_requested_from_js)
        self.bridge._code_action_requested_from_js.connect(
            self._on_code_action_requested_from_js
        )

        self.mark_resolved_button = QPushButton("Mark as Resolved", self)
        self.mark_resolved_button.clicked.connect(
            lambda: self.mark_as_resolved_requested.emit(self)
        )
        self.mark_resolved_button.setVisible(False)
        self.mark_resolved_button.setStyleSheet("""
            QPushButton { 
                background-color: #3C3F41; color: #D8DEE9; border: 1px solid #555555; 
                padding: 8px 16px; border-radius: 4px; 
            }
            QPushButton:hover { background-color: #4B4E50; }
        """)

        self.merge_banner = QPushButton(self)
        self.merge_banner.setDisabled(True)
        self.merge_banner.setStyleSheet("""
            QPushButton {
                background-color: rgba(44, 49, 58, 0.85); 
                color: #abb2bf; 
                border: 1px solid #555555;
                padding: 4px 10px;
                border-radius: 4px;
            }
        """)
        self.merge_banner.setVisible(False)

        html_file_path = Path(__file__).resolve().parent / "web" / "index.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_file_path)))

        self.setup_actions()

    def enter_merge_mode(self):
        if not self.is_ready:
            return
        self.web_view.page().runJavaScript("enter_merge_mode();")
        self.mark_resolved_button.setVisible(True)

        file_path = self.property("file_path")

    def exit_merge_mode(self):
        if not self.is_ready:
            return
        self.web_view.page().runJavaScript("exit_merge_mode();")
        self.mark_resolved_button.setVisible(False)
        self.merge_banner.setVisible(False)

    def setup_actions(self):
        self.bridge.undo_requested.connect(
            lambda: self.web_view.triggerPageAction(QWebEnginePage.WebAction.Undo)
        )
        self.bridge.redo_requested.connect(
            lambda: self.web_view.triggerPageAction(QWebEnginePage.WebAction.Redo)
        )
        self.bridge.cut_requested.connect(
            lambda: self.web_view.triggerPageAction(QWebEnginePage.WebAction.Cut)
        )
        self.bridge.copy_requested.connect(
            lambda: self.web_view.triggerPageAction(QWebEnginePage.WebAction.Copy)
        )
        self.bridge.paste_requested.connect(
            lambda: self.web_view.triggerPageAction(QWebEnginePage.WebAction.Paste)
        )

    def apply_hunk(self, text: str):
        if self.is_ready:
            self.web_view.page().runJavaScript(f"apply_hunk({json.dumps(text)});")

    def apply_theme(self, theme_data: dict):
        self.theme_data = theme_data
        self.web_view.page().setBackgroundColor(
            QColor(
                self.theme_data.get("colors", {}).get("editor.background", "#1e1e1e")
            )
        )
        self.web_view.page().runJavaScript(f"set_theme({json.dumps(self.theme_data)});")

    @Slot()
    def _on_web_channel_ready(self):
        """Called from JS via the bridge when the web channel is established."""
        print("[EditorWidget] Web channel is ready. Initializing Monaco editor.")
        theme_json = json.dumps(self.theme_data)
        self.web_view.page().runJavaScript(f"initialize_editor({theme_json});")

    def set_read_only(self, read_only: bool):
        if self.is_ready:
            self.web_view.page().runJavaScript(
                f"set_read_only({str(read_only).lower()});"
            )
        else:
            self._initial_content_queue.append(
                ("set_read_only", {"read_only": read_only})
            )

    def setFocus(self):
        self.web_view.setFocus()

    def jump_and_highlight(self, line: int, char: int):
        if self.is_ready:
            self.web_view.page().runJavaScript(
                f"jump_and_highlight({line + 1}, {char + 1});"
            )

    @Slot(str, str)
    def _on_js_log(self, level: str, message: str):
        self.js_log_received.emit(f"[JS-{level.upper()}] {message}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        padding = 20

        self.mark_resolved_button.adjustSize()
        btn_size = self.mark_resolved_button.size()
        x_btn = self.width() - btn_size.width() - padding
        y_btn = self.height() - btn_size.height() - padding
        self.mark_resolved_button.move(x_btn, y_btn)
        self.mark_resolved_button.raise_()

        self.merge_banner.adjustSize()
        banner_size = self.merge_banner.size()
        x_banner = self.width() - banner_size.width() - padding
        self.merge_banner.move(x_banner, padding)
        self.merge_banner.raise_()

        if self.is_ready:
            self.resize_timer.start()

    @Slot()
    def _on_resize_timeout(self):
        self.web_view.page().runJavaScript("layout_editor();")

    @Slot()
    def _on_frontend_ready(self):
        self.is_ready = True
        if self._initial_content_queue:
            for action, data in self._initial_content_queue:
                if action == "set_content":
                    self.set_content(
                        data["content"], data["lang_id"], data["uri"], data["callback"]
                    )
                elif action == "set_read_only":
                    self.set_read_only(data["read_only"])
            self._initial_content_queue = []

    @Slot(str, str)
    def _on_text_received(self, callback_id, content):
        if callback_id in self.pending_callbacks:
            self.pending_callbacks.pop(callback_id)(content)

    @Slot(str)
    def _on_model_ready(self, callback_id: str):
        if callback_id in self.pending_callbacks:
            self.pending_callbacks.pop(callback_id)()

    @Slot(str)
    def _on_semantic_tokens_applied(self, callback_id: str):
        if callback_id in self.pending_callbacks:
            self.pending_callbacks.pop(callback_id)()

    @Slot(str, bool)
    def _on_conflict_check_result(self, callback_id: str, has_conflicts: bool):
        if callback_id in self.pending_callbacks:
            self.pending_callbacks.pop(callback_id)(has_conflicts)

    @Slot(str, str, int, int)
    def _on_completion_requested_from_js(self, callback_id, uri, line, character):
        self.completion_requested.emit(self, callback_id, uri, line, character)

    @Slot(str, str, int, int)
    def _on_hover_requested_from_js(self, callback_id, uri, line, character):
        self.hover_requested.emit(self, callback_id, uri, line, character)

    @Slot(str, str, list)
    def _on_code_action_requested_from_js(self, callback_id, uri, diagnostics):
        self.code_action_requested.emit(self, callback_id, uri, diagnostics)

    def resolve_completions(self, callback_id: str, completions: list):
        if self.is_ready:
            self.web_view.page().runJavaScript(
                f"resolve_completions('{callback_id}', {json.dumps(completions)});"
            )

    def resolve_hover(self, callback_id: str, hover_result: dict):
        if self.is_ready:
            hover_json = json.dumps(hover_result) if hover_result else "null"
            self.web_view.page().runJavaScript(
                f"resolve_hover('{callback_id}', {hover_json});"
            )

    def set_content(self, content: str, lang_id: str, uri: str, callback):
        if self.is_ready:
            callback_id = str(uuid.uuid4())
            self.pending_callbacks[callback_id] = callback
            escaped_content = json.dumps(content)
            self.web_view.page().runJavaScript(
                f"set_content({escaped_content}, '{lang_id}', '{uri}', '{callback_id}');"
            )
        else:
            self._initial_content_queue.append(
                (
                    "set_content",
                    {
                        "content": content,
                        "lang_id": lang_id,
                        "uri": uri,
                        "callback": callback,
                    },
                )
            )

    def get_text(self, callback):
        if self.is_ready:
            callback_id = str(uuid.uuid4())
            self.pending_callbacks[callback_id] = callback
            self.web_view.page().runJavaScript(f"getText('{callback_id}');")
        else:
            callback(None)

    def check_for_conflicts(self, callback):
        if self.is_ready:
            callback_id = str(uuid.uuid4())
            self.pending_callbacks[callback_id] = callback
            self.web_view.page().runJavaScript(f"check_for_conflicts('{callback_id}');")
        else:
            callback(False)

    def show_diagnostics(self, diagnostics: list):
        if not self.is_ready:
            return
        markers = []
        for diag in diagnostics:
            start_line, start_col = (
                diag["range"]["start"]["line"] + 1,
                diag["range"]["start"]["character"] + 1,
            )
            end_line, end_col = (
                diag["range"]["end"]["line"] + 1,
                diag["range"]["end"]["character"] + 1,
            )
            lsp_severity = diag.get("severity", 4)
            monaco_severity = 1
            if lsp_severity == 1:
                monaco_severity = 8
            elif lsp_severity == 2:
                monaco_severity = 4
            elif lsp_severity == 3:
                monaco_severity = 2

            code_val = diag.get("code")
            if code_val is not None:
                code_val = str(code_val)

            markers.append(
                {
                    "startLineNumber": start_line,
                    "startColumn": start_col,
                    "endLineNumber": end_line,
                    "endColumn": end_col,
                    "message": diag["message"],
                    "severity": monaco_severity,
                    "code": code_val,
                }
            )
        self.web_view.page().runJavaScript(f"set_diagnostics({json.dumps(markers)});")

    def show_semantic_tokens(self, token_data: list):
        if not self.is_ready:
            return
        callback_id = str(uuid.uuid4())
        self.pending_callbacks[callback_id] = lambda: None
        self.web_view.page().runJavaScript(
            f"set_semantic_tokens({json.dumps(token_data)}, '{callback_id}');"
        )
