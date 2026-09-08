import customtkinter as ctk
from tkinter import Menu
import os


class MenuBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.configure(height=30, corner_radius=0)

        left_frame = ctk.CTkFrame(self, fg_color="transparent")
        left_frame.pack(side="left", fill="y", padx=5)

        self.add_menu_button(left_frame, "File", self.get_file_menu_options)
        self.add_menu_button(left_frame, "Edit", self.get_edit_menu_options)
        self.add_menu_button(left_frame, "Selection", self.get_selection_menu_options)
        self.add_menu_button(left_frame, "View", self.get_view_menu_options)
        self.add_menu_button(left_frame, "Go", self.get_go_menu_options)
        self.add_menu_button(left_frame, "Run", self.get_run_menu_options)
        self.add_menu_button(left_frame, "Terminal", self.get_terminal_menu_options)
        self.add_menu_button(left_frame, "Help", self.get_help_menu_options)

    def get_file_menu_options(self):
        recent_files = self.master.settings.get("recent_files", [])
        recent_projects = self.master.settings.get("recent_projects", [])
        recent_menu_items = []
        if recent_files:
            for f in recent_files:
                if os.path.exists(f):
                    recent_menu_items.append(
                        (f, lambda p=f: self.master.editor_service.on_file_open(p))
                    )
        if recent_projects:
            if recent_menu_items:
                recent_menu_items.append(("---", None))
            for p in recent_projects:
                if os.path.exists(p):
                    recent_menu_items.append(
                        (
                            f"{os.path.basename(p)}  [{p}]",
                            lambda path=p: self.master.project_service.open_project(
                                path
                            ),
                        )
                    )
        if recent_menu_items:
            recent_menu_items.append(("---", None))
            recent_menu_items.append(
                ("Clear Recently Opened", self.master.dummy_command)
            )
        return [
            ("New File...", self.master.dummy_command),
            ("---", None),
            ("Open File...", self.master.dummy_command),
            ("Open Folder...", self.master.prompt_open_folder),
            ("Open Recent", recent_menu_items),
            ("---", None),
            (
                "Save",
                lambda: self.master.trigger_active_editor_command("save_active_file"),
            ),
            (
                "Save As...",
                lambda: self.master.trigger_active_editor_command(
                    "save_as_active_file"
                ),
            ),
            (
                "Save All",
                lambda: self.master.trigger_active_editor_command("save_all_files"),
            ),
            ("---", None),
            (
                "Close Editor",
                lambda: self.master.trigger_active_editor_command("close"),
            ),
            (
                "Close Folder",
                lambda: self.master.trigger_active_editor_command("close_folder"),
            ),
            ("---", None),
            ("Exit", self.master.quit),
        ]

    def get_edit_menu_options(self):
        return [
            ("Undo", lambda: self.master.trigger_active_editor_command("undo")),
            ("Redo", lambda: self.master.trigger_active_editor_command("redo")),
            ("---", None),
            ("Cut", lambda: self.master.trigger_active_editor_command("cut")),
            ("Copy", lambda: self.master.trigger_active_editor_command("copy")),
            ("Paste", lambda: self.master.trigger_active_editor_command("paste")),
        ]

    def get_selection_menu_options(self):
        return [
            (
                "Select All",
                lambda: self.master.trigger_active_editor_command("select_all"),
            )
        ]

    def get_view_menu_options(self):
        return [
            ("Command Palette...", self.master.dummy_command),
            ("---", None),
            (
                "Problems",
                lambda: (
                    self.master.bottom_panel.set("PROBLEMS")
                    if hasattr(self.master, "bottom_panel")
                    else None
                ),
            ),
            (
                "Output",
                lambda: (
                    self.master.bottom_panel.set("OUTPUT")
                    if hasattr(self.master, "bottom_panel")
                    else None
                ),
            ),
            (
                "Terminal",
                lambda: (
                    self.master.bottom_panel.set("TERMINAL")
                    if hasattr(self.master, "bottom_panel")
                    else None
                ),
            ),
        ]

    def get_go_menu_options(self):
        return [("Go to File...", self.master.dummy_command)]

    def get_run_menu_options(self):
        return [
            (
                "Run Without Debugging",
                lambda: self.master.trigger_active_editor_command("run_current_file"),
            ),
            ("Start Debugging", self.master.dummy_command),
        ]

    def get_terminal_menu_options(self):
        return [("New Terminal", self.master.dummy_command)]

    def get_help_menu_options(self):
        return [
            (
                "Welcome",
                lambda: (
                    self.master.editor_area.show_welcome_tab()
                    if hasattr(self.master, "editor_area")
                    else None
                ),
            )
        ]

    def add_menu_button(self, parent, text, options_func):
        button = ctk.CTkButton(
            parent,
            text=text,
            width=40,
            height=25,
            corner_radius=4,
            fg_color="transparent",
            hover_color="#4a4a4a",
        )
        button.pack(side="left", padx=1)

        def show_menu(event):
            options = options_func()
            self._create_menu(button, options)

        button.bind("<Button-1>", show_menu)

    def _create_menu(self, parent_button, options):
        menu = Menu(
            self.master,
            tearoff=0,
            background="#2b2b2b",
            foreground="white",
            activebackground="#0078D7",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
        )
        for label, command in options:
            if not command and not isinstance(command, list):
                continue
            if label == "---":
                menu.add_separator()
            elif isinstance(command, list):
                submenu = Menu(
                    menu,
                    tearoff=0,
                    background="#2b2b2b",
                    foreground="white",
                    activebackground="#0078D7",
                    activeforeground="white",
                    relief="flat",
                    borderwidth=0,
                )
                if not command:
                    submenu.add_command(label="No Recent Items", state="disabled")
                else:
                    for sub_label, sub_command in command:
                        if sub_label == "---":
                            submenu.add_separator()
                        else:
                            submenu.add_command(label=sub_label, command=sub_command)
                menu.add_cascade(label=label, menu=submenu)
            else:
                menu.add_command(
                    label=label,
                    command=command,
                    accelerator=self.get_accelerator(label),
                )
        x = parent_button.winfo_rootx()
        y = parent_button.winfo_rooty() + parent_button.winfo_height()
        menu.tk_popup(x, y)

    def get_accelerator(self, label):
        mapping = {
            "Save": "Ctrl+S",
            "Undo": "Ctrl+Z",
            "Redo": "Ctrl+Y",
            "Cut": "Ctrl+X",
            "Copy": "Ctrl+C",
            "Paste": "Ctrl+V",
            "Select All": "Ctrl+A",
            "Run Without Debugging": "Ctrl+F5",
        }
        return mapping.get(label, "")
