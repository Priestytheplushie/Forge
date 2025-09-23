import os
import json
import sys
import ctypes
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QObject, Slot, Signal
from pathlib import Path

from forge.backend.lsp.manager import LSPManager
from forge.backend.project.scanner import detect_python_project_layout
from forge.frontend.assets.icon_map import get_status_icon


class WorkspaceManager(QObject):
    """Manages the workspace, project settings, and the LSP lifecycle."""

    workspace_will_change = Signal()
    workspace_changed = Signal(str)
    lsp_manager_created = Signal(object)

    def __init__(self, main_window, app_root: str):
        super().__init__(main_window)
        self.main_window = main_window
        self.app_root = app_root
        self.workspace_path = None
        self.lsp_manager = None

        self.settings_path = Path(app_root) / ".forge" / "settings.json"
        self.recent_projects = self._load_recent_projects()

    def _load_recent_projects(self) -> list:
        try:
            if self.settings_path.exists():
                with open(self.settings_path, "r") as f:
                    settings = json.load(f)
                    return settings.get("recent_projects", [])
        except (IOError, json.JSONDecodeError):
            pass
        return []

    def _save_recent_projects(self):
        try:
            forge_dir = self.settings_path.parent
            forge_dir.mkdir(parents=True, exist_ok=True)

            if sys.platform == "win32":
                try:
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(forge_dir))
                    if not attrs & 2:
                        ctypes.windll.kernel32.SetFileAttributesW(
                            str(forge_dir), attrs | 2
                        )
                except Exception:
                    pass

            with open(self.settings_path, "w") as f:
                json.dump({"recent_projects": self.recent_projects}, f, indent=2)
        except IOError:
            pass

    def _add_to_recent_projects(self, path: str):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10]
        self._save_recent_projects()

    @Slot()
    def open_workspace_dialog(self):
        path = QFileDialog.getExistingDirectory(
            self.main_window, "Open Workspace Folder"
        )
        if path:
            self.set_workspace(path)

    def set_workspace(self, path: str):
        self.workspace_will_change.emit()

        self.workspace_path = path
        self._add_to_recent_projects(path)
        self.main_window.setWindowTitle(f"Forge - {os.path.basename(path)}")

        if (
            self.main_window.file_explorer_stack.currentWidget()
            is not self.main_window.file_explorer
        ):
            self.main_window.file_explorer_stack.setCurrentWidget(
                self.main_window.file_explorer
            )
        self.main_window.file_explorer.set_root_path(path)

        self.main_window.terminal.start_session(path)
        self.main_window.show_editor_view()

        if self.lsp_manager:
            self.lsp_manager.shutdown()

        self.workspace_changed.emit(path)

        self.main_window.lsp_status_label.setText("LSP: Initializing...")
        self.main_window.lsp_status_label.setPixmap(
            get_status_icon("cpu").pixmap(16, 16)
        )

        lsp_config = detect_python_project_layout(self.workspace_path)
        self.lsp_manager = LSPManager(
            self.app_root, self.workspace_path, lsp_config, self
        )
        self.lsp_manager_created.emit(self.lsp_manager)
        self.lsp_manager.start_server()

    def shutdown_lsp(self):
        if self.lsp_manager:
            self.lsp_manager.shutdown()

    @Slot()
    def clear_recent_projects(self):
        self.recent_projects.clear()
        self._save_recent_projects()
        self.main_window.welcome_screen.update_recent_list(self.recent_projects)
