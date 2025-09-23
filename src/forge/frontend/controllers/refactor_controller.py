from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import (
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QApplication,
    QMenu,
)
from PySide6.QtGui import QAction, QCursor
from pathlib import Path
import os
from collections import defaultdict
import time
import tempfile

from forge.backend.tools.tool_registry import ToolRegistry
from forge.frontend.components.editor.diff_editor_widget import DiffEditorWidget
from forge.frontend.windows.tool_confirmation_dialog import ToolConfirmationDialog
from forge.frontend.windows.create_branch_dialog import CreateBranchDialog
from forge.frontend.windows.find_replace_dialog import FindReplaceDialog
from forge.frontend.controllers.lsp_client import uri_to_path


class RefactorController(QObject):
    def __init__(
        self, main_window, workspace_manager, file_manager, theme_manager, lsp_client
    ):
        super().__init__(main_window)
        self.main_window = main_window
        self.workspace_manager = workspace_manager
        self.file_manager = file_manager
        self.theme_manager = theme_manager
        self.lsp_client = lsp_client

        self.refactor_manager = None
        self.git_manager = None

        self.tool_registry = ToolRegistry()
        self.in_review_mode = False
        self.review_session_data = {}

        self._setup_dynamic_menus()

    def set_managers(self, refactor_manager, git_manager):
        self.refactor_manager = refactor_manager
        self.git_manager = git_manager

    def init_connections(self):
        self.lsp_client.rename_response_received.connect(self.on_rename_response)

        self.refactor_manager.review_session_started.connect(
            self.on_review_session_started
        )
        self.refactor_manager.log_message.connect(
            lambda msg: self.main_window.log_to_output(
                "Refactor", msg, raise_panel=True
            )
        )

        self.main_window.file_explorer.refactor_requested.connect(
            self.on_file_explorer_refactor
        )

        review_panel = self.main_window.review_panel
        review_panel.accept_all_requested.connect(self.on_accept_all_review_changes)
        review_panel.discard_all_requested.connect(self.on_discard_all_review_changes)
        review_panel.export_to_branch_requested.connect(self.on_export_review_to_branch)
        review_panel.file_selected.connect(self.on_review_file_selected)
        review_panel.accept_file_requested.connect(self.on_review_accept_one_file)
        review_panel.discard_file_requested.connect(self.on_review_discard_one_file)
        review_panel.save_as_snapshot_requested.connect(self.on_review_save_as_snapshot)
        review_panel.save_as_requested.connect(self.on_review_save_as)

        self.main_window.review_toolbar.finish_review_requested.connect(
            self.on_finish_review
        )
        self.main_window.review_placeholder.refactor_button.clicked.connect(
            lambda: self.main_window.refactor_menu.exec(QCursor.pos())
        )

    def _setup_dynamic_menus(self):
        menu = self.main_window.refactor_menu
        menu.clear()
        tools = self.tool_registry.get_all_tools()

        def populate_menu_for_scope(parent_menu, scope_name, suffix):
            categories = defaultdict(list)
            top_level_tools = []

            for tool in tools:
                if scope_name in tool["scopes"]:
                    category = tool.get("category")
                    if category:
                        categories[category].append(tool)
                    else:
                        top_level_tools.append(tool)

            for tool in sorted(top_level_tools, key=lambda x: x.get("order", 99)):
                action = QAction(f"{tool['name']} on {suffix}...", self)
                action.triggered.connect(
                    lambda checked=False, tool_id=tool[
                        "id"
                    ]: self.on_refactor_action_triggered(tool_id, scope_name)
                )
                parent_menu.addAction(action)

            if top_level_tools and categories:
                parent_menu.addSeparator()

            for category_name, cat_tools in sorted(categories.items()):
                submenu = parent_menu.addMenu(f"{category_name} on {suffix}")
                for tool in sorted(cat_tools, key=lambda x: x.get("order", 99)):
                    action = QAction(f"{tool['name']}", self)
                    action.triggered.connect(
                        lambda checked=False, tool_id=tool[
                            "id"
                        ]: self.on_refactor_action_triggered(tool_id, scope_name)
                    )
                    submenu.addAction(action)

        populate_menu_for_scope(menu, "file", "File")
        menu.addSeparator()
        populate_menu_for_scope(menu, "workspace", "Workspace")

        self.main_window.file_explorer.set_refactor_tools(tools)

    def _get_current_file_for_refactor(self):
        editor = self.main_window.get_current_editor()
        if not editor:
            return None
        file_path = self.file_manager.open_file_paths.get(editor)
        if not file_path or not file_path.endswith(".py"):
            return None
        if self.file_manager.is_dirty(editor):
            reply = QMessageBox.question(
                self.main_window,
                "Save Changes",
                "You must save the file before this action. Save now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.file_manager.save_file(editor)
            else:
                return None
        return file_path

    @Slot(str, str)
    def on_refactor_action_triggered(self, tool_id: str, scope: str):
        path = None
        if scope == "file":
            path = self._get_current_file_for_refactor()
            if not path:
                QMessageBox.information(
                    self.main_window,
                    "No File",
                    "Please open a Python file to refactor.",
                )
                return
        elif scope == "workspace":
            path = self.workspace_manager.workspace_path

        if not path:
            return
        tool = self.tool_registry.get_tool(tool_id)
        if tool:
            self.on_path_refactor_requested(path, tool)

    @Slot(str, str)
    def on_file_explorer_refactor(self, tool_id: str, path: str):
        tool = self.tool_registry.get_tool(tool_id)
        if tool:
            self.on_path_refactor_requested(path, tool)

    def on_path_refactor_requested(self, path: str, tool: dict):
        if not path:
            return

        is_dir = Path(path).is_dir()
        target_name = (
            "the entire workspace"
            if is_dir and path == self.workspace_manager.workspace_path
            else f"'{Path(path).name}'"
        )

        tool_kwargs = {}
        if tool["handler_type"] == "programmatic_with_dialog":
            if tool["id"] == "find_replace":
                dialog = FindReplaceDialog(target_name, self.main_window)
                if not dialog.exec():
                    return
                tool_kwargs = dialog.params
        else:
            dialog = ToolConfirmationDialog(
                tool, target_name, self.theme_manager, self.main_window
            )
            if not dialog.exec():
                return

        self.main_window.log_to_output("Refactor", "", clear=True, raise_panel=True)
        self.refactor_manager.run_tool_on_path(path, tool, tool_kwargs)

    @Slot(dict)
    def on_review_session_started(self, session_data):
        if session_data.get("error"):
            QMessageBox.critical(
                self.main_window,
                "Refactor Error",
                f"An error occurred: {session_data['error']}",
            )
            return
        if not session_data.get("changes"):
            QMessageBox.information(
                self.main_window,
                "No Changes",
                "The selected tools made no changes to the file(s).",
            )
            if session_data.get("session_dir"):
                self.refactor_manager.cleanup_session(session_data["session_dir"])
            return

        self.review_session_data = session_data
        self.enter_review_mode()

    def enter_review_mode(self):
        if self.in_review_mode:
            return
        self.in_review_mode = True
        self.main_window.setWindowTitle(
            f"Forge - {os.path.basename(self.workspace_manager.workspace_path)} [Reviewing Changes]"
        )
        self.main_window.corner_stack.setCurrentWidget(self.main_window.review_toolbar)

        num_files = len(self.review_session_data["changes"])
        summary = f"Refactoring tools have proposed changes for {num_files} file(s)."
        self.main_window.review_panel.set_summary_text(summary)
        self.main_window.review_panel.update_changes(
            self.review_session_data["changes"]
        )

        self.main_window.enter_review_mode()

    def exit_review_mode(self):
        if not self.in_review_mode:
            return
        for i in reversed(range(self.main_window.tab_widget.count())):
            widget = self.main_window.tab_widget.widget(i)
            if isinstance(widget, DiffEditorWidget) and getattr(
                widget, "is_review_diff", False
            ):
                self.main_window.tab_widget.removeTab(i)

        if self.review_session_data.get("session_dir"):
            self.refactor_manager.cleanup_session(
                self.review_session_data["session_dir"]
            )

        self.in_review_mode = False
        self.review_session_data = {}
        self.main_window.setWindowTitle(
            f"Forge - {os.path.basename(self.workspace_manager.workspace_path)}"
        )
        self.main_window.corner_stack.setCurrentWidget(
            self.main_window.normal_corner_widget
        )

        self.main_window.exit_review_mode()
        self.git_manager.refresh_status()

    @Slot()
    def on_finish_review(self):
        if self.review_session_data.get("changes"):
            reply = QMessageBox.question(
                self.main_window,
                "Finish Review",
                "You have unhandled changes. Are you sure you want to finish and discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self.exit_review_mode()

    @Slot(dict)
    def on_review_file_selected(self, change_data):
        for i in range(self.main_window.tab_widget.count()):
            widget = self.main_window.tab_widget.widget(i)
            if (
                getattr(widget, "is_review_diff", False)
                and getattr(widget, "change_data", {}) == change_data
            ):
                self.main_window.tab_widget.setCurrentWidget(widget)
                return

        diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
        diff_widget.is_review_diff = True
        diff_widget.change_data = change_data
        diff_widget.enter_review_mode()
        diff_widget.accept_file_requested.connect(self.on_accept_review_change)
        diff_widget.discard_file_requested.connect(self.on_discard_review_change)
        original_path = change_data["original_path"]
        original_label = f"{Path(original_path).name} (Original)"
        modified_label = f"{Path(original_path).name} (Proposed Changes)"
        diff_widget.set_diff_content(
            change_data["original_content"],
            change_data["modified_content"],
            original_label,
            modified_label,
        )
        self.main_window.add_editor_tab(original_path, diff_widget)

    def _handle_review_action(self, diff_widget, is_accept: bool):
        change_data = getattr(diff_widget, "change_data", None)
        if not change_data:
            return

        original_path = change_data["original_path"]

        if is_accept:
            self.refactor_manager.accept_changes(change_data)
        else:
            self.refactor_manager.discard_changes(change_data)

        self.review_session_data["changes"].pop(original_path, None)
        self.main_window.review_panel.remove_file(original_path)

        index = self.main_window.tab_widget.indexOf(diff_widget)
        if index != -1:
            self.main_window.tab_widget.removeTab(index)

        next_file_data = self.main_window.review_panel.get_next_file_data(original_path)
        if next_file_data:
            self.on_review_file_selected(next_file_data)
        elif not self.review_session_data.get("changes"):
            QMessageBox.information(
                self.main_window,
                "Review Complete",
                "All proposed changes have been handled.",
            )
            self.main_window.review_panel.set_summary_text(
                "All changes have been handled."
            )

    @Slot(object)
    def on_accept_review_change(self, diff_widget):
        self._handle_review_action(diff_widget, is_accept=True)

    @Slot(object)
    def on_discard_review_change(self, diff_widget):
        self._handle_review_action(diff_widget, is_accept=False)

    @Slot(dict)
    def on_review_accept_one_file(self, change_data):
        self.refactor_manager.accept_changes(change_data)
        original_path = change_data["original_path"]
        self.review_session_data["changes"].pop(original_path, None)
        self.main_window.review_panel.remove_file(original_path)

    @Slot(dict)
    def on_review_discard_one_file(self, change_data):
        self.refactor_manager.discard_changes(change_data)
        original_path = change_data["original_path"]
        self.review_session_data["changes"].pop(original_path, None)
        self.main_window.review_panel.remove_file(original_path)

    @Slot(dict)
    def on_review_save_as_snapshot(self, change_data):
        name, ok = QInputDialog.getText(
            self.main_window,
            "Save Snapshot",
            "Enter an optional name for this snapshot:",
        )
        if ok:
            metadata = {
                "name": name if name else "From Refactor Review",
                "pinned": True,
                "source": "Refactor Review",
            }
            self.main_window.history_manager.record_snapshot_from_content(
                change_data["original_path"], change_data["modified_content"], metadata
            )
            QMessageBox.information(
                self.main_window,
                "Snapshot Saved",
                f"The proposed changes have been saved to the timeline for '{Path(change_data['original_path']).name}'.",
            )

    @Slot(dict)
    def on_review_save_as(self, change_data):
        original_path = Path(change_data["original_path"])
        save_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Proposed Changes As...",
            str(
                original_path.parent
                / f"{original_path.stem}_modified{original_path.suffix}"
            ),
        )
        if save_path:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(change_data["modified_content"])
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not save file: {e}"
                )

    @Slot()
    def on_accept_all_review_changes(self):

        if not self.review_session_data or "changes" not in self.review_session_data:
            self.exit_review_mode()
            return

        for file_path, change_data in list(self.review_session_data["changes"].items()):
            self.refactor_manager.accept_changes(change_data)
        QMessageBox.information(
            self.main_window,
            "Review Complete",
            "All proposed changes have been accepted.",
        )
        self.exit_review_mode()

    @Slot()
    def on_discard_all_review_changes(self):
        reply = QMessageBox.question(
            self.main_window,
            "Discard All",
            "Are you sure you want to discard all proposed changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.exit_review_mode()

    @Slot()
    def on_export_review_to_branch(self):
        title = "Export Changes to New Branch"
        explanation = "This will create a new branch from your current one, apply all proposed changes, and commit them. This is a safe way to review changes later or create a pull request."
        ok_text = "Create Branch & Commit"
        dialog = CreateBranchDialog(
            [
                b[0]
                for b in self.main_window.controller.git_controller.branch_data_cache.get(
                    "local", []
                )
            ],
            self.main_window.controller.git_controller.current_branch_cache,
            self.main_window,
            title=title,
            explanation=explanation,
            ok_button_text=ok_text,
        )
        dialog.create_branch_requested.connect(self._commit_review_to_new_branch)
        dialog.exec()

    @Slot(str, str)
    def _commit_review_to_new_branch(self, new_branch_name, base_branch):
        original_branch = (
            self.main_window.controller.git_controller.current_branch_cache
        )
        try:
            self.git_manager.create_branch(new_branch_name, base_branch)
            QApplication.processEvents()

            changed_files_rel = []
            for change_data in self.review_session_data["changes"].values():
                self.refactor_manager.accept_changes(change_data)
                rel_path = os.path.relpath(
                    change_data["original_path"], self.workspace_manager.workspace_path
                )
                changed_files_rel.append(rel_path)

            self.git_manager.stage_files(changed_files_rel)
            self.git_manager.commit(
                f"Automated refactoring via Forge tools", stage_all=False
            )

            QMessageBox.information(
                self.main_window,
                "Export Successful",
                f"Changes have been committed to the new branch '{new_branch_name}'.\nYou have been switched back to your original branch '{original_branch}'.",
            )
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Export Failed", f"An error occurred: {e}"
            )
        finally:
            self.git_manager.checkout_branch(original_branch)
            self.exit_review_mode()

    @Slot(dict)
    def on_rename_response(self, workspace_edit: dict):
        changes = workspace_edit.get("changes", {})
        if not changes:
            QMessageBox.information(
                self.main_window,
                "Rename Symbol",
                "Could not determine changes for rename operation.",
            )
            return

        self.refactor_manager.log_message.emit(
            "[Forge Refactor] Received rename data from LSP. Building review session..."
        )

        session_dir = Path(tempfile.gettempdir()) / f"forge_review_{int(time.time())}"
        session_dir.mkdir(parents=True, exist_ok=True)

        session_changes = {}

        for uri, text_edits in changes.items():
            try:
                original_path = uri_to_path(uri)
                original_content = original_path.read_text(encoding="utf-8")

                edits = sorted(
                    text_edits, key=lambda x: x["range"]["start"]["line"], reverse=True
                )
                lines = original_content.splitlines(True)

                for edit in edits:
                    start_line, start_col = (
                        edit["range"]["start"]["line"],
                        edit["range"]["start"]["character"],
                    )
                    end_line, end_col = (
                        edit["range"]["end"]["line"],
                        edit["range"]["end"]["character"],
                    )

                    if start_line == end_line:
                        line_content = lines[start_line]
                        lines[start_line] = (
                            line_content[:start_col]
                            + edit["newText"]
                            + line_content[end_col:]
                        )
                    else:
                        lines = (
                            lines[:start_line]
                            + [edit["newText"]]
                            + lines[end_line + 1 :]
                        )

                modified_content = "".join(lines)

                temp_path = session_dir / original_path.name
                temp_path.write_text(modified_content, encoding="utf-8")

                session_changes[str(original_path)] = {
                    "original_path": str(original_path),
                    "temp_path": str(temp_path),
                    "original_content": original_content,
                    "modified_content": modified_content,
                    "summaries": ["Renamed symbol"],
                }
            except Exception as e:
                self.refactor_manager.log_message.emit(
                    f"[Forge Refactor] ERROR processing rename for {uri}: {e}"
                )

        final_session_data = {
            "session_dir": str(session_dir),
            "changes": session_changes,
        }
        self.on_review_session_started(final_session_data)
