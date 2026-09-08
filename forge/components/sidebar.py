import customtkinter as ctk
from tkinter import Menu
import os
import threading
from .custom_tree_view import CustomTreeView


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, master_controller, **kwargs):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=0, **kwargs)
        self.master = master_controller
        self.project_path = None
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1, minsize=200)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="EXPLORER", font=("Segoe UI", 12, "bold"), anchor="w", padx=10
        ).grid(row=0, column=0, sticky="ew", pady=5)
        self.file_explorer = CustomTreeView(
            self, command=self._handle_explorer_click, app_reference=self.master
        )
        self.file_explorer.grid(row=1, column=0, sticky="nsew", padx=5)

        ctk.CTkLabel(
            self, text="OUTLINE", font=("Segoe UI", 12, "bold"), anchor="w", padx=10
        ).grid(row=2, column=0, sticky="ew", pady=(5, 5))
        self.outline_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.outline_frame.grid(row=3, column=0, sticky="nsew", padx=5)
        self.outline_frame.grid_rowconfigure(0, weight=1)
        self.outline_frame.grid_columnconfigure(0, weight=1)
        self.outline_view = CustomTreeView(
            self.outline_frame,
            command=self._handle_outline_click,
            app_reference=self.master,
        )
        self.outline_placeholder = ctk.CTkLabel(
            self.outline_frame,
            text="Open a file to see its outline.",
            text_color="#777777",
        )
        self.update_outline([])

    def _show_context_menu(self, event):
        target_node = None
        for node in self.file_explorer.nodes.values():
            if node.winfo_containing(event.x_root, event.y_root) in [
                node,
                node.main_frame,
            ] or (
                hasattr(node.main_frame, "winfo_containing")
                and node.main_frame.winfo_containing(event.x_root, event.y_root)
            ):
                target_node = node
                break
        if not target_node:
            return

        path = target_node.data["path"]
        menu = Menu(
            self,
            tearoff=0,
            background="#2b2b2b",
            foreground="white",
            activebackground="#0078D7",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
        )
        menu.add_command(
            label="New File...",
            command=lambda: self.master.project_service.handle_new_file(path),
        )
        menu.add_command(
            label="New Folder...",
            command=lambda: self.master.project_service.handle_new_folder(path),
        )
        menu.add_separator()
        menu.add_command(
            label="Rename...",
            command=lambda: self.master.project_service.handle_rename(path),
        )
        menu.add_command(
            label="Move...",
            command=lambda: self.master.project_service.handle_move(path),
        )
        menu.add_separator()
        menu.add_command(
            label="Delete...",
            command=lambda: self.master.project_service.handle_delete(path),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def update_project_path(self, new_path):
        self.project_path = new_path
        self.scan_and_populate(self.project_path, is_root=True)

    def scan_and_populate(self, path, is_root=False):
        def _scan_thread():
            children = self._get_children_for_path(path)
            if is_root:
                tree_data = {
                    "type": "folder",
                    "name": os.path.basename(path),
                    "path": path,
                    "children": children,
                }
                self.master.after(0, self.file_explorer.update_tree, tree_data)
            else:
                node = self.file_explorer.nodes.get(path)
                if node:
                    self.master.after(0, node.set_children, children)

        threading.Thread(target=_scan_thread, daemon=True).start()

    def _get_children_for_path(self, path):
        children = []
        try:
            for entry in sorted(
                os.scandir(path), key=lambda e: (e.is_file(), e.name.lower())
            ):
                if entry.name.startswith(".") or entry.name in [
                    "__pycache__",
                    "venv",
                    ".venv",
                    "build",
                    "dist",
                ]:
                    continue
                node_data = {
                    "type": "folder" if entry.is_dir() else "file",
                    "name": entry.name,
                    "path": entry.path,
                }
                if entry.is_dir():
                    node_data["children"] = []
                children.append(node_data)
        except OSError:
            pass
        return children

    def refresh_directory(self, path):
        parent_dir = os.path.dirname(path)
        if os.path.exists(parent_dir):
            if parent_dir == self.project_path:
                self.scan_and_populate(self.project_path, is_root=True)
            else:
                self.scan_and_populate(parent_dir)
        if os.path.isdir(path) and os.path.exists(path):
            self.scan_and_populate(path)

    def _handle_explorer_click(self, node):
        node_data = node.data
        if node_data["type"] == "folder":

            node.toggle_expansion()
            if not node.children_created:
                self.scan_and_populate(node_data["path"])
        else:
            self.master.editor_service.on_file_open(node_data["path"])

    def _handle_outline_click(self, node):
        line = node.data.get("lineno")
        if line:
            self.master.editor_area.goto_active_editor_line(int(line))

    def update_outline(self, symbols):
        if not symbols:
            self.outline_placeholder.grid(row=0, column=0, sticky="nsew")
            self.outline_view.grid_forget()
        else:
            self.outline_placeholder.grid_forget()
            self.outline_view.grid(row=0, column=0, sticky="nsew")
            outline_data = {"type": "file", "name": "Symbols", "children": symbols}
            self.outline_view.update_tree(outline_data)
