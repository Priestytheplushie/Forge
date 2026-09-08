import customtkinter as ctk
import tkinter as tk
import subprocess
import threading
import os
import sys
import shutil
import re
from pathlib import Path
from ..services.traceback_handler import TracebackHandler


class ForgeTerminal(ctk.CTkFrame):
    def __init__(self, master, app_reference, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app_reference
        self.cwd = self.app.project_service.project_path

        self.text = ctk.CTkTextbox(
            self,
            wrap="word",
            font=("Consolas", 14),
            text_color="#CCCCCC",
            fg_color="#1E1E1E",
            border_width=0,
        )
        self.text.pack(fill="both", expand=True)

        self._setup_tags_and_bindings()
        self.traceback_handler = TracebackHandler()
        self.process = None

        self.input_start_mark = "input_start"
        self.text.mark_set(self.input_start_mark, "1.0")
        self.text.mark_gravity(self.input_start_mark, "left")

        self.after(100, self._start_process)

    def _start_process(self):
        self._insert_welcome_message()
        threading.Thread(
            target=self._execute_command_in_thread, args=(None,), daemon=True
        ).start()

    def _setup_tags_and_bindings(self):
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Button-3>", self._on_right_click)

        self.text.tag_config("prompt_venv", foreground="#66FF66")
        self.text.tag_config("prompt_path", foreground="#569CD6")
        self.text.tag_config("stderr_tag", foreground="#FFB8B8")
        self.text.tag_config("link", foreground="#4FC1FF", underline=True)
        self.text.tag_bind(
            "link", "<Enter>", lambda e: self.text.configure(cursor="hand2")
        )
        self.text.tag_bind("link", "<Leave>", lambda e: self.text.configure(cursor=""))
        self.text.tag_config("h2", foreground="#FFD700")
        self.text.tag_config("h3", foreground="#d3d7cf")
        self.text.tag_config("info", foreground="#cccccc")
        self.text.tag_config("run_button", foreground="#a6e22e")
        self.text.tag_config("command_style", foreground="#ce9178")
        self.text.tag_config("error_name", foreground="#F44747")
        self.text.tag_config("error_message", foreground="#F44747")
        self.text.tag_config("h1", foreground="#F44747")

    def _on_key(self, event):
        if event.state & 4 and event.keysym.lower() == "c":
            return
        try:
            sel_start = self.text.index("sel.first")
            if self.text.compare(sel_start, "<", self.input_start_mark):
                if event.keysym not in ("Left", "Right", "Up", "Down", "Home", "End"):
                    return "break"
        except tk.TclError:
            if self.text.index("insert") < self.text.index(self.input_start_mark):
                self.text.mark_set("insert", "end")

        if (
            self.text.index("insert") == self.text.index(self.input_start_mark)
            and event.keysym == "BackSpace"
        ):
            return "break"

        if event.keysym == "Return":
            self._on_enter_key()
            return "break"

    def _on_right_click(self, event):
        try:
            self.text.insert("insert", self.clipboard_get())
        except:
            pass
        return "break"

    def _on_enter_key(self):
        command = self.text.get(self.input_start_mark, "end").strip()
        self.text.insert("end", "\n")
        self.text.configure(state="disabled")
        if self.process and self.process.stdin:
            if command:
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
            else:
                self.process.stdin.write("\n")
                self.process.stdin.flush()

    def write(self, text_data):
        self.text.configure(state="normal")
        items_to_write = []
        if isinstance(text_data, list):
            items_to_write.extend(text_data)
        elif isinstance(text_data, dict):
            items_to_write.append(text_data)
        else:
            items_to_write.append({"type": "raw", "content": text_data})

        for item in items_to_write:
            if item["type"] == "raw":
                self.text.insert("end", item["content"])
            elif item["type"] == "pretty_traceback":
                self._render_pretty_traceback(item)

        self.text.see("end")
        self.text.mark_set(self.input_start_mark, self.text.index("end-1c"))

    def show_prompt(self):
        self.text.configure(state="normal")
        self.text.see("end")
        self.text.focus_set()

    def _execute_command_in_thread(self, initial_command):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        shell_cmd = (
            ["powershell.exe", "-NoLogo", "-NoExit"]
            if sys.platform == "win32"
            else ["bash", "-i"]
        )
        self.process = subprocess.Popen(
            shell_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.cwd,
            env=env,
            bufsize=1,
            universal_newlines=True,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
            encoding="utf-8",
            errors="replace",
        )
        if initial_command:
            self.process.stdin.write(initial_command + "\n")
            self.process.stdin.flush()
        else:
            self.process.stdin.write("\n")
            self.process.stdin.flush()

        if self.process.stdout:
            for line in iter(self.process.stdout.readline, ""):
                processed_data = self.traceback_handler.process_line(line)
                self.after(0, self.write, processed_data or line)

        self.after(0, self.show_prompt)

    def run_command(self, command):
        self.text.configure(state="normal")
        self.text.mark_set("insert", "end")
        self.text.insert("end", f"{command}\n")

        if self.process and self.process.stdin:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        else:
            threading.Thread(
                target=self._execute_command_in_thread, args=(command,), daemon=True
            ).start()

    def _insert_welcome_message(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Welcome to the Forge Intelligent Terminal!\n", ("h2",))
        self.text.insert("end", "- Type a command like ", ("info",))
        self.text.insert("end", "dir", ("command_style",))
        self.text.insert("end", " and press Enter.\n", ("info",))
        self.text.insert("end", "- Run the active file with the ", ("info",))
        self.text.insert("end", "▶ ", ("run_button",))
        self.text.insert("end", "button.\n", ("info",))
        self.text.insert(
            "end", "- Python tracebacks are automatically parsed and made ", ("info",)
        )
        self.text.insert("end", "clickable", ("link",))
        self.text.insert("end", ".\n\n", ("info",))
        self.text.configure(state="disabled")

    def _render_pretty_traceback(self, tb_data):
        self.text.configure(state="normal")
        self.text.insert("end", "\n--- 🔴 Traceback ---\n", ("h1",))
        if tb_data.get("explanation"):
            self.text.insert("end", f"{tb_data['explanation']['title']}\n", ("h2",))
            self.text.insert(
                "end", f"{tb_data['explanation']['explanation']}\n\n", ("info",)
            )
        for frame in tb_data.get("lines", []):
            path = Path(frame["file_path"])
            file_name = path.name
            tag_name = f"link-{frame['file_path']}-{frame['line_num']}"
            link_text = f"  File \"{file_name}\", line {frame['line_num']}"
            self.text.insert("end", link_text, ("link", tag_name))
            self.text.tag_bind(
                tag_name,
                "<Button-1>",
                lambda e, p=path.as_uri(), l=frame[
                    "line_num"
                ]: self.app.editor_service.goto_location(p, l),
            )
            self.text.insert("end", f", in {frame['context']}\n")
        if tb_data.get("error"):
            self.text.insert("end", f"\n{tb_data['error']['name']}:", ("error_name",))
            self.text.insert(
                "end", f" {tb_data['error']['message']}\n", ("error_message",)
            )
        if tb_data.get("explanation"):
            self.text.insert(
                "end", f"\n💡 Tip: {tb_data['explanation']['example']}\n", ("info",)
            )
        self.text.configure(state="disabled")
