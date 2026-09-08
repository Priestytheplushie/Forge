import customtkinter as ctk
from .style import ICON_MAP


class ProblemsPanel(ctk.CTkFrame):
    """
    A high-performance, virtualized list for displaying problems.
    It only creates a small pool of widgets and reconfigures them on scroll.
    """

    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.command = command
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = ctk.CTkCanvas(
            self, background="#242424", highlightthickness=0, borderwidth=0
        )
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.item_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.canvas.create_window((0, 0), window=self.item_frame, anchor="nw")

        self.item_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        self.all_problems = []
        self.widget_pool = []
        self.pool_size = 30
        self.item_height = 24
        self.top_visible_index = 0
        self._create_widget_pool()

    def _create_widget_pool(self):
        for i in range(self.pool_size):
            row_frame = ctk.CTkFrame(
                self.item_frame,
                fg_color="transparent",
                corner_radius=4,
                height=self.item_height,
            )
            row_frame.pack(fill="x", expand=True)

            icon = ctk.CTkLabel(
                row_frame, text="", width=20, font=("Segoe UI Emoji", 14)
            )
            icon.pack(side="left", padx=(5, 10))

            message = ctk.CTkLabel(row_frame, text="", anchor="w")
            message.pack(side="left", fill="x", expand=True)

            details = ctk.CTkLabel(row_frame, text="", text_color="#999999", anchor="e")
            details.pack(side="right", padx=(10, 5))

            widget_set = {
                "frame": row_frame,
                "icon": icon,
                "message": message,
                "details": details,
                "data": None,
            }
            self.widget_pool.append(widget_set)

            def create_click_handler(ws):
                return lambda e: (
                    self.command(ws["data"]) if self.command and ws["data"] else None
                )

            handler = create_click_handler(widget_set)
            row_frame.bind("<Button-1>", handler)
            icon.bind("<Button-1>", handler)
            message.bind("<Button-1>", handler)
            details.bind("<Button-1>", handler)

    def update_items(self, problems):
        self.all_problems = problems
        self.canvas.yview_moveto(0)
        self._on_scroll()

    def _on_scroll(self, *args):
        total_height = len(self.all_problems) * self.item_height
        self.canvas.configure(
            scrollregion=(0, 0, self.item_frame.winfo_width(), total_height)
        )

        scroll_fraction = self.scrollbar.get()[0]
        self.top_visible_index = int(scroll_fraction * len(self.all_problems))

        self.item_frame.place(x=0, y=self.top_visible_index * self.item_height)

        self._redraw_visible_items()

    def _redraw_visible_items(self):
        for i in range(self.pool_size):
            item_index = self.top_visible_index + i
            widget_set = self.widget_pool[i]

            if item_index < len(self.all_problems):
                problem = self.all_problems[item_index]
                icon_data = ICON_MAP.get(problem["type"], ICON_MAP["default_file"])

                widget_set["icon"].configure(
                    text=icon_data["icon"], text_color=icon_data["color"]
                )
                widget_set["message"].configure(text=problem["name"])
                widget_set["details"].configure(text=problem["details"])
                widget_set["data"] = problem
                widget_set["frame"].pack(fill="x", expand=True)
            else:

                widget_set["frame"].pack_forget()
                widget_set["data"] = None

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        if self.winfo_containing(event.x_root, event.y_root) in [
            self,
            self.canvas,
            self.item_frame,
        ]:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            self._on_scroll()
