import customtkinter as ctk
from .style import ICON_MAP


class CustomTreeView(ctk.CTkScrollableFrame):
    def __init__(self, master, command=None, app_reference=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="transparent")
        self.command = command
        self.app_reference = app_reference
        self.nodes = {}

    def update_tree(self, data):
        for widget in self.winfo_children():
            widget.destroy()
        self.nodes.clear()
        if data and data.get("children"):
            self._create_nodes(self, data, [])

    def _create_nodes(self, parent, data, prefix_parts):
        children = data.get("children", [])
        for i, child_data in enumerate(children):
            is_last = i == len(children) - 1
            node = self._TreeNode(self, parent, child_data, prefix_parts, is_last)
            node.pack(fill="x", pady=0, padx=0)
            node_key = (
                child_data.get("path")
                or f"{child_data.get('name')}-{child_data.get('lineno', i)}"
            )
            self.nodes[node_key] = node

    class _TreeNode(ctk.CTkFrame):
        def __init__(self, tree_view, parent, data, prefix_parts, is_last):
            super().__init__(parent, fg_color="transparent")
            self.tree_view = tree_view
            self.data = data
            self.prefix_parts = prefix_parts
            self.is_last = is_last
            self.is_expanded = False
            self.children_created = False
            self.is_expandable = (
                self.data["type"] == "folder" or "children" in self.data
            )

            self.main_frame = ctk.CTkFrame(
                self, fg_color="transparent", corner_radius=4
            )
            self.main_frame.pack(fill="x")

            all_bindable_widgets = [self, self.main_frame]

            self.main_frame.bind(
                "<Enter>", lambda e: self.main_frame.configure(fg_color="#333333")
            )
            self.main_frame.bind(
                "<Leave>", lambda e: self.main_frame.configure(fg_color="transparent")
            )

            self.prefix_labels = []
            for part in self.prefix_parts:
                lbl = ctk.CTkLabel(
                    self.main_frame, text=part, text_color="#555555", width=10
                )
                lbl.pack(side="left")
                all_bindable_widgets.append(lbl)

            self.branch_label = ctk.CTkLabel(
                self.main_frame, text="", text_color="#555555"
            )
            self.toggle_label = ctk.CTkLabel(self.main_frame, text="", width=10)
            self.icon_label = ctk.CTkLabel(
                self.main_frame, width=20, text="", font=("Segoe UI Emoji", 14)
            )
            self.name_label = ctk.CTkLabel(self.main_frame, text="", anchor="w")
            self.details_label = ctk.CTkLabel(
                self.main_frame, text="", text_color="#999999", anchor="w"
            )
            self.child_frame = ctk.CTkFrame(self, fg_color="transparent")

            self.update_data()
            self._bind_scroll_recursively(self)

            all_bindable_widgets.extend(
                [
                    self.branch_label,
                    self.toggle_label,
                    self.icon_label,
                    self.name_label,
                    self.details_label,
                ]
            )
            for widget in all_bindable_widgets:
                widget.bind("<Button-1>", self._on_click)
                if (
                    self.tree_view.app_reference
                    and hasattr(self.tree_view.app_reference, "sidebar")
                    and self.tree_view
                    == self.tree_view.app_reference.sidebar.file_explorer
                ):
                    widget.bind("<Button-3>", self._on_context)

        def update_data(self):
            for widget in self.main_frame.winfo_children():
                widget.pack_forget()

            for lbl in self.prefix_labels:
                lbl.pack(side="left")
            self.branch_label.configure(text="└── " if self.is_last else "├── ")
            self.branch_label.pack(side="left")
            self.toggle_label.configure(
                text=(
                    ("▶ " if not self.is_expanded else "▼ ")
                    if self.is_expandable
                    else "  "
                )
            )
            self.toggle_label.pack(side="left")
            icon_data = self._get_icon_data()
            self.icon_label.configure(
                text=icon_data["icon"], text_color=icon_data["color"]
            )
            self.icon_label.pack(side="left", padx=(0, 4))
            self.name_label.configure(text=self.data.get("name", "Unknown"))
            self.name_label.pack(side="left")
            details_text = self.data.get("details", "")
            self.details_label.configure(text=details_text)
            if details_text:
                self.details_label.pack(
                    side="left", padx=(10, 0), expand=True, anchor="e"
                )

        def _on_click(self, event):
            if self.tree_view.command:
                self.tree_view.command(self)

        def _on_context(self, event):

            if self.tree_view.app_reference and hasattr(
                self.tree_view.app_reference, "sidebar"
            ):
                self.tree_view.app_reference.sidebar._show_context_menu(event)

        def toggle_expansion(self):
            self.is_expanded = not self.is_expanded
            self.toggle_label.configure(text="▼ " if self.is_expanded else "▶ ")
            if self.is_expanded:
                if not self.children_created:
                    self._create_children()
                self.child_frame.pack(fill="x")
            else:
                self.child_frame.pack_forget()

        def set_children(self, children_data):
            self.data["children"] = children_data
            if not self.children_created:
                self._create_children()

        def _create_children(self):
            self.tree_view._create_nodes(
                self.child_frame,
                self.data,
                self.prefix_parts + ["│   " if not self.is_last else "    "],
            )
            self.children_created = True

        def _bind_scroll_recursively(self, widget):
            widget.bind("<MouseWheel>", self._on_mousewheel, add=True)
            for child in widget.winfo_children():
                self._bind_scroll_recursively(child)

        def _on_mousewheel(self, event):
            self.tree_view._parent_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units"
            )

        def _get_icon_data(self):
            node_type = self.data.get("type", "file")
            if node_type in ICON_MAP:
                return ICON_MAP[node_type]
            extension = self.data.get("name", "").split(".")[-1]
            return ICON_MAP.get(extension, ICON_MAP["default_file"])
