import customtkinter as ctk
from tkinter import ttk


class OutlineView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master_app = master.master

        self.tree = ttk.Treeview(self, show="tree")
        self.tree.pack(fill="both", expand=True, pady=(5, 0))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def on_select(self, event=None):
        if not self.tree.selection():
            return
        selected_item_id = self.tree.selection()[0]

        values = self.tree.item(selected_item_id, "values")
        if not values:
            return

        lineno = values[0]

        self.master_app.editor_area.goto_active_editor_line(int(lineno))

    def update_symbols(self, symbols):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._add_symbols_recursively(symbols, "")

    def _add_symbols_recursively(self, symbols, parent_id):
        icon_map = {"class": "🔸", "function": "🔹"}

        for symbol in symbols:
            icon = icon_map.get(symbol["type"], "▫️")
            item_text = f" {icon} {symbol['name']}"
            child_id = self.tree.insert(
                parent_id, "end", text=item_text, values=(symbol["lineno"],), open=True
            )
            if symbol["children"]:
                self._add_symbols_recursively(symbol["children"], child_id)
