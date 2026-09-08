import customtkinter as ctk


class ActivityBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(width=50, fg_color="#2b2b2b", corner_radius=0)

        icons = ["📄", "🔍", "", "🐞", "✨"]
        tooltips = ["Explorer", "Search", "Source Control", "Run and Debug", "Forge AI"]

        for icon, tooltip in zip(icons, tooltips):
            btn = ctk.CTkButton(
                self,
                text=icon,
                width=50,
                height=50,
                font=("Segoe UI Emoji", 20),
                fg_color="transparent",
                hover_color="#444444",
                corner_radius=0,
            )
            btn.pack(pady=2)
