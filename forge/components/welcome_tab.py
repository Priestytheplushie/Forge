import customtkinter as ctk


class WelcomeTab(ctk.CTkFrame):
    def __init__(self, master, callbacks):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.grid(row=0, column=0)

        header_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        header_frame.pack(pady=(0, 40))
        ctk.CTkLabel(header_frame, text="🔥", font=("Segoe UI Emoji", 50)).pack(pady=10)
        ctk.CTkLabel(
            header_frame, text="Forge IDE", font=("Segoe UI", 28, "bold")
        ).pack(pady=(0, 5))
        ctk.CTkLabel(
            header_frame,
            text="Your workspace is ready.",
            font=("Segoe UI", 16),
            text_color="#999999",
        ).pack()

        content_grid = ctk.CTkFrame(main_container, fg_color="transparent")
        content_grid.pack(fill="x")
        content_grid.grid_columnconfigure((0, 2), weight=1)

        start_frame = ctk.CTkFrame(content_grid, fg_color="transparent")
        start_frame.grid(row=0, column=0, sticky="nsew", padx=20)
        ctk.CTkLabel(
            start_frame,
            text="START",
            font=("Segoe UI", 13, "bold"),
            text_color="#999999",
            anchor="w",
        ).pack(fill="x", pady=(0, 5))
        ctk.CTkButton(
            start_frame,
            text="New File...",
            anchor="w",
            fg_color="transparent",
            text_color="#3498db",
            hover=False,
            command=callbacks["dummy_command"],
        ).pack(fill="x")
        ctk.CTkButton(
            start_frame,
            text="Go to File...",
            anchor="w",
            fg_color="transparent",
            text_color="#3498db",
            hover=False,
            command=callbacks["dummy_command"],
        ).pack(fill="x")
        ctk.CTkButton(
            start_frame,
            text="Show All Commands...",
            anchor="w",
            fg_color="transparent",
            text_color="#3498db",
            hover=False,
            command=callbacks["dummy_command"],
        ).pack(fill="x")

        recent_frame = ctk.CTkFrame(content_grid, fg_color="transparent")
        recent_frame.grid(row=0, column=1, sticky="nsew", padx=20)
        ctk.CTkLabel(
            recent_frame,
            text="RECENT",
            font=("Segoe UI", 13, "bold"),
            text_color="#999999",
            anchor="w",
        ).pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(
            recent_frame, text="No recent folders", text_color="#777777", anchor="w"
        ).pack(fill="x")

        help_frame = ctk.CTkFrame(content_grid, fg_color="transparent")
        help_frame.grid(row=0, column=2, sticky="nsew", padx=20)
        ctk.CTkLabel(
            help_frame,
            text="HELP",
            font=("Segoe UI", 13, "bold"),
            text_color="#999999",
            anchor="w",
        ).pack(fill="x", pady=(0, 5))
        ctk.CTkButton(
            help_frame,
            text="View Documentation",
            anchor="w",
            fg_color="transparent",
            text_color="#3498db",
            hover=False,
            command=callbacks["dummy_command"],
        ).pack(fill="x")
