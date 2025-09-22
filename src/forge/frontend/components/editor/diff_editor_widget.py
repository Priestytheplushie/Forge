from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Slot, Signal, Qt
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QColor
from pathlib import Path
import json
import time

from .editor_bridge import DiffBridge
from .editor_widget import RecoverableWebEnginePage


class DiffEditorWidget(QWidget):
    primary_action_requested = Signal(object)
    secondary_action_requested = Signal(object)
    stage_lines_requested = Signal(str)
    accept_file_requested = Signal(object)
    discard_file_requested = Signal(object)

    def __init__(self, theme_data: dict, parent=None):
        super().__init__(parent)
        self.is_ready = False
        self._pending_content = None
        self.theme_data = theme_data
        self.last_recovery_time = 0

        profile = QWebEngineProfile.defaultProfile()
        self.web_view = QWebEngineView(self)
        page = RecoverableWebEnginePage(profile, self)
        bg_color = self.theme_data.get("colors", {}).get("editor.background", "#1e1e1e")
        page.setBackgroundColor(QColor(bg_color))
        self.web_view.setPage(page)

        page.critical_js_error_detected.connect(self._trigger_recovery_reload)
        self.web_view.renderProcessTerminated.connect(self._trigger_recovery_reload)

        self.bridge = DiffBridge(self)
        self.channel = QWebChannel(self.web_view.page())
        self.web_view.page().setWebChannel(self.channel)
        self.channel.registerObject("diff_bridge", self.bridge)
        self.bridge._internal_web_channel_ready.connect(self._on_web_channel_ready)
        self.bridge.js_ready.connect(self._on_js_ready)
        self.bridge.stage_lines_requested.connect(self.stage_lines_requested)

        self.primary_action_button = QPushButton("Action", self)
        self.primary_action_button.clicked.connect(
            lambda: self.primary_action_requested.emit(self)
        )
        self.primary_action_button.setVisible(False)

        self.secondary_action_button = QPushButton("Action 2", self)
        self.secondary_action_button.clicked.connect(
            lambda: self.secondary_action_requested.emit(self)
        )
        self.secondary_action_button.setVisible(False)

        self.review_button_widget = QWidget(self)
        review_layout = QHBoxLayout(self.review_button_widget)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(10)
        self.accept_button = QPushButton("Accept File")
        self.discard_button = QPushButton("Discard File")
        review_layout.addWidget(self.accept_button)
        review_layout.addWidget(self.discard_button)
        self.review_button_widget.setVisible(False)
        self.accept_button.clicked.connect(
            lambda: self.accept_file_requested.emit(self)
        )
        self.discard_button.clicked.connect(
            lambda: self.discard_file_requested.emit(self)
        )

        html_file_path = Path(__file__).resolve().parent / "web" / "index.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_file_path)))

    def enter_review_mode(self):
        self.review_button_widget.setVisible(True)
        self.primary_action_button.setVisible(False)

    def set_primary_action(self, text: str, visible: bool = True):
        self.primary_action_button.setText(text)
        self.primary_action_button.setVisible(visible)

    def set_secondary_action(self, text: str, visible: bool = True):
        self.secondary_action_button.setText(text)
        self.secondary_action_button.setVisible(visible)

    @Slot()
    def _on_web_channel_ready(self):
        theme_json = json.dumps(self.theme_data)
        self.web_view.page().runJavaScript(f"initialize_editor({theme_json}, true);")

    def apply_theme(self, theme_data: dict):
        self.theme_data = theme_data
        bg_color = self.theme_data.get("colors", {}).get("editor.background", "#1e1e1e")
        self.web_view.page().setBackgroundColor(QColor(bg_color))
        self.web_view.page().runJavaScript(f"set_theme({json.dumps(self.theme_data)});")

    @Slot()
    def _on_js_ready(self):
        self.is_ready = True
        if self._pending_content:
            self.set_diff_content(**self._pending_content)
            self._pending_content = None

    def set_diff_content(
        self,
        original_content: str,
        modified_content: str,
        original_label: str,
        modified_label: str,
    ):
        self._pending_content = {
            "original_content": original_content,
            "modified_content": modified_content,
            "original_label": original_label,
            "modified_label": modified_label,
        }
        if self.is_ready:
            js_original, js_modified = json.dumps(original_content), json.dumps(
                modified_content
            )
            js_original_label, js_modified_label = json.dumps(
                original_label
            ), json.dumps(modified_label)
            self.web_view.page().runJavaScript(
                f"set_diff_content({js_original}, {js_modified}, {js_original_label}, {js_modified_label});"
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.web_view.setGeometry(self.rect())
        padding = 20

        btn_size = self.primary_action_button.sizeHint()
        x = self.width() - btn_size.width() - padding
        y = self.height() - btn_size.height() - padding
        self.primary_action_button.move(x, y)

        sec_btn_size = self.secondary_action_button.sizeHint()
        x_sec = self.width() - sec_btn_size.width() - btn_size.width() - padding - 10
        self.secondary_action_button.move(x_sec, y)

        review_size = self.review_button_widget.sizeHint()
        review_x = self.width() - review_size.width() - padding
        review_y = self.height() - review_size.height() - padding
        self.review_button_widget.move(review_x, review_y)

        self.primary_action_button.raise_()
        self.secondary_action_button.raise_()
        self.review_button_widget.raise_()

        if self.is_ready:
            self.web_view.page().runJavaScript("layout_editor();")

    def _trigger_recovery_reload(self):
        current_time = time.time()
        if current_time - self.last_recovery_time < 5:
            return
        self.last_recovery_time = current_time
        self.is_ready = False
        self.web_view.reload()
