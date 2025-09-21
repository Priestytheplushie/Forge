from PySide6.QtCore import QObject, Slot, QTimer, QTime, QMimeData, QPoint, Signal, QUrl
from PySide6.QtWidgets import (
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QWidget,
    QApplication,
    QStyle,
)
from PySide6.QtGui import QCursor, QDesktopServices, QAction, QKeySequence
from pathlib import Path
import os
import shutil

from forge.frontend.components.editor.editor_widget import EditorWidget
from forge.frontend.components.editor.diff_editor_widget import DiffEditorWidget
from forge.backend.history.manager import HistoryManager
from forge.backend.git.manager import GitManager
from forge.backend.refactor.manager import RefactorManager
from forge.frontend.controllers.lsp_client import LSPClient
from forge.frontend.controllers.git_controller import GitController
from forge.frontend.controllers.refactor_controller import RefactorController

AUTOSAVE_ENABLED = True
AUTOSAVE_DELAY_MS = 3000


class ClickableStatusBarWidget(QWidget):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class MainController(QObject):
    def __init__(
        self,
        main_window,
        theme_manager,
        file_manager,
        workspace_manager,
        run_manager,
        lsp_client,
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.theme_manager = theme_manager
        self.file_manager = file_manager
        self.workspace_manager = workspace_manager
        self.run_manager = run_manager
        self.lsp_client = lsp_client

        self.history_manager = HistoryManager(self)
        self.git_manager = GitManager(self)
        self.refactor_manager = RefactorManager(self)

        self.git_controller = GitController(
            main_window, self.git_manager, self.workspace_manager
        )
        self.refactor_controller = RefactorController(
            main_window,
            self.refactor_manager,
            self.workspace_manager,
            self.git_manager,
            self.file_manager,
            self.theme_manager,
        )

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(AUTOSAVE_DELAY_MS)

        self._connect_signals()
        self._initialize_ui_state()

    def _connect_signals(self):

        self.git_manager.branches_updated.connect(
            self.git_controller.on_branches_updated
        )
        self.git_manager.clone_finished.connect(self.git_controller.on_clone_finished)

        self.main_window.git_branch_widget.clicked.connect(
            self.git_controller.on_branch_menu_requested
        )

        self.workspace_manager.workspace_changed.connect(self.on_workspace_changed)
        self.workspace_manager.lsp_manager_created.connect(
            self.lsp_client.set_lsp_manager
        )
        self.file_manager.file_opened.connect(self.on_editor_opened)
        self.file_manager.file_closed.connect(self.on_file_closed)
        self.file_manager.file_modified.connect(self.on_file_modified)
        self.file_manager.file_saved.connect(self.history_manager.record_save)
        self.file_manager.file_saved.connect(self.on_file_saved)
        self.autosave_timer.timeout.connect(self.trigger_autosave)

        self.main_window.welcome_screen.action_triggered.connect(self.on_welcome_action)
        self.main_window.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.theme_manager.theme_changed.connect(self.on_theme_changed)

    def on_workspace_changed(self, path: str):
        self.file_manager.set_workspace_path(path)
        self.run_manager.set_workspace_path(path)
        self.lsp_client.clear_lsp_manager()
        self.history_manager.set_workspace_path(path)
        self.git_manager.set_workspace_path(path)

    def on_editor_opened(self, uri, lang_id, content, editor):

        self.lsp_client.on_file_opened(uri, lang_id, content, editor)
        editor.bridge.stage_lines_requested.connect(self.on_stage_lines)
        editor.bridge.apply_staged_changes_requested.connect(
            lambda e=editor: self.on_apply_staged_changes(e)
        )

    def on_file_closed(self, uri: str):
        self.lsp_client.on_file_closed(uri)

    @Slot(str)
    def on_stage_lines(self, selected_text: str):
        clipboard = QApplication.clipboard()
        mime_data = QMimeData()
        mime_data.setText(selected_text)
        mime_data.setData("application/x-forge-hunk", b"1")
        clipboard.setMimeData(mime_data)

    @Slot(EditorWidget)
    def on_apply_staged_changes(self, editor):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if not mime_data.hasFormat("application/x-forge-hunk"):
            return
        hunk_text = mime_data.text()
        final_text_lines = []
        for line in hunk_text.split("\n"):
            if line.startswith("+"):
                final_text_lines.append(line[1:])
        final_text = "\n".join(final_text_lines)
        editor.apply_hunk(final_text)

    def _initialize_ui_state(self):
        if not AUTOSAVE_ENABLED:
            self.main_window.autosave_status_label.setText("Autosave Disabled")

    def shutdown(self):
        self.refactor_controller.exit_review_mode()
        self.workspace_manager.shutdown_lsp()

    @Slot(int)
    def on_tab_changed(self, index: int):
        editor = self.main_window.tab_widget.widget(index)
        self.main_window.controller._update_ui_for_editor(editor)
        self.main_window.controller._update_timeline_for_editor(editor)

    @Slot(EditorWidget)
    def on_file_modified(self, editor):
        if AUTOSAVE_ENABLED:
            self.autosave_timer.start()

    @Slot()
    def trigger_autosave(self):
        editor = self.main_window.get_current_editor()
        if editor and editor in self.file_manager.dirty_editors:
            self.file_manager.save_file(editor)

    @Slot(str, str)
    def on_file_saved(self, file_path: str, content: str):
        self.main_window.autosave_status_label.setText(
            f"Saved at {QTime.currentTime().toString('HH:mm:ss')}"
        )
        editor = self.main_window.get_current_editor()
        if editor and self.file_manager.open_file_paths.get(editor) == file_path:
            self._update_timeline_for_editor(editor)

    @Slot(dict)
    def on_theme_changed(self, theme_data: dict):
        for i in range(self.main_window.tab_widget.count()):
            widget = self.main_window.tab_widget.widget(i)
            if hasattr(widget, "apply_theme"):
                widget.apply_theme(theme_data)
        for editor in self.file_manager.editor_cache:
            if hasattr(editor, "apply_theme"):
                editor.apply_theme(theme_data)
        if self.main_window._preloaded_editor:
            self.main_window._preloaded_editor.apply_theme(theme_data)

    def _update_ui_for_editor(self, editor):
        is_diff = isinstance(editor, DiffEditorWidget)
        is_review_diff = getattr(editor, "is_review_diff", False)

        if self.refactor_controller.in_review_mode:
            self.main_window.corner_stack.setCurrentWidget(
                self.main_window.review_toolbar
            )
        else:
            self.main_window.corner_stack.setCurrentWidget(
                self.main_window.normal_corner_widget
            )

        self.run_manager.update_run_actions_state(editor if not is_diff else None)

        if is_review_diff:
            original_path = getattr(editor, "change_data", {}).get("original_path")
            uri = Path(original_path).as_uri() if original_path else None
            self.lsp_client.update_outline_panel_from_uri(uri)
        else:
            self.lsp_client.update_outline_panel(editor if not is_diff else None)

    def _update_timeline_for_editor(self, editor):
        if not isinstance(editor, EditorWidget) or isinstance(editor, DiffEditorWidget):
            self.main_window.timeline_panel.clear_view()
            return

        file_path = self.file_manager.open_file_paths.get(editor)
        if not file_path:
            self.main_window.timeline_panel.clear_view()
            return

        local_history = self.history_manager.get_history_for_file(file_path)
        git_history = self.git_manager.get_file_commit_history(file_path)

        unified_history = []
        for path, meta in local_history:
            unified_history.append(
                {
                    "type": "save",
                    "timestamp": meta["timestamp"],
                    "path": str(path),
                    "meta": meta,
                }
            )
        for commit in git_history:
            unified_history.append(
                {"type": "commit", "timestamp": commit["timestamp"], **commit}
            )

        unified_history.sort(key=lambda x: x["timestamp"], reverse=True)
        self.main_window.timeline_panel.update_view(file_path, unified_history)

    @Slot(str)
    def on_welcome_action(self, action: str):
        if action == "open_folder":
            self.workspace_manager.open_workspace_dialog()
        elif action == "clone_repo":
            self.git_controller.on_clone_repo_requested()
