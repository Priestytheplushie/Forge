import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        self.configure(height=25, corner_radius=0)

        ctk.CTkLabel(self, text="Ln 1, Col 1", padx=10).pack(side="right")

        self.python_version_button = ctk.CTkButton(
            self,
            text="Discovering Python...",
            corner_radius=0,
            fg_color="transparent",
            hover_color="#4a4a4a",
            height=25,
            command=self.master.select_interpreter,
        )
        self.python_version_button.pack(side="right", padx=10)

        self.ai_status_label = ctk.CTkLabel(self, text="✨ Idle", padx=10)
        self.ai_status_label.pack(side="right")

        self.git_branch_label = ctk.CTkLabel(self, text=" main", padx=10)
        self.git_branch_label.pack(side="left")

    def update_python_version(self, version_string):
        """Updates the text on the Python version button."""
        short_version = version_string.replace("Python ", "")
        self.python_version_button.configure(text=f"🐍 {short_version}")
