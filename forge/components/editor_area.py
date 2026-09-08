import customtkinter as ctk
from tkinter import messagebox
from tkinter.filedialog import asksaveasfilename
from pathlib import Path
from queue import Queue, Empty
import customtkinter as ctk
import sys
from pathlib import Path
from urllib.parse import unquote

from .welcome_tab import WelcomeTab
from .editor.code_editor import CodeEditor


class EditorArea(ctk.CTkFrame):
    """Minimal EditorArea providing the UI methods other modules expect.

    This is intentionally lightweight: it hosts editor widgets, tracks
    open editors by URI, and exposes the small API surface the app uses.
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.open_editors = {}
        self.active_tab = None
        self._welcome = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def show_welcome_tab(self):
        self._destroy_all_editor_frames()
        if self._welcome and self._welcome.winfo_exists():
            return
        self._welcome = WelcomeTab(self, {"dummy_command": lambda: None})
        self._welcome.grid(row=0, column=0, sticky="nsew")
        self.active_tab = None

    def add_editor_tab(self, doc):

        if doc.file_uri in self.open_editors:
            self.set_active_tab(doc.file_uri)
            return self.open_editors[doc.file_uri]["editor"]

        if self._welcome and self._welcome.winfo_exists():
            try:
                self._welcome.destroy()
            except:
                pass
            self._welcome = None

        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew")
        editor = CodeEditor(frame, doc, self.app)
        editor.pack(fill="both", expand=True)

        self.open_editors[doc.file_uri] = {"frame": frame, "editor": editor, "doc": doc}
        self.set_active_tab(doc.file_uri)
        return editor

    def set_active_tab(self, file_uri):
        if file_uri not in self.open_editors:
            return
        for uri, v in list(self.open_editors.items()):
            if uri == file_uri:
                v["frame"].tkraise()
                v["frame"].grid()
            else:
                try:
                    v["frame"].grid_forget()
                except:
                    pass
        self.active_tab = file_uri

    def get_active_editor(self):
        if not self.active_tab:
            return None
        return self.open_editors.get(self.active_tab, {}).get("editor")

    def get_active_file_path(self):
        if not self.active_tab:
            return None
        return self.open_editors.get(self.active_tab, {}).get("doc").file_path

    def get_active_file_uri(self):
        return self.active_tab

    def get_editor_for_uri(self, file_uri):
        return self.open_editors.get(file_uri, {}).get("editor")

    def update_tab_dirty_status(self, doc):

        return

    def reopen_tab_with_new_path(self, old_uri, doc):
        if old_uri not in self.open_editors:
            return
        entry = self.open_editors.pop(old_uri)
        self.open_editors[doc.file_uri] = {
            "frame": entry["frame"],
            "editor": entry["editor"],
            "doc": doc,
        }
        if self.active_tab == old_uri:
            self.active_tab = doc.file_uri

    def mark_as_loaded(self, file_uri):

        return

    def close_tab(self, file_uri):
        if file_uri not in self.open_editors:
            return
        entry = self.open_editors.pop(file_uri)
        try:
            entry["frame"].destroy()
        except:
            pass
        self.active_tab = next(iter(self.open_editors.keys()), None)
        if not self.active_tab:
            self.show_welcome_tab()

    def _destroy_all_editor_frames(self):
        for e in list(self.open_editors.values()):
            try:
                e["frame"].destroy()
            except:
                pass
        self.open_editors.clear()

    def goto_location(self, file_uri, line):
        if file_uri not in self.open_editors:

            file_path = Path(unquote(file_uri.replace("file://", "")))
            if sys.platform == "win32":
                file_path = Path(str(file_path).lstrip("/"))
            self.app.editor_service.on_file_open(str(file_path))
            self.after(150, lambda: self.goto_location(file_uri, line))
            return

        self.set_active_tab(file_uri)
        editor = self.get_editor_for_uri(file_uri)
        if editor and hasattr(editor, "goto_line"):
            editor.goto_line(line)
