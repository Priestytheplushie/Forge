import customtkinter as ctk
from tkinter import messagebox
from tkinter.filedialog import asksaveasfilename
from pathlib import Path
from queue import Queue, Empty
import threading
import subprocess
import sys
import re
import os

from .document import Document


class EditorService:
    def __init__(self, app_instance):
        self.app = app_instance
        self.open_documents = {}

        self.output_textbox = None
        self.output_input_entry = None
        self.process_input_queue = Queue()

    def setup_output_panel(self, output_tab):
        self.output_textbox = ctk.CTkTextbox(
            output_tab,
            wrap="word",
            fg_color="#242424",
            font=("Consolas", 13),
            border_width=0,
        )
        self.output_textbox.grid(row=0, column=0, sticky="nsew")
        self.output_textbox.configure(state="disabled")
        self.output_input_entry = ctk.CTkEntry(
            output_tab, font=("Consolas", 13), border_width=0, fg_color="#333333"
        )
        self.output_input_entry.bind("<Return>", self._on_output_input)
        self._setup_output_tags()

    def _on_output_input(self, event):
        user_input = self.output_input_entry.get()
        self.process_input_queue.put(user_input)
        self._process_and_insert_output(user_input + "\n")
        self.output_input_entry.delete(0, "end")
        self.output_input_entry.grid_forget()
        self.output_textbox.focus_set()
        self.output_textbox.see("end")

    def run_current_file_in_output(self):
        active_file_path = self.app.editor_area.get_active_file_path()
        if not (active_file_path and self.app.environment_service.active_interpreter):
            return

        self.app.bottom_panel.set("OUTPUT")
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")

        command = [
            self.app.environment_service.active_interpreter,
            "-u",
            active_file_path,
        ]
        threading.Thread(
            target=self._execute_and_stream_output, args=(command,), daemon=True
        ).start()

    def _execute_and_stream_output(self, command):
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            cwd=self.app.project_service.project_path,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        def reader_thread(pipe):
            while True:
                try:
                    line = pipe.readline()
                    if not line:
                        break
                    self.app.after(0, self._process_and_insert_output, line)
                except:
                    break

        threading.Thread(
            target=reader_thread, args=[process.stdout], daemon=True
        ).start()

        def writer_thread(pipe):
            while process.poll() is None:
                try:
                    data = self.process_input_queue.get(timeout=0.1)
                    pipe.write(data + "\n")
                    pipe.flush()
                except Empty:
                    continue
                except (IOError, OSError):
                    break

        threading.Thread(
            target=writer_thread, args=[process.stdin], daemon=True
        ).start()

        return_code = process.wait()
        self.app.after(
            0,
            self.output_textbox.insert,
            "end",
            f"\n--- Process finished with exit code {return_code} ---\n",
        )
        self.app.after(0, self.output_input_entry.grid_forget)
        self.app.after(0, lambda: self.output_textbox.see("end"))

    def _process_and_insert_output(self, line):
        self.output_textbox.configure(state="normal")
        if not line.endswith(("\n", "\r\n")) and self.process_input_queue.empty():
            self.output_input_entry.grid(row=1, column=0, sticky="ew")
            self.output_input_entry.focus_set()
        else:
            self.output_input_entry.grid_forget()

        ansi_pattern = re.compile(r"\x1B\[(\d+(?:;\d+)*)?m")
        traceback_pattern = re.compile(r'^\s*File "(.+)", line (\d+), in (.+)')
        parts = ansi_pattern.split(line)
        current_tags = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                if not part:
                    continue
                match = traceback_pattern.match(part)
                if match:
                    file_path, line_num, func = match.groups()
                    tag_name = f"link-{file_path}-{line_num}"
                    self.output_textbox.tag_bind(
                        tag_name,
                        "<Button-1>",
                        lambda e, p=file_path, l=line_num: self.goto_location(
                            Path(p).as_uri(), int(l)
                        ),
                    )
                    self.output_textbox.tag_bind(
                        tag_name,
                        "<Enter>",
                        lambda e: self.output_textbox.config(cursor="hand2"),
                    )
                    self.output_textbox.tag_bind(
                        tag_name,
                        "<Leave>",
                        lambda e: self.output_textbox.config(cursor=""),
                    )
                    self.output_textbox.insert(
                        "end", part, ("traceback_link", tag_name) + tuple(current_tags)
                    )
                else:
                    self.output_textbox.insert("end", part, tuple(current_tags))
            else:
                if part is None or part == "0":
                    current_tags.clear()
                else:
                    for code in part.split(";"):
                        tag = f"ansi_{code}"
                        if tag not in current_tags:
                            current_tags.append(tag)
        self.output_textbox.see("end")
        self.output_textbox.configure(state="disabled")

    def _setup_output_tags(self):
        colors = {
            "30": "#2e3436",
            "31": "#cc0000",
            "32": "#4e9a06",
            "33": "#c4a000",
            "34": "#3465a4",
            "35": "#75507b",
            "36": "#06989a",
            "37": "#d3d7cf",
        }
        for code, color in colors.items():
            self.output_textbox.tag_config(f"ansi_{code}", foreground=color)
        bright_colors = {
            "90": "#555753",
            "91": "#ef2929",
            "92": "#8ae234",
            "93": "#fce94f",
            "94": "#729fcf",
            "95": "#ad7fa8",
            "96": "#34e2e2",
            "97": "#eeeeec",
        }
        for code, color in bright_colors.items():
            self.output_textbox.tag_config(f"ansi_{code}", foreground=color)
            if code.startswith("9"):
                bold_code = str(int(code) - 60)
                self.output_textbox.tag_config(f"ansi_1;{bold_code}", foreground=color)
        self.output_textbox.tag_config("ansi_4", underline=True)

    def on_file_open(self, file_path):

        file_uri = Path(file_path).as_uri()
        if file_uri in self.open_documents:
            self.app.editor_area.set_active_tab(file_uri)
            return
        doc = Document(file_path, file_uri)
        self.open_documents[file_uri] = doc
        editor_widget = self.app.editor_area.add_editor_tab(doc)
        editor_widget.show_loading()
        self.app.update_title(file_path)
        content_queue = Queue()
        threading.Thread(
            target=self._threaded_file_read,
            args=(file_path, content_queue),
            daemon=True,
        ).start()
        self.app.after(
            50, self._process_file_load_queue, editor_widget, doc, content_queue
        )

    def _threaded_file_read(self, file_path, queue):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            queue.put(content)
        except Exception as e:
            queue.put(f"Error opening file: {e}")
        finally:
            queue.put(None)

    def _process_file_load_queue(self, editor_widget, doc, queue):
        try:
            content = queue.get_nowait()
            if content is not None:
                doc.set_content(content)
                editor_widget.finish_loading()
            self.app.post_load_actions(doc)
        except Empty:
            self.app.after(20, self._process_file_load_queue, editor_widget, doc, queue)

    def save_file(self, doc):
        if not doc or doc.file_uri == "forge://welcome":
            return
        try:
            with open(doc.file_path, "w", encoding="utf-8") as f:
                f.write(doc.get_content())
            doc.mark_as_saved()
            self.app.editor_area.update_tab_dirty_status(doc)
        except Exception as e:
            messagebox.showerror(
                "Save Error", f"Could not save file {doc.file_path}:\n{e}"
            )

    def save_active_file(self):
        active_uri = self.app.editor_area.get_active_file_uri()
        if active_uri and active_uri in self.open_documents:
            self.save_file(self.open_documents[active_uri])

    def save_as_active_file(self):
        active_uri = self.app.editor_area.get_active_file_uri()
        if not (active_uri and active_uri in self.open_documents):
            return
        doc = self.open_documents[active_uri]
        new_path = asksaveasfilename(
            initialdir=os.path.dirname(doc.file_path),
            initialfile=os.path.basename(doc.file_path),
            defaultextension=".*",
            filetypes=[("All Files", "*.*")],
        )
        if new_path:
            old_uri = doc.file_uri
            doc.file_path = new_path
            doc.file_uri = Path(new_path).as_uri()
            self.save_file(doc)
            del self.open_documents[old_uri]
            self.open_documents[doc.file_uri] = doc
            self.app.editor_area.reopen_tab_with_new_path(old_uri, doc)
            self.app.sidebar.refresh_directory(os.path.dirname(new_path))

    def save_all_files(self):
        for doc in self.get_dirty_documents():
            self.save_file(doc)

    def get_dirty_documents(self):
        return [
            doc
            for doc in self.open_documents.values()
            if hasattr(doc, "is_dirty") and doc.is_dirty
        ]

    def close_all_documents(self):
        self.open_documents.clear()

    def goto_location(self, file_uri, line):

        if file_uri not in self.open_documents:
            file_path = Path(file_uri[8:])
            self.on_file_open(str(file_path))
            self.app.after(100, lambda: self.goto_location(file_uri, line))
            return

        self.app.editor_area.set_active_tab(file_uri)
        editor = self.app.editor_area.get_editor_for_uri(file_uri)
        if editor:
            editor.goto_line(line)
