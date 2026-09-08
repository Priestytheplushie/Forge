import tkinter as tk
import re
import threading


class EditorActions:
    def __init__(self, editor_view):
        self.editor = editor_view
        self.doc = editor_view.doc
        self.canvas = editor_view.canvas

    def toggle_fold(self, line_num):

        internal_line = line_num - 1
        if internal_line in self.editor._folded_lines:
            self.editor._folded_lines.remove(internal_line)
        else:
            self.editor._folded_lines.add(internal_line)

        if internal_line in self.editor.folding_markers:
            state = self.editor.folding_markers[internal_line]["state"]
            self.editor.folding_markers[internal_line]["state"] = (
                "collapsed" if state == "expanded" else "expanded"
            )

        self.editor._schedule_redraw()

    def on_key_release(self, event):
        if self.doc.file_uri in self.editor.app.editor_service.open_documents:
            self.editor.app.editor_service.on_document_change(self.doc)
        if not self.editor.is_python_file:
            return
        nav_keys = {
            "Up",
            "Down",
            "Left",
            "Right",
            "Return",
            "Tab",
            "Escape",
            "Control_L",
            "Control_R",
            "Shift_L",
            "Shift_R",
            "Home",
            "End",
        }
        if event.keysym in nav_keys:
            return
        prefix, _ = self.editor.get_completion_prefix()
        if (
            self.editor.autocomplete_menu
            and self.editor.autocomplete_menu.winfo_exists()
        ):
            if prefix is None:
                self.editor.autocomplete_menu.close()
            else:
                self.editor.autocomplete_menu.filter(prefix)
        elif (
            prefix is not None
            and len(event.char) > 0
            and event.char.isprintable()
            and not event.char.isspace()
        ):
            self.request_completions()

    def apply_doc_change(self, text, start_line, start_col, end_line, end_col):
        self.editor._invalidate_cache_for_change(start_line)
        self.doc.apply_change(text, start_line, start_col, end_line, end_col)

    def on_mouse_press(self, event):
        self.canvas.focus_set()
        self.editor.cursor_pos = self.editor._coords_to_pos(event.x, event.y)
        self.editor.selection_start = self.editor.cursor_pos
        self.editor.cursor_goal_col = self.editor.cursor_pos[1]
        self.editor._schedule_redraw()

    def on_mouse_drag(self, event):
        self.editor.cursor_pos = self.editor._coords_to_pos(event.x, event.y)
        self.editor._schedule_redraw()

    def on_mouse_release(self, event=None):
        pass

    def on_double_click(self, event):
        line, col = self.editor._coords_to_pos(event.x, event.y)
        line_text = self.doc.lines[line]
        start = col
        end = col
        while start > 0 and (
            line_text[start - 1].isalnum() or line_text[start - 1] == "_"
        ):
            start -= 1
        while end < len(line_text) and (
            line_text[end].isalnum() or line_text[end] == "_"
        ):
            end += 1
        self.editor.selection_start = (line, start)
        self.editor.cursor_pos = (line, end)
        self.editor._schedule_redraw()
        return "break"

    def on_triple_click(self, event):
        line, _ = self.editor._coords_to_pos(event.x, event.y)
        self.editor.selection_start = (line, 0)
        self.editor.cursor_pos = (line, len(self.doc.lines[line]))
        self.editor._schedule_redraw()
        return "break"

    def on_key_press(self, event):
        if (
            self.editor.autocomplete_menu
            and self.editor.autocomplete_menu.winfo_exists()
        ):
            if event.keysym == "Down":
                self.editor.autocomplete_menu.move_selection(1)
                return "break"
            if event.keysym == "Up":
                self.editor.autocomplete_menu.move_selection(-1)
                return "break"
            if event.keysym in ("Return", "Tab"):
                self.editor.autocomplete_menu.select_current()
                return "break"
            if event.keysym == "Escape":
                self.editor.autocomplete_blocked_line = self.editor.cursor_pos[0]
                self.editor.autocomplete_menu.close()
                return "break"
        is_shift = (event.state & 0x1) != 0
        if (
            not self.editor.selection_start
            and is_shift
            and event.keysym in ("Up", "Down", "Left", "Right", "Home", "End")
        ):
            self.editor.selection_start = self.editor.cursor_pos
        elif not is_shift:
            self.editor.selection_start = None
        if event.keysym not in (
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
        ):
            self.editor._push_undo()
        start_pos, _ = self.editor._get_selection_range()
        if start_pos and event.keysym not in (
            "Up",
            "Down",
            "Left",
            "Right",
            "Shift_L",
            "Shift_R",
            "Home",
            "End",
        ):
            self.editor.cursor_pos = self.delete_selection()
        if event.keysym in ("Left", "Right", "Up", "Down"):
            self.handle_cursor_movement(event.keysym)
        else:
            self.handle_text_modification(event)
        self.editor._ensure_cursor_visible()
        self.editor._schedule_redraw()

    def handle_cursor_movement(self, keysym):
        line, col = self.editor.cursor_pos
        if keysym == "Left":
            if col > 0:
                col -= 1
            elif line > 0:
                line -= 1
                col = len(self.doc.lines[line])
        elif keysym == "Right":
            if col < len(self.doc.lines[line]):
                col += 1
            elif line < len(self.doc.lines) - 1:
                line += 1
                col = 0
        elif keysym == "Up":
            current_v_line_idx = self.editor._get_visual_line_idx_for_pos(line, col)
            if current_v_line_idx > 0:
                target_v_line = self.editor.renderer.visible_layout[
                    current_v_line_idx - 1
                ]
                col_in_chunk = self.editor._get_col_in_chunk(
                    target_v_line.text,
                    self.editor.cursor_goal_col - target_v_line.start_col,
                )
                line, col = (
                    target_v_line.doc_line_num,
                    target_v_line.start_col + col_in_chunk,
                )
        elif keysym == "Down":
            current_v_line_idx = self.editor._get_visual_line_idx_for_pos(line, col)
            if current_v_line_idx < len(self.editor.renderer.visible_layout) - 1:
                target_v_line = self.editor.renderer.visible_layout[
                    current_v_line_idx + 1
                ]
                col_in_chunk = self.editor._get_col_in_chunk(
                    target_v_line.text,
                    self.editor.cursor_goal_col - target_v_line.start_col,
                )
                line, col = (
                    target_v_line.doc_line_num,
                    target_v_line.start_col + col_in_chunk,
                )
        self.editor.cursor_pos = (line, col)
        if keysym in ("Left", "Right"):
            self.editor.cursor_goal_col = col

    def handle_text_modification(self, event):
        line, col = self.editor.cursor_pos
        current_line_text = self.doc.lines[line]
        if event.keysym == "BackSpace":
            if col > 0:
                self.apply_doc_change("", line, col - 1, line, col)
                self.editor.cursor_pos = (line, col - 1)
            elif line > 0:
                prev_line_len = len(self.doc.lines[line - 1])
                self.apply_doc_change("", line - 1, prev_line_len, line, 0)
                self.editor.cursor_pos = (line - 1, prev_line_len)
        elif event.keysym == "Delete":
            if col < len(current_line_text):
                self.apply_doc_change("", line, col, line, col + 1)
            elif line < len(self.doc.lines) - 1:
                self.apply_doc_change("", line, col, line + 1, 0)
        elif event.keysym == "Return":
            indent = re.match(r"^(\s*)", current_line_text).group(0)
            text_to_insert = "\n" + indent
            if current_line_text.rstrip().endswith(":"):
                text_to_insert += "    "
            self.apply_doc_change(text_to_insert, line, col, line, col)
            new_col = len(indent) + (
                4 if current_line_text.rstrip().endswith(":") else 0
            )
            self.editor.cursor_pos = (line + 1, new_col)
        elif event.keysym == "Tab":
            self.apply_doc_change("    ", line, col, line, col)
            self.editor.cursor_pos = (line, col + 4)
        elif len(event.char) > 0 and event.char.isprintable():
            self.apply_doc_change(event.char, line, col, line, col)
            self.editor.cursor_pos = (line, col + 1)
        self.editor.cursor_goal_col = self.editor.cursor_pos[1]

    def delete_selection(self):
        start_pos, end_pos = self.editor._get_selection_range()
        if start_pos:
            self.apply_doc_change(
                "", start_pos[0], start_pos[1], end_pos[0], end_pos[1]
            )
        self.editor.selection_start = None
        return start_pos

    def undo(self, event=None):
        self.editor._undo()
        return "break"

    def redo(self, event=None):
        self.editor._redo()
        return "break"

    def copy(self, event=None):
        selected_text = self.editor._get_selected_text()
        if selected_text:
            self.editor.clipboard_clear()
            self.editor.clipboard_append(selected_text)
        return "break"

    def cut(self, event=None):
        self.copy()
        start_pos = self.delete_selection()
        if start_pos:
            self.editor.cursor_pos = start_pos
            self.editor.selection_start = None
            self.editor._schedule_redraw()
        return "break"

    def paste(self, event=None):
        try:
            text = self.editor.clipboard_get()
            line, col = self.editor.cursor_pos
            self.apply_doc_change(text, line, col, line, col)
            lines = text.split("\n")
            if len(lines) == 1:
                self.editor.cursor_pos = (line, col + len(text))
            else:
                self.editor.cursor_pos = (line + len(lines) - 1, len(lines[-1]))
            self.editor.cursor_goal_col = self.editor.cursor_pos[1]
            self.editor._schedule_redraw()
        except tk.TclError:
            pass
        return "break"

    def select_all(self, event=None):
        self.editor.selection_start = (0, 0)
        self.editor.cursor_pos = (len(self.doc.lines) - 1, len(self.doc.lines[-1]))
        self.editor._schedule_redraw()
        return "break"

    def request_completions(self, event=None):
        if not self.editor.is_python_file:
            return "break"
        if (
            not self.editor.autocomplete_menu
            or not self.editor.autocomplete_menu.winfo_exists()
        ):
            from ..autocomplete import AutocompleteMenu

            self.editor.autocomplete_menu = AutocompleteMenu(
                self.editor, self.editor.winfo_toplevel()
            )
        line, char = self.editor.cursor_pos
        threading.Thread(
            target=self.editor._threaded_fetch_completions,
            args=(line, char),
            daemon=True,
        ).start()
        return "break"
