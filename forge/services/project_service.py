import os
import shutil
from tkinter import messagebox
import customtkinter as ctk
from pathlib import Path

from ..components.move_dialog import MoveDialog


class ProjectService:
    def __init__(self, app_instance):
        self.app = app_instance
        self.project_path = None

    def open_project(self, path):
        if not os.path.isdir(path):

            if path in self.app.settings.get("recent_projects", []):
                self.app.settings["recent_projects"].remove(path)
            self.app._save_settings()
            self.app.show_welcome_screen()
            return

        self.project_path = path
        self.app.title(f"Forge - {os.path.basename(path)}")
        self.app._add_to_recent_projects(path)

        if (
            hasattr(self.app, "welcome_screen")
            and self.app.welcome_screen.winfo_exists()
        ):
            self.app.welcome_screen.destroy()

        self.app.withdraw()
        self.app.initialize_ide_ui()

    def close_folder(self):
        dirty_docs = self.app.editor_service.get_dirty_documents()
        if dirty_docs:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved files. Save them before closing the folder?",
            )
            if response is True:
                self.app.editor_service.save_all_files()
            elif response is None:
                return

        self.project_path = None
        self.app.diagnostics_cache.clear()
        self.app.last_symbols.clear()
        self.app.editor_service.close_all_documents()

        if self.app.lsp_client:
            self.app.lsp_client.shutdown()
            self.app.lsp_client = None

        self.app.title("Forge")
        self.app.show_welcome_screen()

    def handle_new_file(self, parent_path):
        if not os.path.isdir(parent_path):
            parent_path = os.path.dirname(parent_path)
        dialog = ctk.CTkInputDialog(text="Enter new file name:", title="New File")
        file_name = dialog.get_input()
        if file_name:
            new_path = os.path.join(parent_path, file_name)
            try:
                Path(new_path).touch()
                self.app.sidebar.refresh_directory(parent_path)
            except OSError as e:
                messagebox.showerror("Error", f"Could not create file: {e}")

    def handle_new_folder(self, parent_path):
        if not os.path.isdir(parent_path):
            parent_path = os.path.dirname(parent_path)
        dialog = ctk.CTkInputDialog(text="Enter new folder name:", title="New Folder")
        folder_name = dialog.get_input()
        if folder_name:
            new_path = os.path.join(parent_path, folder_name)
            try:
                os.makedirs(new_path)
                self.app.sidebar.refresh_directory(parent_path)
            except OSError as e:
                messagebox.showerror("Error", f"Could not create folder: {e}")

    def handle_rename(self, path):
        dialog = ctk.CTkInputDialog(
            text=f"Enter new name for {os.path.basename(path)}:", title="Rename"
        )
        if dialog._entry:
            dialog._entry.delete(0, "end")
            dialog._entry.insert(0, os.path.basename(path))

        new_name = dialog.get_input()
        if new_name and new_name != os.path.basename(path):
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
                self.app.sidebar.refresh_directory(os.path.dirname(path))
            except OSError as e:
                messagebox.showerror("Error", f"Could not rename: {e}")

    def handle_move(self, path):
        dialog = MoveDialog(self.app, item_path=path)
        new_dir = dialog.get_input()
        if new_dir and os.path.isdir(new_dir):
            try:
                shutil.move(path, new_dir)
                self.app.sidebar.refresh_directory(os.path.dirname(path))
                self.app.sidebar.refresh_directory(new_dir)
            except (OSError, shutil.Error) as e:
                messagebox.showerror("Error", f"Could not move item: {e}")

    def handle_delete(self, path):
        if messagebox.askyesno(
            "Delete", f"Are you sure you want to delete {os.path.basename(path)}?"
        ):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.app.sidebar.refresh_directory(os.path.dirname(path))
            except OSError as e:
                messagebox.showerror("Error", f"Could not delete: {e}")
