from PySide6.QtCore import QObject, Slot, QTimer, QTime, QMimeData
from PySide6.QtWidgets import (
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QWidget,
    QApplication,
)
from pathlib import Path

from forge.frontend.components.editor.editor_widget import EditorWidget
from forge.frontend.components.editor.diff_editor_widget import DiffEditorWidget
from forge.frontend.windows.clone_dialog import CloneDialog
from forge.backend.history.manager import HistoryManager
from forge.backend.git.manager import GitManager
from forge.frontend.controllers.lsp_client import LSPClient

AUTOSAVE_ENABLED = True
AUTOSAVE_DELAY_MS = 3000


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
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(AUTOSAVE_DELAY_MS)

        self.in_merge_conflict_mode = False

        self._connect_signals()
        self._initialize_ui_state()

    def _connect_signals(self):
        sc_panel = self.main_window.source_control_panel
        self.git_manager.repo_status_changed.connect(sc_panel.set_repo_status)
        self.git_manager.status_changed.connect(sc_panel.update_files)
        self.git_manager.status_changed.connect(
            self.on_git_status_changed_for_conflicts
        )
        self.git_manager.branch_changed.connect(
            self.main_window.git_branch_label.setText
        )
        self.git_manager.remote_status_changed.connect(
            self.on_git_remote_status_changed
        )
        self.git_manager.git_command_output.connect(
            lambda msg: self.main_window.log_to_output("Git", msg)
        )
        self.git_manager.upstream_branch_not_found.connect(
            self.on_upstream_branch_not_found
        )
        self.git_manager.merge_conflict_detected.connect(
            self.on_merge_conflict_detected
        )

        sc_panel.file_selected.connect(self.on_git_file_selected)
        sc_panel.discard_changes_requested.connect(self.on_git_discard_changes)
        sc_panel.stage_requested.connect(self.git_manager.stage_files)
        sc_panel.unstage_requested.connect(self.git_manager.unstage_files)
        sc_panel.stage_all_requested.connect(self.git_manager.stage_all_files)
        sc_panel.unstage_all_requested.connect(self.git_manager.unstage_all_files)
        sc_panel.commit_requested.connect(self.on_git_commit)
        sc_panel.commit_merge_requested.connect(self.on_git_commit_merge)
        sc_panel.stash_requested.connect(self.git_manager.stash_changes)
        sc_panel.initialize_repo_requested.connect(self.git_manager.initialize_repo)
        sc_panel.clone_repo_requested.connect(self.on_clone_repo_requested)
        sc_panel.abort_merge_requested.connect(self.on_abort_merge)

        self.main_window.welcome_screen.action_triggered.connect(self.on_welcome_action)
        self.main_window.welcome_file_explorer.clone_repo_button.clicked.connect(
            self.on_clone_repo_requested
        )

        self.main_window.git_refresh_button.clicked.connect(self.git_manager.fetch)
        self.main_window.git_pull_button.clicked.connect(self.git_manager.pull)
        self.main_window.git_push_button.clicked.connect(self.git_manager.push)

        self.main_window.conflicts_panel.file_selected.connect(
            self.on_conflict_file_selected
        )

        self.main_window.edit_menu.actions()[0].triggered.connect(self.undo)
        self.main_window.edit_menu.actions()[1].triggered.connect(self.redo)
        self.main_window.edit_menu.actions()[3].triggered.connect(self.cut)
        self.main_window.edit_menu.actions()[4].triggered.connect(self.copy)
        self.main_window.edit_menu.actions()[5].triggered.connect(self.paste)

        self.main_window.tab_widget.currentChanged.connect(self.on_tab_changed)

        self.workspace_manager.workspace_changed.connect(
            self.file_manager.set_workspace_path
        )
        self.workspace_manager.workspace_changed.connect(
            self.run_manager.set_workspace_path
        )
        self.workspace_manager.workspace_changed.connect(
            self.lsp_client.clear_lsp_manager
        )
        self.workspace_manager.workspace_changed.connect(
            self.history_manager.set_workspace_path
        )
        self.workspace_manager.workspace_changed.connect(
            self.git_manager.set_workspace_path
        )
        self.workspace_manager.lsp_manager_created.connect(
            self.lsp_client.set_lsp_manager
        )

        self.file_manager.file_opened.connect(self.on_editor_opened)
        self.file_manager.file_closed.connect(self.on_file_closed)
        self.file_manager.file_modified.connect(self.on_file_modified)
        self.file_manager.file_saved.connect(self.history_manager.record_save)
        self.file_manager.file_saved.connect(self.on_file_saved)

        self.autosave_timer.timeout.connect(self.trigger_autosave)

        timeline = self.main_window.timeline_panel
        timeline.history_item_selected.connect(self.on_history_item_selected)
        timeline.restore_requested.connect(self.on_restore_requested)
        timeline.delete_requested.connect(self.on_delete_requested)
        timeline.pin_toggled.connect(self.on_pin_toggled)
        timeline.rename_requested.connect(self.on_rename_requested)
        timeline.compare_with_requested.connect(self.on_compare_with_requested)
        timeline.show_contents_requested.connect(self.on_show_contents_requested)

        self.theme_manager.theme_changed.connect(self.on_theme_changed)

    def _enter_merge_mode(self, conflicted_files: list):
        if self.in_merge_conflict_mode:
            return
        self.in_merge_conflict_mode = True

        self.main_window.conflicts_panel.update_conflicts(conflicted_files)
        self.main_window.source_control_panel.enter_merge_mode(conflicted_files)
        self.main_window.file_explorer_dock.setVisible(False)
        self.main_window.timeline_dock.setVisible(False)

        self.main_window.conflicts_dock.setVisible(True)
        self.main_window.conflicts_dock.raise_()

    def _exit_merge_mode(self):
        if not self.in_merge_conflict_mode:
            return
        self.in_merge_conflict_mode = False

        for i in range(self.main_window.tab_widget.count()):
            editor = self.main_window.tab_widget.widget(i)
            if isinstance(editor, EditorWidget) and editor.property("is_merge_editor"):
                editor.exit_merge_mode()
                editor.setProperty("is_merge_editor", False)

        self.main_window.source_control_panel.exit_merge_mode()
        self.main_window.conflicts_dock.setVisible(False)
        self.main_window.file_explorer_dock.setVisible(True)
        self.main_window.timeline_dock.setVisible(True)
        self.main_window.file_explorer_dock.raise_()
        self.git_manager.refresh_status()

    @Slot(list)
    def on_merge_conflict_detected(self, conflicted_files: list):
        self._enter_merge_mode(conflicted_files)

    @Slot(list, list)
    def on_git_status_changed_for_conflicts(self, staged: list, unstaged: list):
        """Updates the dedicated conflicts panel when in merge mode."""
        if self.in_merge_conflict_mode:

            self.main_window.conflicts_panel.update_conflicts(unstaged)

    def on_abort_merge(self):
        self.git_manager.abort_merge()
        self._exit_merge_mode()

    @Slot()
    def on_clone_repo_requested(self):
        dialog = CloneDialog(self.main_window)
        self.clone_dialog = dialog

        dialog.clone_requested.connect(self.git_manager.clone_repo)
        self.git_manager.clone_progress.connect(dialog.update_progress)
        self.git_manager.clone_finished.connect(self.on_clone_finished)
        self.git_manager.clone_finished.connect(dialog.on_clone_finished)

        dialog.exec()

        try:
            self.git_manager.clone_progress.disconnect(dialog.update_progress)
            self.git_manager.clone_finished.disconnect(self.on_clone_finished)
            self.git_manager.clone_finished.disconnect(dialog.on_clone_finished)
        except RuntimeError:
            pass

    @Slot(bool, str)
    def on_clone_finished(self, success: bool, path_or_error: str):
        if success:
            self.workspace_manager.set_workspace(path_or_error)

    @Slot(str)
    def on_welcome_action(self, action: str):
        if action == "open_folder":
            self.workspace_manager.open_workspace_dialog()
        elif action == "clone_repo":
            self.on_clone_repo_requested()

    def on_editor_opened(self, uri, lang_id, content, editor):
        if self.in_merge_conflict_mode:
            editor.setProperty("is_merge_editor", True)
            editor.enter_merge_mode()
            editor.mark_as_resolved_requested.connect(self.on_mark_as_resolved)
            editor.all_conflicts_resolved.connect(self.on_all_conflicts_resolved)
            self.update_outline_for_conflict_editor(editor)
        else:
            self.lsp_client.on_file_opened(uri, lang_id, content, editor)
            editor.bridge.stage_lines_requested.connect(self.on_stage_lines)
            editor.bridge.apply_staged_changes_requested.connect(
                lambda e=editor: self.on_apply_staged_changes(e)
            )

    def on_file_closed(self, uri: str):
        self.lsp_client.on_file_closed(uri)
        if self.in_merge_conflict_mode:
            self.git_manager.refresh_status()

    @Slot(EditorWidget)
    def on_all_conflicts_resolved(self, editor: EditorWidget):
        """Called automatically from JS when an action resolves the last conflict."""
        self._on_get_text_for_resolve(editor)

    @Slot(EditorWidget)
    def on_mark_as_resolved(self, editor: EditorWidget):
        """Called manually by the user clicking the button."""

        def proceed_to_resolve():
            self._on_get_text_for_resolve(editor)

        def on_check_complete(has_conflicts):
            if has_conflicts:
                reply = QMessageBox.question(
                    self.main_window,
                    "Conflicts Remain",
                    "This file still contains conflict markers.\nAre you sure you want to mark it as resolved?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    proceed_to_resolve()
            else:
                proceed_to_resolve()

        editor.check_for_conflicts(on_check_complete)

    def _on_get_text_for_resolve(self, editor: EditorWidget):
        path = self.file_manager.open_file_paths.get(editor)
        if not path:
            return

        def save_and_stage(content: str):
            if content is None:
                return

            relative_path = str(
                Path(path).relative_to(self.git_manager.repo.working_dir)
            )
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.git_manager.stage_files([relative_path])
                self.file_manager.close_tab_by_path(path)
            except Exception as e:
                self.git_manager._log(f"Error saving resolved file: {e}")

        editor.get_text(save_and_stage)

    @Slot(str)
    def on_stage_lines(self, selected_text: str):
        clipboard = QApplication.clipboard()
        mime_data = QMimeData()
        mime_data.setText(selected_text)
        mime_data.setData("application/x-forge-hunk", b"1")
        clipboard.setMimeData(mime_data)
        print("[Controller] Staged lines to clipboard.")

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
        print("[Controller] Applied staged changes.")

    def undo(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.bridge.undo_requested.emit()

    def redo(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.bridge.redo_requested.emit()

    def cut(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.bridge.cut_requested.emit()

    def copy(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.bridge.copy_requested.emit()

    def paste(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.bridge.paste_requested.emit()

    @Slot(object)
    def on_restore_requested(self, diff_widget: QWidget):
        history_path_str = getattr(diff_widget, "history_path_str", None)
        current_path_str = getattr(diff_widget, "current_path_str", None)
        if not history_path_str or not current_path_str:
            return
        reply = QMessageBox.question(
            self.main_window,
            "Confirm Restore",
            "Are you sure you want to restore this version?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        history_content = self.history_manager.get_history_content(history_path_str)
        if history_content is None:
            return
        editor = self.file_manager.editors_by_path.get(current_path_str)

        def on_restore_complete():
            if editor:
                editor_index = self.main_window.tab_widget.indexOf(editor)
                if editor_index != -1:
                    self.main_window.tab_widget.setCurrentIndex(editor_index)
            diff_index = self.main_window.tab_widget.indexOf(diff_widget)
            if diff_index != -1:
                self.main_window.tab_widget.removeTab(diff_index)
            if editor:
                self.file_manager.mark_file_clean(editor)

        def on_content_set_and_saved():
            self.file_manager.save_file(editor)
            on_restore_complete()

        if editor:
            uri = Path(current_path_str).as_uri()
            lang_id = self.file_manager.get_language_id(current_path_str)
            editor.set_content(history_content, lang_id, uri, on_content_set_and_saved)
        else:
            with open(current_path_str, "w", encoding="utf-8") as f:
                f.write(history_content)
            on_restore_complete()

    def _initialize_ui_state(self):
        if not AUTOSAVE_ENABLED:
            self.main_window.autosave_status_label.setText("Autosave Disabled")

    def shutdown(self):
        self.workspace_manager.shutdown_lsp()

    @Slot(int)
    def on_tab_changed(self, index: int):
        editor = self.main_window.tab_widget.widget(index)
        self._update_ui_for_editor(editor)
        self._update_timeline_for_editor(editor)

    def _update_ui_for_editor(self, editor):
        is_merge_editor = editor and editor.property("is_merge_editor")
        if self.in_merge_conflict_mode or is_merge_editor:
            self.run_manager.update_run_actions_state(None)
            if is_merge_editor:
                self.update_outline_for_conflict_editor(editor)
            else:
                self.main_window.outline_panel.clear_symbols()
            self.main_window.lsp_status_label.setText("LSP: Disabled (Merge)")
            return
        is_diff = isinstance(editor, DiffEditorWidget)
        is_readonly_history = getattr(editor, "metadata", {}).get(
            "is_history_view", False
        )
        is_special_view = is_diff or is_readonly_history
        self.run_manager.update_run_actions_state(None if is_special_view else editor)
        self.lsp_client.update_outline_panel(None if is_special_view else editor)
        if is_special_view:
            self.main_window.lsp_status_label.setText("LSP: Disabled")
        else:
            lang_id = None
            if isinstance(editor, EditorWidget):
                path = self.file_manager.open_file_paths.get(editor)
                if path:
                    lang_id = self.file_manager.get_language_id(path)
            if self.lsp_client.is_lsp_ready:
                self.main_window.lsp_status_label.setText(
                    "LSP: Disabled" if lang_id != "python" else "LSP: Ready"
                )

    def _update_timeline_for_editor(self, editor):
        if self.in_merge_conflict_mode:
            self.main_window.timeline_panel.clear_view()
            return

        if editor is None:
            self.main_window.timeline_panel.clear_view()
            return
        editor_metadata = getattr(editor, "metadata", {})
        if editor_metadata.get("is_history_view"):
            self.main_window.timeline_panel.show_details_view(
                editor_metadata["history_details"]
            )
            return
        if isinstance(editor, DiffEditorWidget):
            self.main_window.timeline_panel.details_view_button.setChecked(True)
            return
        if editor in self.file_manager.open_file_paths:
            file_path = self.file_manager.open_file_paths.get(editor)
            if file_path:
                history = self.history_manager.get_history_for_file(file_path)
                self.main_window.timeline_panel.show_list_view(file_path, history)
            else:
                self.main_window.timeline_panel.clear_view()
        else:
            self.main_window.timeline_panel.clear_view()

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

    @Slot(str, str)
    def on_history_item_selected(self, current_path_str: str, history_path_str: str):
        try:
            current_content = Path(current_path_str).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not read current file: {e}"
            )
            return
        history_content = self.history_manager.get_history_content(history_path_str)
        if history_content is None:
            return
        diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
        diff_widget.history_path_str = history_path_str
        diff_widget.current_path_str = current_path_str
        diff_widget.primary_action_requested.connect(self.on_restore_requested)
        diff_widget.set_primary_action("Restore This Version")
        diff_widget.stage_lines_requested.connect(self.on_stage_lines)
        history_path, current_path = Path(history_path_str), Path(current_path_str)
        timeline = self.main_window.timeline_panel
        history_entries = self.history_manager.get_history_for_file(current_path_str)
        meta = next((m for p, m in history_entries if str(p) == history_path_str), {})
        relative_time, full_time = timeline._format_timestamp(
            meta["timestamp"]
        ), timeline._format_timestamp(meta["timestamp"], relative=False)
        original_label = f"Historical ({relative_time})"
        modified_label = f"Current ({current_path.name})"
        diff_widget.set_diff_content(
            history_content, current_content, original_label, modified_label
        )
        details = {
            "filename": current_path.name,
            "full_time": full_time,
            "relative_time": relative_time,
            "full_path": history_path_str,
            "additions": meta.get("additions", 0),
            "deletions": meta.get("deletions", 0),
        }
        timeline.show_details_view(details)
        self.main_window.add_editor_tab(f"{current_path.name} (diff)", diff_widget)

    @Slot(str)
    def on_delete_requested(self, history_path_str: str):
        reply = QMessageBox.question(
            self.main_window, "Confirm Delete", "Permanently delete this snapshot?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_manager.delete_snapshot(history_path_str)
            self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str, bool)
    def on_pin_toggled(self, history_path_str: str, is_pinned: bool):
        self.history_manager.update_snapshot_meta(
            history_path_str, {"pinned": is_pinned}
        )
        self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str, str)
    def on_rename_requested(self, history_path_str: str, old_name: str):
        new_name, ok = QInputDialog.getText(
            self.main_window, "Rename Snapshot", "Enter name:", text=(old_name or "")
        )
        if ok and new_name:
            self.history_manager.update_snapshot_meta(
                history_path_str, {"name": new_name}
            )
            self._update_timeline_for_editor(self.main_window.get_current_editor())

    @Slot(str)
    def on_compare_with_requested(self, history_path_str: str):
        other_file, _ = QFileDialog.getOpenFileName(self.main_window, "Compare With...")
        if not other_file:
            return
        history_content = self.history_manager.get_history_content(history_path_str)
        other_content = Path(other_file).read_text(encoding="utf-8")
        diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
        diff_widget.set_diff_content(
            history_content,
            other_content,
            f"{Path(history_path_str).name} (History)",
            Path(other_file).name,
        )
        self.main_window.add_editor_tab("Compare", diff_widget)

    @Slot(str)
    def on_show_contents_requested(self, history_path_str: str):
        history_content = self.history_manager.get_history_content(history_path_str)
        if history_content is None:
            return
        editor = (
            EditorWidget(self.theme_manager.get_current_theme_data())
            if not self.file_manager.editor_cache
            else self.file_manager.editor_cache.pop()
        )
        if not hasattr(editor, "theme_data"):
            editor.theme_data = self.theme_manager.get_current_theme_data()
        history_path = Path(history_path_str)
        lang_id = self.file_manager.get_language_id(history_path.name)
        original_path = self.main_window.timeline_panel.current_file_path
        history_entries = self.history_manager.get_history_for_file(original_path)
        meta = next((m for p, m in history_entries if str(p) == history_path_str), {})
        relative_time, full_time = self.main_window.timeline_panel._format_timestamp(
            meta["timestamp"]
        ), self.main_window.timeline_panel._format_timestamp(
            meta["timestamp"], relative=False
        )
        editor.metadata = {
            "is_history_view": True,
            "original_path": original_path,
            "history_details": {
                "filename": Path(original_path).name,
                "full_time": full_time,
                "relative_time": relative_time,
                "full_path": history_path_str,
                "additions": meta.get("additions", 0),
                "deletions": meta.get("deletions", 0),
            },
        }
        fake_uri = f"history://{history_path_str}"

        def on_content_set():
            editor.set_read_only(True)

        editor.set_content(history_content, lang_id, fake_uri, on_content_set)
        self.main_window.add_editor_tab(
            f"{Path(original_path).name} (Read-only)", editor
        )

    @Slot(str, str)
    def on_git_file_selected(self, file_path_str: str, status: str):
        if not self.git_manager.repo:
            return
        workspace_path = Path(self.git_manager.repo.working_dir)
        full_path = workspace_path / file_path_str

        if self.in_merge_conflict_mode and status == "U":
            self.file_manager.open_file_from_path(str(full_path))
            return

        original_content = ""
        if status in ["A", "U"] and not self.in_merge_conflict_mode:
            original_content = ""
        else:
            original_content = self.git_manager.get_head_content(file_path_str)

        if original_content is None:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not get HEAD content for {file_path_str}",
            )
            return

        try:
            modified_content = (
                "" if status == "D" else full_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not read current file: {e}"
            )
            return

        diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
        diff_widget.set_primary_action("Discard Changes", False)
        original_label = f"{Path(file_path_str).name} (HEAD)"
        modified_label = f"{Path(file_path_str).name} (Workspace)"
        diff_widget.set_diff_content(
            original_content, modified_content, original_label, modified_label
        )
        self.main_window.add_editor_tab(
            f"{Path(file_path_str).name} (diff)", diff_widget
        )

    @Slot(list)
    def on_git_discard_changes(self, file_paths: list[str]):
        file_list = "\n - ".join(Path(p).name for p in file_paths)
        reply = QMessageBox.question(
            self.main_window,
            "Discard Changes",
            f"Are you sure you want to discard changes to the following files?\n - {file_list}\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for file_path in file_paths:
                self.git_manager.discard_changes(file_path)

    @Slot(str, bool)
    def on_git_commit(self, message: str, stage_all: bool):
        self.git_manager.commit(message, stage_all)

    @Slot(str)
    def on_git_commit_merge(self, message: str):
        self.on_git_commit(message, stage_all=False)
        self._exit_merge_mode()

    @Slot(int, int)
    def on_git_remote_status_changed(self, ahead: int, behind: int):
        if ahead == 0 and behind == 0:
            self.main_window.git_remote_status_label.setText("")
        else:
            self.main_window.git_remote_status_label.setText(f" ↑{ahead} ↓{behind}")

    @Slot()
    def on_upstream_branch_not_found(self):
        branch_name = self.git_manager.current_branch
        reply = QMessageBox.question(
            self.main_window,
            "Publish Branch",
            f"The branch '{branch_name}' has no upstream branch.\n\nDo you want to publish this branch and set the remote as its upstream?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.git_manager.push_and_set_upstream()

    @Slot(dict)
    def on_theme_changed(self, theme_data: dict):
        for i in range(self.main_window.tab_widget.count()):
            widget = self.main_window.tab_widget.widget(i)
            if hasattr(widget, "apply_theme") and callable(widget.apply_theme):
                widget.apply_theme(theme_data)
        for editor in self.file_manager.editor_cache:
            if hasattr(editor, "apply_theme") and callable(editor.apply_theme):
                editor.apply_theme(theme_data)
        if self.main_window._preloaded_editor and hasattr(
            self.main_window._preloaded_editor, "apply_theme"
        ):
            self.main_window._preloaded_editor.apply_theme(theme_data)

    @Slot(str)
    def on_conflict_file_selected(self, relative_path: str):
        if not self.git_manager.repo:
            return
        full_path = Path(self.git_manager.repo.working_dir) / relative_path
        self.file_manager.open_file_from_path(str(full_path))

    def update_outline_for_conflict_editor(self, editor: EditorWidget):
        def on_text_received(content: str):
            if content is None:
                self.main_window.outline_panel.clear_symbols()
                return
            lines = content.splitlines()
            hunks = []
            for i, line in enumerate(lines):
                if line.startswith("<<<<<<<"):
                    hunks.append({"name": "Conflict Block", "line": i + 1, "char": 0})
            self.main_window.outline_panel.update_from_hunks(hunks)

        editor.get_text(on_text_received)
