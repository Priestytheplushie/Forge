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
import time

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

        self.refactor_controller = RefactorController(
            main_window,
            self.workspace_manager,
            self.file_manager,
            self.theme_manager,
            self.lsp_client,
        )
        self.refactor_manager = RefactorManager(
            self.refactor_controller.tool_registry, self
        )

        self.refactor_controller.set_managers(self.refactor_manager, self.git_manager)

        self.git_controller = GitController(
            main_window, self.git_manager, self.workspace_manager, self.file_manager
        )

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(AUTOSAVE_DELAY_MS)

        self._connect_signals()
        self.refactor_controller.init_connections()
        self.git_controller.init_connections()

        self._initialize_ui_state()

    def _connect_signals(self):

        self.git_manager.repo_status_changed.connect(
            self.main_window.source_control_panel.set_repo_status
        )
        self.git_manager.repo_status_changed.connect(
            self.git_controller.on_repo_status_changed
        )
        self.git_manager.status_changed.connect(
            self.main_window.source_control_panel.update_files
        )
        self.git_manager.branch_changed.connect(self.git_controller.on_branch_changed)
        self.git_manager.remote_status_changed.connect(
            self.git_controller.on_remote_status_changed
        )
        self.git_manager.head_commit_changed.connect(
            self.git_controller.on_head_commit_changed
        )
        self.git_manager.merge_conflict_detected.connect(
            self.git_controller.on_merge_conflict
        )
        self.git_manager.branches_updated.connect(
            self.git_controller.on_branches_updated
        )
        self.git_manager.clone_finished.connect(self.git_controller.on_clone_finished)
        self.git_manager.git_command_output.connect(
            lambda msg: self.main_window.log_to_output("Git", msg)
        )
        self.git_manager.upstream_branch_not_found.connect(
            self.git_controller.on_upstream_branch_not_found
        )

        self.main_window.git_branch_widget.clicked.connect(
            self.git_controller.on_branch_menu_requested
        )
        self.main_window.source_control_panel.file_selected.connect(
            self.git_controller.on_git_file_selected
        )
        self.main_window.source_control_panel.discard_changes_requested.connect(
            self.on_discard_changes_requested
        )
        self.main_window.conflicts_panel.file_selected.connect(
            self.git_controller.on_conflict_file_selected
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
        self.main_window.welcome_screen.open_recent_requested.connect(
            self.workspace_manager.set_workspace
        )
        self.main_window.file_menu.actions()[1].triggered.connect(
            self.workspace_manager.open_workspace_dialog
        )
        self.main_window.welcome_file_explorer.open_folder_button.clicked.connect(
            self.workspace_manager.open_workspace_dialog
        )
        self.main_window.welcome_file_explorer.clone_repo_button.clicked.connect(
            self.git_controller.on_clone_repo_requested
        )

        self.main_window.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.theme_manager.theme_changed.connect(self.on_theme_changed)

        timeline_panel = self.main_window.timeline_panel
        timeline_panel.history_item_selected.connect(self.on_history_item_selected)
        timeline_panel.item_single_clicked.connect(self.on_history_item_selected)
        timeline_panel.restore_requested.connect(self.on_history_restore_requested)
        timeline_panel.delete_requested.connect(self.on_history_delete_requested)
        timeline_panel.delete_all_requested.connect(
            self.on_history_delete_all_requested
        )
        timeline_panel.pin_toggled.connect(self.on_history_pin_toggled)
        timeline_panel.rename_requested.connect(self.on_history_rename_requested)
        timeline_panel.compare_with_requested.connect(
            self.on_history_compare_with_current
        )
        timeline_panel.show_contents_requested.connect(
            self.on_history_show_contents_requested
        )

    def on_workspace_changed(self, path: str):
        self.git_controller.exit_merge_mode()
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
        editor.js_log_received.connect(self.on_editor_log)

    @Slot(str)
    def on_editor_log(self, message: str):
        self.main_window.log_to_output("Debug", message, raise_panel=False)

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
        self._update_ui_for_editor(editor)
        self._update_timeline_for_editor(editor)

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
        if self.git_controller.is_in_merge_conflict:
            self.git_manager.refresh_status()

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
        self.main_window.welcome_screen.apply_theme(theme_data)

    def _update_ui_for_editor(self, editor):
        is_diff = isinstance(editor, DiffEditorWidget)
        is_review_diff = getattr(editor, "is_review_diff", False)
        is_history_view = getattr(editor, "metadata", {}).get("is_history_view", False)

        if self.refactor_controller.in_review_mode:
            self.main_window.corner_stack.setCurrentWidget(
                self.main_window.review_toolbar
            )
        else:
            self.main_window.corner_stack.setCurrentWidget(
                self.main_window.normal_corner_widget
            )

        self.run_manager.update_run_actions_state(editor if not is_diff else None)

        if is_review_diff or is_history_view:
            original_path = getattr(editor, "metadata", {}).get(
                "original_path"
            ) or getattr(editor, "change_data", {}).get("original_path")
            uri = Path(original_path).as_uri() if original_path else None
            self.lsp_client.update_outline_panel_from_uri(uri)
        else:
            self.lsp_client.update_outline_panel(editor if not is_diff else None)

        timeline_panel = self.main_window.timeline_panel
        if is_history_view:
            timeline_panel.details_view_button.setEnabled(True)
        else:
            timeline_panel.details_view_button.setEnabled(False)
            timeline_panel.list_view_button.setChecked(True)

    def _update_timeline_for_editor(self, editor):
        is_history_view = getattr(editor, "metadata", {}).get("is_history_view", False)
        if is_history_view:
            return

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

    def _populate_timeline_details(self, data: dict):
        current_file_path = self._get_current_timeline_file()
        if not current_file_path:
            return

        details = {}
        panel = self.main_window.timeline_panel

        if data["type"] == "save":
            details = {
                "full_path": data["path"],
                "filename": Path(current_file_path).name,
                "full_time": panel._format_timestamp(data["timestamp"], relative=False),
                "relative_time": panel._format_timestamp(
                    data["timestamp"], relative=True
                ),
                "additions": data["meta"].get("additions", "N/A"),
                "deletions": data["meta"].get("deletions", "N/A"),
            }
        elif data["type"] == "commit":
            details = {
                "full_path": current_file_path,
                "filename": Path(current_file_path).name,
                "full_time": panel._format_timestamp(data["timestamp"], relative=False),
                "relative_time": panel._format_timestamp(
                    data["timestamp"], relative=True
                ),
                "additions": "N/A",
                "deletions": "N/A",
            }

        if details:
            panel.show_details_view(details)

    @Slot(str)
    def on_welcome_action(self, action: str):
        if action == "open_folder":
            self.workspace_manager.open_workspace_dialog()
        elif action == "clone_repo":
            self.git_controller.on_clone_repo_requested()

    def _get_current_timeline_file(self):
        return self.main_window.timeline_panel.current_file_path

    @Slot(dict)
    def on_history_item_selected(self, data: dict):
        current_file_path = self._get_current_timeline_file()
        if not current_file_path:
            return

        try:
            current_content = Path(current_file_path).read_text(encoding="utf-8")
            historical_content = ""
            label = ""

            if data["type"] == "save":
                historical_content = self.history_manager.get_history_content(
                    data["path"]
                )
                ts = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(data["timestamp"] / 1000)
                )
                label = f"{Path(current_file_path).name} (Snapshot @ {ts})"
            elif data["type"] == "commit":
                original, modified = self.git_manager.get_commit_diff(
                    current_file_path, data["sha"]
                )
                historical_content = modified
                label = f"{Path(current_file_path).name} (@{data['sha'][:7]})"

            if historical_content is None:
                QMessageBox.critical(
                    self.main_window, "Error", "Could not load historical content."
                )
                return

            diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
            diff_widget.metadata = {
                "is_history_view": True,
                "original_path": current_file_path,
            }

            if data["type"] == "save":
                history_path = data["path"]
                diff_widget.set_primary_action("Restore This Version")
                diff_widget.primary_action_requested.connect(
                    lambda _, hp=history_path: self.on_history_restore_requested(hp)
                )

            modified_label = f"{Path(current_file_path).name} (Current)"
            diff_widget.set_diff_content(
                historical_content, current_content, label, modified_label
            )
            self.main_window.add_editor_tab(label, diff_widget)

            self._populate_timeline_details(data)
            self.main_window.timeline_panel.details_view_button.setChecked(True)

        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Failed to create diff view: {e}"
            )

    @Slot(str)
    def on_history_restore_requested(self, history_path: str):
        current_file_path = self._get_current_timeline_file()
        if not current_file_path:
            return

        reply = QMessageBox.question(
            self.main_window,
            "Restore Snapshot",
            f"This will overwrite the contents of '{Path(current_file_path).name}' with the selected snapshot. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            content = self.history_manager.get_history_content(history_path)
            if content is not None:
                try:
                    with open(current_file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    editor = self.file_manager.editors_by_path.get(current_file_path)
                    if editor:
                        uri = Path(current_file_path).as_uri()
                        lang_id = self.file_manager.get_language_id(current_file_path)
                        editor.set_content(content, lang_id, uri, lambda: None)
                except Exception as e:
                    QMessageBox.critical(
                        self.main_window, "Error", f"Could not restore file: {e}"
                    )

    @Slot(str)
    def on_history_delete_requested(self, history_path: str):
        self.history_manager.delete_snapshot(history_path)
        self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str)
    def on_history_delete_all_requested(self, file_path: str):
        self.history_manager.delete_all_snapshots(file_path)
        self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str, bool)
    def on_history_pin_toggled(self, history_path: str, is_pinned: bool):
        self.history_manager.update_snapshot_meta(history_path, {"pinned": is_pinned})
        self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str, str)
    def on_history_rename_requested(self, history_path: str, current_name: str):
        new_name, ok = QInputDialog.getText(
            self.main_window,
            "Rename Snapshot",
            "Enter new name:",
            text=current_name or "",
        )
        if ok:
            self.history_manager.update_snapshot_meta(history_path, {"name": new_name})
            self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str)
    def on_history_compare_with_current(self, history_path: str):
        snapshots = self.history_manager.get_history_for_file(
            self._get_current_timeline_file()
        )
        for path, meta in snapshots:
            if str(path) == history_path:
                self.on_history_item_selected(
                    {
                        "type": "save",
                        "path": history_path,
                        "timestamp": meta["timestamp"],
                    }
                )
                return

    @Slot(str)
    def on_history_show_contents_requested(self, history_path: str):
        current_file_path = self._get_current_timeline_file()
        if not current_file_path:
            return

        content = self.history_manager.get_history_content(history_path)
        if content is None:
            QMessageBox.critical(
                self.main_window, "Error", "Could not load historical content."
            )
            return

        editor = EditorWidget(self.theme_manager.get_current_theme_data())

        snapshots = self.history_manager.get_history_for_file(current_file_path)
        meta = next((m for p, m in snapshots if str(p) == history_path), {})
        ts = time.strftime("%H:%M:%S", time.localtime(meta.get("timestamp", 0) / 1000))
        label = f"{Path(current_file_path).name} (Snapshot @ {ts})"

        editor.metadata = {"is_history_view": True, "original_path": current_file_path}

        def on_editor_ready():
            editor.set_read_only(True)

        self.main_window.add_editor_tab(label, editor)
        uri = Path(history_path).as_uri()
        lang_id = self.file_manager.get_language_id(current_file_path)
        editor.set_content(content, lang_id, uri, on_editor_ready)

    @Slot(object, list)
    def on_discard_changes_requested(self, diff_widget, file_paths: list[str]):
        if not file_paths:
            return

        file_name = os.path.basename(file_paths[0])
        plural = "s" if len(file_paths) > 1 else ""
        message = (
            f"Are you sure you want to discard the change{plural} in '{file_name}'?"
        )
        if len(file_paths) > 1:
            message = (
                f"Are you sure you want to discard changes in {len(file_paths)} files?"
            )

        reply = QMessageBox.question(
            self.main_window,
            "Discard Changes",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.git_manager.discard_changes(file_paths)
            if diff_widget:
                index = self.main_window.tab_widget.indexOf(diff_widget)
                if index != -1:
                    self.main_window.tab_widget.removeTab(index)
