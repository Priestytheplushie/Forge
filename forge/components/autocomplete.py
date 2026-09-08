import customtkinter as ctk
from .base_widgets import StableToplevel
from .style import KIND_MAP_COLOR


class AutocompleteMenu(StableToplevel):
    def __init__(self, master_editor, app_window):
        super().__init__(master_editor)
        self.editor = master_editor
        self.font = master_editor.font

        self.withdraw()
        self.overrideredirect(True)
        try:
            self.wm_attributes("-topmost", True)
        except Exception:
            pass

        self.configure(fg_color="#252526", border_width=1, border_color="#454545")

        self.listbox = ctk.CTkTextbox(
            self,
            fg_color="#252526",
            border_width=0,
            corner_radius=0,
            text_color="#cccccc",
            font=self.font,
            border_spacing=0,
            padx=4,
            pady=2,
        )
        self.listbox.pack(fill="both", expand=True)
        self.listbox.configure(state="disabled")

        self.listbox.tag_config("selected", background="#094771")
        self.listbox.tag_config("match", foreground="#569cd6")
        for kind, info in KIND_MAP_COLOR.items():
            self.listbox.tag_config(f"kind_{kind}", foreground=info["color"])

        self.full_completion_list = []
        self.filtered_list = []
        self.current_selection_index = 0
        self.item_height = self.font.metrics("linespace") + 2

        self.listbox.bind("<Button-1>", self.on_click)

    def has_items(self):
        return bool(self.full_completion_list)

    def update_items(self, items):
        current_items = {item["label"]: item for item in self.full_completion_list}
        new_items = {item["label"]: item for item in items if item.get("label")}
        current_items.update(new_items)
        self.full_completion_list = sorted(
            list(current_items.values()), key=lambda x: x.get("label", "").lower()
        )

    def filter(self, text):
        self.filtered_list = (
            [
                item
                for item in self.full_completion_list
                if item.get("label", "").lower().startswith(text.lower())
            ]
            if text
            else self.full_completion_list
        )
        if not self.filtered_list:
            self.close()
            return

        self.current_selection_index = 0
        self._redraw(text)

    def _redraw(self, prefix=""):
        self.listbox.configure(state="normal")
        self.listbox.delete("1.0", "end")

        prefix_len = len(prefix)

        for i, item in enumerate(self.filtered_list):
            kind_info = KIND_MAP_COLOR.get(item.get("kind"), KIND_MAP_COLOR["default"])
            icon = kind_info["icon"]
            label = item.get("label", "")

            line_text = f"{icon}  {label}\n"
            self.listbox.insert(f"{i+1}.0", line_text)

            icon_start = f"{i+1}.0"
            icon_end = f"{icon_start}+{len(icon)}c"
            self.listbox.tag_add(
                f"kind_{item.get('kind', 'default')}", icon_start, icon_end
            )

            if prefix_len > 0 and label.lower().startswith(prefix.lower()):
                match_start_char_index = len(icon) + 2
                match_start = f"{i+1}.{match_start_char_index}"
                match_end = f"{match_start}+{prefix_len}c"
                self.listbox.tag_add("match", match_start, match_end)

        self.listbox.configure(state="disabled")

        try:
            current_geo = self.geometry().split("+")
            current_x, current_y = current_geo[1], current_geo[2]
            new_height = min(len(self.filtered_list), 10) * self.item_height + 8
            self.geometry(f"300x{new_height}+{current_x}+{current_y}")
        except (IndexError, ValueError):
            self.show()

        self.activate(0)

    def show(self):
        if self.winfo_viewable():
            return

        self.filter("")
        if not self.filtered_list:
            return

        cursor_x, cursor_y = self.editor.get_cursor_screen_coords()

        prefix, _ = self.editor.get_completion_prefix()
        prefix = prefix or ""
        prefix_width = self.editor.font.measure(prefix)

        final_x = self.editor.winfo_rootx() + cursor_x - prefix_width - 10
        final_y = self.editor.winfo_rooty() + cursor_y + self.editor.line_height + 2

        height = min(len(self.filtered_list), 10) * self.item_height + 8
        self.geometry(f"300x{height}+{int(final_x)}+{int(final_y)}")

        self.deiconify()
        self.lift()
        self.activate(0)

    def activate(self, index):
        self.listbox.tag_remove("selected", "1.0", "end")
        self.current_selection_index = index
        if 0 <= self.current_selection_index < len(self.filtered_list):
            line_start = f"{self.current_selection_index + 1}.0"
            line_end = f"{self.current_selection_index + 1}.end"
            self.listbox.tag_add("selected", line_start, line_end)
            self.listbox.see(line_start)

    def move_selection(self, delta):
        new_index = self.current_selection_index + delta
        if 0 <= new_index < len(self.filtered_list):
            self.activate(new_index)

    def on_click(self, event):
        index_str = self.listbox.index(f"@{event.x},{event.y}")
        line_num = int(index_str.split(".")[0]) - 1
        if 0 <= line_num < len(self.filtered_list):
            self.current_selection_index = line_num
            self.select_current()

    def select_current(self):
        if 0 <= self.current_selection_index < len(self.filtered_list):
            item = self.filtered_list[self.current_selection_index]
            self.editor.on_completion_inserted(item.get("label", ""))
            self.close()

    def close(self):
        if self.winfo_exists():
            self.editor.on_autocomplete_close()
            self.destroy()
