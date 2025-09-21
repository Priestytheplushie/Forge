import os
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog, QWidget
from PySide6.QtCore import QObject, Slot, Signal
from ..components.editor.editor_widget import EditorWidget
from ..components.editor.diff_editor_widget import DiffEditorWidget


class FileManager(QObject):
    """Manages all file I/O operations and editor state."""

    file_opened = Signal(str, str, str, EditorWidget)
    file_closed = Signal(str)
    file_modified = Signal(EditorWidget)
    file_saved = Signal(str, str)

    def __init__(self, main_window, theme_manager):
        super().__init__(main_window)
        self.main_window = main_window
        self.theme_manager = theme_manager
        self.workspace_path = None

        self.open_file_paths = {}
        self.editors_by_path = {}
        self.editor_cache = []
        self.dirty_editors = set()

        self._connect_signals()

    def _connect_signals(self):
        self.main_window.file_menu.actions()[2].triggered.connect(self.open_file_dialog)
        self.main_window.file_menu.actions()[3].triggered.connect(self.save_file)
        self.main_window.file_menu.actions()[4].triggered.connect(self.save_file_as)
        self.main_window.file_explorer.file_double_clicked.connect(
            self.open_file_from_path
        )
        self.main_window.file_explorer.new_file_requested.connect(self.handle_new_file)
        self.main_window.file_explorer.new_folder_requested.connect(
            self.handle_new_folder
        )
        self.main_window.file_explorer.rename_item_requested.connect(
            self.handle_rename_item
        )
        self.main_window.file_explorer.delete_item_requested.connect(
            self.handle_delete_item
        )
        self.main_window.tab_widget.tabCloseRequested.connect(self.handle_close_tab)

    def set_workspace_path(self, path: str):
        self.workspace_path = path

    def get_language_id(self, file_path: str) -> str:
        return "python" if Path(file_path).suffix == ".py" else "plaintext"

    def is_dirty(self, editor: QWidget) -> bool:
        return editor in self.dirty_editors

    @Slot()
    def open_file_dialog(self):
        start_dir = self.workspace_path or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Open File", dir=start_dir
        )
        if file_path:
            self.open_file_from_path(file_path)

    @Slot(str)
    def open_file_from_path(self, file_path: str, is_merge_conflict: bool = False):
        if not self.workspace_path:
            QMessageBox.warning(
                self.main_window,
                "No Workspace",
                "Please open a workspace folder first.",
            )
            return

        workspace_p = Path(self.workspace_path).resolve()
        file_p = Path(file_path).resolve()

        if workspace_p not in file_p.parents and workspace_p != file_p.parent:
            if self.main_window.sender() is not self.main_window.file_menu.actions()[2]:
                return

        canonical_path = str(file_p)
        if canonical_path in self.editors_by_path:
            editor = self.editors_by_path[canonical_path]
            self.main_window.tab_widget.setCurrentWidget(editor)
            if is_merge_conflict:
                editor.enter_merge_mode()
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if self.editor_cache:
                editor = self.editor_cache.pop()
                editor.apply_theme(self.theme_manager.get_current_theme_data())
            else:
                editor = EditorWidget(self.theme_manager.get_current_theme_data())

            editor.text_changed.connect(lambda e=editor: self.mark_file_dirty(e))

            self.open_file_paths[editor] = canonical_path
            self.editors_by_path[canonical_path] = editor

            editor.setProperty("is_merge_editor", is_merge_conflict)

            self.main_window.add_editor_tab(file_path, editor)

            uri = file_p.as_uri()
            lang_id = self.get_language_id(file_path)

            def on_model_ready():
                self.file_opened.emit(uri, lang_id, content, editor)
                if is_merge_conflict:
                    editor.enter_merge_mode()

            editor.set_content(content, lang_id, uri, on_model_ready)

        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not open file:\n{e}"
            )

    def open_diff_viewer(self, file_path: str, status: str):
        head_content = self.main_window.controller.git_manager.get_head_content(
            file_path
        )

        try:
            disk_content = Path(file_path).read_text(encoding="utf-8")
        except (IOError, UnicodeDecodeError):
            disk_content = ""

        if head_content is None and status == "A":
            head_content = ""
        elif head_content is None:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not retrieve previous version of '{os.path.basename(file_path)}' from Git.",
            )
            return

        diff_widget = DiffEditorWidget(self.theme_manager.get_current_theme_data())
        original_label = f"{os.path.basename(file_path)} (HEAD)"
        modified_label = f"{os.path.basename(file_path)} (Working Tree)"
        diff_widget.set_diff_content(
            head_content, disk_content, original_label, modified_label
        )
        self.main_window.add_editor_tab(
            f"Diff: {os.path.basename(file_path)}", diff_widget
        )

    def open_file_for_merge(self, file_path: str):
        self.open_file_from_path(file_path, is_merge_conflict=True)

    def close_all_merge_editors(self):
        for i in reversed(range(self.main_window.tab_widget.count())):
            widget = self.main_window.tab_widget.widget(i)
            if widget and widget.property("is_merge_editor"):

                if hasattr(widget, "exit_merge_mode"):
                    widget.exit_merge_mode()
                self.handle_close_tab(i, force=True)

    @Slot(int)
    def handle_close_tab(self, index: int, force: bool = False):
        editor_widget = self.main_window.tab_widget.widget(index)
        if editor_widget:
            if not force and editor_widget in self.dirty_editors:
                current_text = self.main_window.tab_widget.tabText(index)
                file_name = (
                    current_text[:-2] if current_text.endswith(" *") else current_text
                )
                reply = QMessageBox.question(
                    self.main_window,
                    "Unsaved Changes",
                    f"'{file_name}' has unsaved changes. Do you want to save them?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Save:
                    self.save_file(editor_widget)
                elif reply == QMessageBox.StandardButton.Cancel:
                    return

            path = self.open_file_paths.pop(editor_widget, None)
            if path:
                uri = Path(path).as_uri()
                self.editors_by_path.pop(path, None)
                self.file_closed.emit(uri)
                self.dirty_editors.discard(editor_widget)

            self.main_window.tab_widget.removeTab(index)
            editor_widget.setVisible(False)
            editor_widget.setParent(None)

            if isinstance(editor_widget, EditorWidget) and not isinstance(
                editor_widget, DiffEditorWidget
            ):
                self.editor_cache.append(editor_widget)

    def close_tab_by_path(self, file_path: str):
        editor_to_close = self.editors_by_path.get(file_path)
        if editor_to_close:
            index = self.main_window.tab_widget.indexOf(editor_to_close)
            if index != -1:
                self.dirty_editors.discard(editor_to_close)
                self.handle_close_tab(index)

    def save_file(self, editor=None):
        if editor is None:
            editor = self.main_window.get_current_editor()

        if (
            editor
            and isinstance(editor, EditorWidget)
            and editor in self.open_file_paths
        ):
            file_path = self.open_file_paths[editor]
            if file_path:
                editor.get_text(
                    lambda content, e=editor, p=file_path: self._on_get_text_for_save(
                        content, e, p
                    )
                )
        else:
            self.save_file_as()

    def _on_get_text_for_save(self, content, editor, file_path):
        if content is None:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.mark_file_clean(editor)
            self.file_saved.emit(file_path, content)
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not save file:\n{e}"
            )

    @Slot()
    def save_file_as(self):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, EditorWidget):
            editor.get_text(self._on_get_text_for_save_as)

    def _on_get_text_for_save_as(self, content):
        if content is None:
            return
        editor = self.main_window.get_current_editor()
        start_dir = self.workspace_path or ""
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save File As...", start_dir
        )
        if file_path:
            self.open_file_paths[editor] = file_path
            self._on_get_text_for_save(content, editor, file_path)
            index = self.main_window.tab_widget.indexOf(editor)
            self.main_window.tab_widget.setTabText(index, os.path.basename(file_path))

    @Slot(EditorWidget)
    def mark_file_dirty(self, editor):
        if editor not in self.dirty_editors:
            self.dirty_editors.add(editor)
            index = self.main_window.tab_widget.indexOf(editor)
            if index != -1:
                current_text = self.main_window.tab_widget.tabText(index)
                if not current_text.endswith(" *"):
                    self.main_window.tab_widget.setTabText(index, f"{current_text} *")
            self.file_modified.emit(editor)

    def mark_file_clean(self, editor):
        if editor in self.dirty_editors:
            self.dirty_editors.remove(editor)
            index = self.main_window.tab_widget.indexOf(editor)
            if index != -1:
                current_text = self.main_window.tab_widget.tabText(index)
                if current_text.endswith(" *"):
                    self.main_window.tab_widget.setTabText(index, current_text[:-2])

    @Slot(str)
    def handle_new_file(self, parent_dir):
        file_name, ok = QInputDialog.getText(
            self.main_window, "New File", "Enter file name:"
        )
        if ok and file_name:
            new_path = Path(parent_dir) / file_name
            try:
                if not new_path.exists():
                    new_path.touch()
                else:
                    QMessageBox.warning(
                        self.main_window,
                        "Exists",
                        "A file with that name already exists.",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not create file:\n{e}"
                )

    @Slot(str)
    def handle_new_folder(self, parent_dir):
        folder_name, ok = QInputDialog.getText(
            self.main_window, "New Folder", "Enter folder name:"
        )
        if ok and folder_name:
            new_path = Path(parent_dir) / folder_name
            try:
                new_path.mkdir(exist_ok=False)
            except FileExistsError:
                QMessageBox.warning(
                    self.main_window,
                    "Exists",
                    "A folder with that name already exists.",
                )
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not create folder:\n{e}"
                )

    @Slot(str)
    def handle_rename_item(self, path_str):
        path = Path(path_str)
        old_name = path.name
        new_name, ok = QInputDialog.getText(
            self.main_window, f"Rename {old_name}", "Enter new name:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            new_path = path.with_name(new_name)
            try:
                path.rename(new_path)
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not rename item:\n{e}"
                )

    @Slot(str)
    def handle_delete_item(self, path_str):
        import shutil

        path = Path(path_str)
        is_dir = path.is_dir()
        item_type = "folder" if is_dir else "file"
        reply = QMessageBox.question(
            self.main_window,
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_dir:
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except Exception as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not delete {item_type}:\n{e}"
                )
