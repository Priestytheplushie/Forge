import customtkinter as ctk
import tkinter as tk
import threading
import re
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.util import ClassNotFound
from pygments.styles import get_style_by_name

from .renderer import EditorRenderer
from .actions import EditorActions
from ..line_numbers import LineNumbers
from ..autocomplete import AutocompleteMenu
from ..tooltip import Tooltip
from .layout_manager import LineLayoutManager


class CodeEditor(ctk.CTkFrame):
    def __init__(self, master, document_model, app_callbacks, **kwargs):
        super().__init__(master, **kwargs)
        self.doc = document_model
        self.app = app_callbacks

        self.font = ctk.CTkFont(family="Consolas", size=14)
        self.line_height = self.font.metrics("linespace")
        self.y_padding = 2

        self.word_wrap = True

        self.top_line = 0
        self.cursor_pos = (0, 0)
        self.cursor_goal_col = 0
        self.selection_start = None
        self.x_offset = 0
        self.undo_stack = []
        self.redo_stack = []
        self._last_change_time = 0
        self._syntax_cache = {}
        self.diagnostics = []

        self.folding_markers = {}
        self._folded_lines = set()

        self._redraw_job = None
        self.is_loading = False

        self.autocomplete_menu = None
        self.tooltip = None
        self._hover_job = None
        self.autocomplete_blocked_line = None

        self._text_item_pool = []
        self._rect_item_pool = []
        self._line_item_pool = []

        self.is_python_file = self.doc.file_path.endswith((".py", ".pyw"))
        try:
            self.lexer = guess_lexer_for_filename(self.doc.file_path, "")
        except ClassNotFound:
            self.lexer = get_lexer_by_name("text")
        self.style = get_style_by_name("monokai")
        self.tag_colors = self.get_tag_colors()

        self._setup_widgets()

        self.layout_manager = LineLayoutManager(self.font)
        self.renderer = EditorRenderer(self)
        self.actions = EditorActions(self)

        self._bind_events()
        self._start_blinker()

        self.style_hint_codes = {
            "E101",
            "E111",
            "E112",
            "E113",
            "E114",
            "E115",
            "E116",
            "E117",
            "E201",
            "E202",
            "E203",
            "E211",
            "E221",
            "E222",
            "E223",
            "E224",
            "E225",
            "E226",
            "E227",
            "E228",
            "E231",
            "E241",
            "E242",
            "E251",
            "E252",
            "E261",
            "E262",
            "E265",
            "E266",
            "E271",
            "E272",
            "E273",
            "E274",
            "E275",
            "E301",
            "E302",
            "E303",
            "E304",
            "E305",
            "E306",
            "E401",
            "E402",
            "E501",
            "E502",
            "E701",
            "E702",
            "E703",
            "E704",
            "W191",
            "W291",
            "W292",
            "W293",
            "W391",
            "W503",
            "W504",
            "W505",
            "D100",
            "D101",
            "D102",
            "D103",
            "D104",
            "D105",
            "D106",
            "D107",
            "D200",
            "D201",
            "D202",
            "D203",
            "D204",
            "D205",
            "D206",
            "D207",
            "D208",
            "D209",
            "D210",
            "D211",
            "D212",
            "D213",
            "D300",
            "D301",
            "D302",
            "D400",
            "D401",
            "D402",
            "D403",
            "D404",
            "D405",
            "D406",
            "D407",
            "D408",
            "D409",
            "D410",
            "D411",
            "D412",
            "D413",
            "D414",
            "C0103",
            "C0114",
            "C0115",
            "C0116",
        }

    def _setup_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.line_numbers = LineNumbers(self, self, self.font)
        self.line_numbers.pack(side="left", fill="y")
        self.canvas = tk.Canvas(
            self,
            bg="#2b2b2b",
            highlightthickness=0,
            borderwidth=0,
            insertbackground="white",
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.v_scrollbar = ctk.CTkScrollbar(self, command=self.on_scrollbar_move)
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar = ctk.CTkScrollbar(
            self, orientation="horizontal", command=self.on_h_scrollbar_move
        )
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.canvas.configure(
            yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set
        )
        self.cursor_obj = self.canvas.create_line(0, 0, 0, 0, fill="white", width=2)
        self.canvas.focus_set()

    def _bind_events(self):
        self.canvas.bind("<Key>", self.actions.on_key_press)
        self.canvas.bind("<KeyRelease>", self.actions.on_key_release)
        self.canvas.bind("<Button-1>", self.actions.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.actions.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.actions.on_mouse_release)
        self.canvas.bind("<Double-Button-1>", self.actions.on_double_click)
        self.canvas.bind("<Triple-Button-1>", self.actions.on_triple_click)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<Leave>", self.on_mouse_leave)
        self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel, add=True)
        self.canvas.bind("<Control-s>", lambda e: self.app.save_active_file())

        key_map = {
            "<Control-z>": self.actions.undo,
            "<Control-y>": self.actions.redo,
            "<Control-c>": self.actions.copy,
            "<Control-x>": self.actions.cut,
            "<Control-v>": self.actions.paste,
            "<Control-a>": self.actions.select_all,
            "<Control-space>": self.actions.request_completions,
        }
        for key, func in key_map.items():
            self.canvas.bind(key, func)

    def finish_loading(self):
        self.is_loading = False
        self.doc.lines = self.doc.get_content().splitlines()
        if not self.doc.lines:
            self.doc.lines = [""]
        self._clear_syntax_cache()
        self.canvas.delete("all")
        self._text_item_pool = []
        self._rect_item_pool = []
        self._line_item_pool = []
        self.cursor_obj = self.canvas.create_line(0, 0, 0, 0, fill="white", width=2)
        self._push_undo()
        self._schedule_redraw()

    def show_loading(self):
        self.is_loading = True
        self.canvas.delete("all")
        self.canvas.create_text(
            100, 100, text="Loading file...", fill="white", font=self.font, anchor="nw"
        )

    def _schedule_redraw(self):
        if self._redraw_job:
            self.after_cancel(self._redraw_job)
        self._redraw_job = self.after(1, self.renderer.redraw)

    def on_scrollbar_move(self, *args):

        if args[0] == "moveto":
            fraction = float(args[1])
            self.top_line = int(fraction * len(self.doc.lines))
        elif args[0] == "scroll":
            count = int(args[1])
            self.top_line += count
        self._set_top_line(self.top_line)

    def _on_mouse_wheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) != self.canvas:
            return
        delta = -1 if event.delta > 0 else 1
        self._set_top_line(self.top_line + (delta * 3))

    def on_h_scrollbar_move(self, *args):
        if self.word_wrap:
            return
        max_line_width = max(
            (self.font.measure(line) for line in self.doc.lines), default=0
        )
        if args[0] == "moveto":
            self.x_offset = int(float(args[1]) * max_line_width)
        self._schedule_redraw()

    def _set_top_line(self, new_line):
        max_top = max(0, len(self.doc.lines) - 5)
        self.top_line = max(0, min(new_line, max_top))
        self._schedule_redraw()

    def _push_undo(self):
        import time

        current_time = time.time()
        if current_time - self._last_change_time > 0.5 or not self.undo_stack:
            self.undo_stack.append(
                {"lines": [l for l in self.doc.lines], "cursor": self.cursor_pos}
            )
        self._last_change_time = current_time
        self.redo_stack.clear()
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

    def _undo(self):
        if len(self.undo_stack) > 1:
            self._clear_syntax_cache()
            self.redo_stack.append(
                {"lines": [l for l in self.doc.lines], "cursor": self.cursor_pos}
            )
            self.undo_stack.pop()
            state = self.undo_stack[-1]
            self.doc.lines = [l for l in state["lines"]]
            self.cursor_pos = state["cursor"]
            self._schedule_redraw()

    def _redo(self):
        if self.redo_stack:
            self._clear_syntax_cache()
            state = self.redo_stack.pop()
            self.undo_stack.append(
                {"lines": [l for l in self.doc.lines], "cursor": self.cursor_pos}
            )
            self.doc.lines = state["lines"]
            self.cursor_pos = state["cursor"]
            self._schedule_redraw()

    def _on_resize(self, event=None):
        self._schedule_redraw()

    def _start_blinker(self):
        try:
            if self.focus_get() == self.canvas:
                state = self.canvas.itemcget(self.cursor_obj, "state")
                self.canvas.itemconfigure(
                    self.cursor_obj, state="hidden" if state == "normal" else "normal"
                )
            else:
                self.canvas.itemconfigure(self.cursor_obj, state="hidden")
        except tk.TclError:
            pass
        self.after(500, self._start_blinker)

    def _invalidate_cache_for_change(self, start_line):
        keys_to_delete = [k for k in self._syntax_cache.keys() if k >= start_line]
        for k in keys_to_delete:
            del self._syntax_cache[k]

    def _clear_syntax_cache(self):
        self._syntax_cache.clear()

    def _get_selection_range(self):
        if self.selection_start and self.cursor_pos != self.selection_start:
            return min(self.selection_start, self.cursor_pos), max(
                self.selection_start, self.cursor_pos
            )
        return None, None

    def _get_selected_text(self):
        start_pos, end_pos = self._get_selection_range()
        if not start_pos:
            return ""
        start_line, start_col = start_pos
        end_line, end_col = end_pos
        if start_line == end_line:
            return self.doc.lines[start_line][start_col:end_col]
        text = self.doc.lines[start_line][start_col:]
        for i in range(start_line + 1, end_line):
            text += "\n" + self.doc.lines[i]
        text += "\n" + self.doc.lines[end_line][:end_col]
        return text

    def get_tag_colors(self):
        colors = {}
        for token, style in self.style:
            if style["color"]:
                colors[str(token)] = f"#{style['color']}"
        return colors

    def get_completion_prefix(self):
        line, char = self.cursor_pos
        line_text = self.doc.lines[line][:char]
        match = re.search(r"[\w\.]*$", line_text)
        return (match.group(0), None) if match else (None, None)

    def _threaded_fetch_completions(self, line, char):
        ast_items = self.app.ast_parser.get_completions(
            self.doc.get_content(), line + 1
        )
        self.after(0, self._update_completions_ui, ast_items)
        self.app.lsp_client.get_completions(
            self.doc.file_uri, line, char, self.handle_lsp_completions
        )

    def handle_lsp_completions(self, lsp_items_raw):
        lsp_items = [
            {"label": item.get("label"), "kind": item.get("kind")}
            for item in lsp_items_raw
        ]
        self.after(0, self._update_completions_ui, lsp_items)

    def _update_completions_ui(self, items):
        if not items:
            return
        if not self.autocomplete_menu or not self.autocomplete_menu.winfo_exists():
            self.autocomplete_menu = AutocompleteMenu(self, self.winfo_toplevel())
        self.autocomplete_menu.update_items(items)
        if self.autocomplete_menu.has_items():
            prefix, _ = self.get_completion_prefix()
            if not self.autocomplete_menu.winfo_viewable():
                self.autocomplete_menu.show()
            self.autocomplete_menu.filter(prefix or "")

    def on_autocomplete_close(self):
        self.autocomplete_menu = None
        self.canvas.focus_set()

    def on_completion_inserted(self, selection_str):
        prefix, _ = self.get_completion_prefix()
        prefix_len = len(prefix) if prefix else 0
        line, col = self.cursor_pos
        self.actions.apply_doc_change(selection_str, line, col - prefix_len, line, col)
        self.cursor_pos = (line, col - prefix_len + len(selection_str))
        self.cursor_goal_col = self.cursor_pos[1]
        self._schedule_redraw()
        self.canvas.focus_set()

    def _coords_to_pos(self, x, y):

        v_line_idx = (
            self.top_line + int((y - self.y_padding) / self.line_height)
            if self.line_height > 0
            else 0
        )
        return self.renderer.screen_to_doc_pos(x, y)

    def _get_visual_line_idx_for_pos(self, doc_line, doc_col):
        return self.renderer.get_visual_line_idx_for_pos(doc_line, doc_col)

    def get_cursor_screen_coords(self):
        return self.renderer.get_cursor_screen_coords()

    def goto_line(self, line_num):
        doc_line = line_num - 1
        self.cursor_pos = (doc_line, 0)
        self.selection_start = None
        self._set_top_line(max(0, doc_line - 5))
        self.canvas.focus_set()

    def _ensure_cursor_visible(self):

        pass

    def _get_col_in_chunk(self, chunk_text, goal_col_in_chunk):
        return min(len(chunk_text), max(0, goal_col_in_chunk))

    def on_mouse_leave(self, event=None):
        if self._hover_job:
            self.after_cancel(self._hover_job)
            self._hover_job = None
        if self.tooltip:
            self.tooltip.hide()

    def _on_mouse_motion(self, event):
        if self._hover_job:
            self.after_cancel(self._hover_job)
            self._hover_job = None
        if self.tooltip:
            self.tooltip.hide()
        self._hover_job = self.after(300, lambda: self._show_tooltip_at_event(event))

    def _show_tooltip_at_event(self, event):
        line, col = self._coords_to_pos(event.x, event.y)
        hovered_diags = [
            d
            for d in self.diagnostics
            if d["range"]["start"]["line"] == line
            and d["range"]["start"]["character"]
            <= col
            <= d["range"]["end"]["character"]
        ]
        if hovered_diags:
            diag = min(hovered_diags, key=lambda d: d.get("severity", 4))
            sev = diag.get("severity", 4)
            code = diag.get("code")
            msg = diag.get("message", "")
            is_style = (
                any(str(code).startswith(sc) for sc in self.style_hint_codes)
                or "line too long" in msg
                or "unused" in msg
            )
            sev_map = {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}
            sev_text = "Style Hint" if is_style else sev_map.get(sev, "Hint")
            message = f"{sev_text}: {msg}" + (f" ({code})" if code else "")
            if self.tooltip:
                self.tooltip.destroy()
            self.tooltip = Tooltip(self, message)
            self.tooltip.show(event)
            return

    def apply_diagnostics(self, diagnostics):
        self.diagnostics = diagnostics
        self._schedule_redraw()

    def update_folding_markers(self, symbols):
        self.folding_markers.clear()
        for symbol in symbols:
            if symbol["type"] in ["class", "function", "method"]:

                start_line, end_line = symbol["lineno"], symbol.get(
                    "end_lineno", symbol["lineno"]
                )
                if end_line > start_line:

                    self.folding_markers[start_line - 1] = {
                        "state": "expanded",
                        "end_lineno": end_line - 1,
                    }
        self._schedule_redraw()
