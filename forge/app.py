import customtkinter as ctk
from tkinter.filedialog import askdirectory, asksaveasfilename
from tkinter import messagebox
import os, sys, threading, subprocess, json, shutil, re
from pathlib import Path
from urllib.parse import unquote
from collections import defaultdict
from queue import Queue, Empty

from .components.menu_bar import MenuBar
from .components.activity_bar import ActivityBar
from .components.sidebar import Sidebar
from .components.editor_area import EditorArea
from .components.status_bar import StatusBar
from .components.terminal import ForgeTerminal
from .components.custom_tree_view import CustomTreeView
from .components.move_dialog import MoveDialog
from .services.document import Document
from .services.environment_service import EnvironmentService
from .services.lsp_client import ForgeLspClient
from .services.ast_parser import ASTParser
from .services.project_service import ProjectService
from .services.editor_service import EditorService


class WelcomeScreen(ctk.CTkFrame):
    def __init__(self, master, open_project_callback, open_recent_callback):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        self.grid_rowconfigure((0, 3), weight=1)
        self.grid_columnconfigure((0, 2), weight=1)
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=1, column=1)
        ctk.CTkLabel(container, text="🔥", font=("Segoe UI Emoji", 80)).pack(pady=20)
        ctk.CTkLabel(container, text="Forge", font=("Segoe UI", 40, "bold")).pack(
            pady=(0, 10)
        )
        ctk.CTkLabel(
            container,
            text="Your Local-First AI IDE",
            font=("Segoe UI", 16),
            text_color="#999999",
        ).pack(pady=(0, 40))
        ctk.CTkButton(
            container,
            text="Open Folder",
            command=open_project_callback,
            height=40,
            font=("Segoe UI", 14),
        ).pack(fill="x", pady=5)
        ctk.CTkButton(
            container,
            text="Clone Repository",
            height=40,
            fg_color="#333333",
            hover_color="#444444",
            font=("Segoe UI", 14),
        ).pack(fill="x", pady=5)
        recent_projects = master.settings.get("recent_projects", [])
        if recent_projects:
            ctk.CTkLabel(
                container,
                text="Recent Projects",
                font=("Segoe UI", 12, "bold"),
                text_color="#aaaaaa",
            ).pack(fill="x", pady=(20, 5))
            for path in recent_projects[:5]:
                project_name = os.path.basename(path)
                btn = ctk.CTkButton(
                    container,
                    text=project_name,
                    anchor="w",
                    fg_color="transparent",
                    text_color="#3498db",
                    hover=False,
                    command=lambda p=path: open_recent_callback(p),
                )
                btn.pack(fill="x")


class ForgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Forge")
        self.geometry("1400x900")
        self.settings_path = self._get_settings_path()
        self.settings = self._load_settings()
        self.project_service = ProjectService(self)
        self.editor_service = EditorService(self)
        self.environment_service = None
        self.lsp_client = None
        self.ast_parser = ASTParser()
        self.diagnostics_cache = defaultdict(list)
        self._ast_update_job = None
        self._update_problems_job = None
        self.last_symbols = {}
        self.show_welcome_screen()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<FocusOut>", self.on_focus_out)

    def select_interpreter(self):
        if self.environment_service:
            self.environment_service.select_interpreter()

    def trigger_active_editor_command(self, command_name):
        if command_name == "quit":
            self.quit()
            return
        if command_name == "open_folder":
            self.prompt_open_folder()
            return
        if not (hasattr(self, "project_service") and self.project_service.project_path):
            if command_name != "dummy":
                print("Command requires an open project.")
            return
        if command_name == "run_current_file_in_terminal":
            self.run_current_file_in_terminal()
            return
        if command_name == "run_current_file_in_output":
            self.editor_service.run_current_file_in_output()
            return
        if hasattr(self.editor_service, command_name):
            getattr(self.editor_service, command_name)()
        elif hasattr(self.project_service, command_name):
            getattr(self.project_service, command_name)()
        elif hasattr(self, command_name):
            getattr(self, command_name)()
        elif command_name == "close":
            if self.editor_area.active_tab:
                self.editor_area.close_tab(self.editor_area.active_tab)
        elif command_name == "dummy":
            self.dummy_command()
        else:
            editor = self.editor_area.get_active_editor()
            if hasattr(editor, "actions") and hasattr(editor.actions, command_name):
                getattr(editor.actions, command_name)()

    def show_welcome_screen(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.welcome_screen = WelcomeScreen(
            self, self.prompt_open_folder, self.project_service.open_project
        )

    def on_focus_out(self, event=None):
        if (
            hasattr(self, "editor_area")
            and self.editor_area
            and self.editor_area.winfo_exists()
        ):
            active_editor = self.editor_area.get_active_editor()
            if active_editor and hasattr(active_editor, "autocomplete_menu"):
                if (
                    active_editor.autocomplete_menu
                    and active_editor.autocomplete_menu.winfo_exists()
                ):
                    active_editor.autocomplete_menu.close()

    def initialize_ide_ui(self):
        for widget in self.winfo_children():
            if hasattr(self, "welcome_screen") and widget is self.welcome_screen:
                continue
            widget.destroy()
        self.environment_service = EnvironmentService(self)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.menu_bar = MenuBar(self)
        self.menu_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        main_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, minsize=50, weight=0)
        main_frame.grid_columnconfigure(1, minsize=250, weight=1)
        main_frame.grid_columnconfigure(2, minsize=600, weight=5)
        self.activity_bar = ActivityBar(main_frame)
        self.activity_bar.grid(row=0, column=0, sticky="ns")
        self.sidebar = Sidebar(main_frame, self)
        self.sidebar.grid(row=0, column=1, sticky="ns")
        self.sidebar.update_project_path(self.project_service.project_path)
        content_area = ctk.CTkFrame(main_frame, fg_color="transparent")
        content_area.grid(row=0, column=2, sticky="nsew")
        content_area.grid_rowconfigure(0, weight=3)
        content_area.grid_rowconfigure(1, weight=0)
        content_area.grid_rowconfigure(2, weight=1)
        content_area.grid_columnconfigure(0, weight=1)
        self.editor_area = EditorArea(content_area, self)
        self.editor_area.grid(row=0, column=0, sticky="nsew")
        self.resizer = ctk.CTkFrame(
            content_area, height=5, cursor="sb_v_double_arrow", fg_color="#333333"
        )
        self.resizer.grid(row=1, column=0, sticky="ew")
        self.resizer.bind("<B1-Motion>", self._do_resize)
        self.bottom_panel = ctk.CTkTabview(
            content_area, fg_color="#242424", corner_radius=0, border_width=0
        )
        self.bottom_panel.grid(row=2, column=0, sticky="nsew")

        problems_tab = self.bottom_panel.add("PROBLEMS")
        problems_tab.grid_columnconfigure(0, weight=1)
        problems_tab.grid_rowconfigure(0, weight=1)
        self.problems_view = CustomTreeView(
            problems_tab, command=self.on_problem_select, app_reference=self
        )
        self.problems_placeholder = ctk.CTkLabel(
            problems_tab, text="No problems have been detected.", text_color="#777777"
        )

        output_tab = self.bottom_panel.add("OUTPUT")
        output_tab.grid_rowconfigure(0, weight=1)
        output_tab.grid_columnconfigure(0, weight=1)
        self.editor_service.setup_output_panel(output_tab)

        terminal_tab = self.bottom_panel.add("TERMINAL")
        terminal_tab.grid_rowconfigure(0, weight=1)
        terminal_tab.grid_columnconfigure(0, weight=1)

        self.terminal = ForgeTerminal(terminal_tab, app_reference=self)
        self.terminal.grid(row=0, column=0, sticky="nsew")

        self.bottom_panel.set("TERMINAL")
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.update_status_bar_python_version()
        self.start_lsp_client()
        self.after(100, self.activate_terminal_venv)
        self.editor_area.show_welcome_tab()
        self.deiconify()
        self.update_idletasks()

    def _get_settings_path(self):
        home = Path.home()
        settings_dir = home / ".forge"
        settings_dir.mkdir(exist_ok=True)
        return settings_dir / "settings.json"

    def _load_settings(self):
        try:
            with open(self.settings_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_settings(self):
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _add_to_recent_projects(self, path):
        recent = self.settings.get("recent_projects", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.settings["recent_projects"] = recent[:10]
        self._save_settings()

    def _add_to_recent_files(self, path):
        recent = self.settings.get("recent_files", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.settings["recent_files"] = recent[:10]
        self._save_settings()

    def _do_resize(self, event):
        content_area = self.resizer.master
        total_height = content_area.winfo_height()
        new_y = event.y_root - content_area.winfo_rooty()
        if new_y < 100:
            new_y = 100
        if new_y > total_height - 100:
            new_y = total_height - 100
        content_area.grid_rowconfigure(0, weight=new_y)
        content_area.grid_rowconfigure(2, weight=total_height - new_y)

    def prompt_open_folder(self):
        path = askdirectory(title="Select a Folder to Open")
        if path:
            self.project_service.open_project(path)

    def run_current_file_in_terminal(self):
        active_file_path = self.editor_area.get_active_file_path()
        if not (active_file_path and self.environment_service.active_interpreter):
            return
        interp = self.environment_service.active_interpreter
        project_root = self.project_service.project_path
        rel_path = os.path.relpath(active_file_path, project_root)
        module_path = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
        command = f'"{interp}" -m {module_path}'
        if sys.platform == "win32":
            command = f"& {command}"
        self.bottom_panel.set("TERMINAL")
        self.terminal.run_command(command)

    def activate_terminal_venv(self):
        if (
            self.environment_service
            and self.environment_service.active_interpreter
            and "venv" in self.environment_service.active_interpreter
        ):
            interp = self.environment_service.active_interpreter
            venv_path = os.path.dirname(os.path.dirname(interp))
            if sys.platform == "win32":
                activate_script = os.path.join(venv_path, "Scripts", "Activate.ps1")
                command = f". '{activate_script}'"
            else:
                activate_script = os.path.join(venv_path, "bin", "activate")
                command = f"source '{activate_script}'"
            self.terminal.run_command(command)

    def post_load_actions(self, doc):
        self._add_to_recent_files(doc.file_path)
        content = doc.get_content()
        editor_widget = self.editor_area.get_editor_for_uri(doc.file_uri)
        symbols = (
            self.ast_parser.get_symbols(content)
            if editor_widget
            and hasattr(editor_widget, "is_python_file")
            and editor_widget.is_python_file
            else []
        )

        def update_ui_main_thread():
            if not editor_widget or not editor_widget.winfo_exists():
                return
            self.last_symbols[doc.file_uri] = symbols
            if self.editor_area.get_active_file_uri() == doc.file_uri:
                self.sidebar.update_outline(symbols)
            if hasattr(editor_widget, "update_folding_markers"):
                editor_widget.update_folding_markers(symbols)
            self.editor_area.mark_as_loaded(doc.file_uri)
            if (
                self.lsp_client
                and hasattr(editor_widget, "is_python_file")
                and editor_widget.is_python_file
            ):
                self.lsp_client.did_open(doc.file_uri, content)

        self.after(0, update_ui_main_thread)

    def on_diagnostics(self, file_uri, diagnostics):
        self.diagnostics_cache[file_uri] = diagnostics
        editor = self.editor_area.get_editor_for_uri(file_uri)
        if editor and hasattr(editor, "apply_diagnostics"):
            editor.apply_diagnostics(diagnostics)
        if self._update_problems_job:
            self.after_cancel(self._update_problems_job)
        self._update_problems_job = self.after(50, self._build_and_apply_problems)

    def update_problems_panel_async(self):
        if hasattr(self, "bottom_panel"):
            self._build_and_apply_problems()

    def _build_and_apply_problems(self):
        grouped_problems = defaultdict(list)
        for uri, diags in self.diagnostics_cache.items():
            if not diags:
                continue
            for p in diags:
                problem_data = {
                    "type": (
                        "problem_error"
                        if p.get("severity", 1) == 1
                        else "problem_warning"
                    ),
                    "name": p["message"],
                    "details": f"[{p['range']['start']['line'] + 1}, {p['range']['start']['character'] + 1}]",
                    "lineno": p["range"]["start"]["line"] + 1,
                    "file_uri": uri,
                }
                grouped_problems[uri].append(problem_data)
        tree_data_children = []
        for uri, problems in grouped_problems.items():
            file_name = os.path.basename(unquote(uri.replace("file:///", "")))
            file_node = {
                "type": "folder",
                "name": file_name,
                "details": f"{len(problems)} problem{'s' if len(problems) > 1 else ''}",
                "path": uri,
                "children": sorted(problems, key=lambda p: p["lineno"]),
            }
            tree_data_children.append(file_node)
        tree_data_children.sort(key=lambda x: x["name"])
        final_tree_data = {
            "type": "root",
            "name": "root",
            "children": tree_data_children,
        }
        problem_count = sum(
            len(node.get("children", [])) for node in final_tree_data["children"]
        )
        problems_tab_name = (
            f"PROBLEMS ({problem_count})" if problem_count > 0 else "PROBLEMS"
        )
        try:
            self.bottom_panel._tab_dict["PROBLEMS"].configure(text=problems_tab_name)
        except Exception:
            pass
        if not problem_count:
            self.problems_view.grid_forget()
            self.problems_placeholder.grid(row=0, column=0, sticky="nsew")
        else:
            self.problems_placeholder.grid_forget()
            self.problems_view.grid(row=0, column=0, sticky="nsew")
            self.problems_view.update_tree(final_tree_data)

    def on_problem_select(self, node):
        uri = node.data.get("file_uri") or node.data.get("path")
        line = node.data.get("lineno")
        file_path = unquote(uri.replace("file:///", ""))
        if line:
            self.editor_area.goto_location(uri, line)
        else:
            self.editor_service.on_file_open(file_path)

    def update_status_bar_python_version(self):
        if self.environment_service and self.environment_service.active_interpreter:
            version = self.environment_service.get_version(
                self.environment_service.active_interpreter
            )
            self.status_bar.update_python_version(version)
        else:
            self.status_bar.update_python_version("No Python Found")

    def start_lsp_client(self):
        if self.lsp_client:
            self.lsp_client.shutdown()
        ide_python = sys.executable
        project_python = (
            self.environment_service.active_interpreter
            if self.environment_service
            else None
        )
        project_path = (
            self.project_service.project_path if self.project_service else None
        )
        if project_python and project_path:
            self.lsp_client = ForgeLspClient(self, ide_python, project_python)
            root_uri = Path(project_path).as_uri()
            self.lsp_client.initialize(root_uri)
        else:
            print("Cannot start LSP client: No active interpreter or project path.")

    def on_close(self):
        if hasattr(self, "project_service") and self.project_service.project_path:
            self.project_service.close_folder()
            if self.project_service.project_path is None:
                self.destroy()
        else:
            self.destroy()

    def update_title(self, current_file_path=None):
        if not self.winfo_exists():
            return
        project_path = (
            self.project_service.project_path if self.project_service else None
        )
        if current_file_path:
            self.title(
                f"Forge - {os.path.basename(current_file_path)} ({project_path})"
            )
        elif project_path:
            self.title(f"Forge - {os.path.basename(project_path)}")
        else:
            self.title("Forge")

    def on_all_tabs_closed(self):
        self.update_title()
        self.sidebar.update_outline([])
        self.editor_area.show_welcome_tab()

    def update_ast_views(self, doc):
        content = doc.get_content()
        threading.Thread(
            target=self._threaded_update_ast, args=(doc, content), daemon=True
        ).start()

    def _threaded_update_ast(self, doc, content):
        symbols = self.ast_parser.get_symbols(content)
        self.after(0, self._update_ast_ui, doc.file_uri, symbols)

    def _update_ast_ui(self, file_uri, symbols):
        self.last_symbols[file_uri] = symbols
        if self.editor_area.get_active_file_uri() == file_uri:
            self.sidebar.update_outline(symbols)
        editor = self.editor_area.get_editor_for_uri(file_uri)
        if editor and hasattr(editor, "update_folding_markers"):
            editor.update_folding_markers(symbols)

    def quit(self):
        self.on_close()

    def dummy_command(self):
        print("Dummy command executed")
