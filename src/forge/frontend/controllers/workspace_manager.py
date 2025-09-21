import os
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QObject, Slot, Signal

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
        self._connect_signals()

    def _connect_signals(self):
        self.main_window.welcome_file_explorer.open_folder_button.clicked.connect(
            self.open_workspace_dialog
        )
        self.main_window.file_menu.actions()[1].triggered.connect(
            self.open_workspace_dialog
        )

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
