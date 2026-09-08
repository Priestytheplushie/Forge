import customtkinter as ctk
from .base_widgets import StableToplevel


class Tooltip(StableToplevel):
    def __init__(self, master, text, bg_color="#323232"):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.wm_attributes("-topmost", True)
        except Exception:
            pass

        self.label = ctk.CTkLabel(
            self,
            text=text,
            justify="left",
            fg_color=bg_color,
            corner_radius=5,
            padx=10,
            pady=5,
        )
        self.label.pack()

    def show(self, event):
        x = event.x_root + 15
        y = event.y_root + 10
        self.geometry(f"+{x}+{y}")
        self.deiconify()

    def hide(self):
        self.withdraw()
