import customtkinter as ctk
from tkinter.filedialog import askdirectory
import os


class MoveDialog(ctk.CTkToplevel):
    def __init__(self, parent, item_path):
        super().__init__(parent)
        self.transient(parent)
        self.title("Move Item")
        self.geometry("400x150")

        self.item_name = os.path.basename(item_path)
        self.result = None

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(padx=20, pady=20, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            main_frame, text=f"Move '{self.item_name}' to a new location:"
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        self.path_entry = ctk.CTkEntry(main_frame, width=300)
        self.path_entry.grid(row=1, column=0, pady=10, sticky="ew")
        self.path_entry.insert(0, os.path.dirname(item_path))

        browse_button = ctk.CTkButton(
            main_frame, text="Browse...", width=80, command=self._browse
        )
        browse_button.grid(row=1, column=1, padx=(10, 0))

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))

        ok_button = ctk.CTkButton(button_frame, text="Move", command=self._ok)
        ok_button.pack(side="left", padx=5)

        cancel_button = ctk.CTkButton(
            button_frame, text="Cancel", fg_color="#555555", command=self.destroy
        )
        cancel_button.pack(side="left")

        self.path_entry.focus_set()
        self.grab_set()
        self.wait_window()

    def _browse(self):
        initial_dir = self.path_entry.get() or "/"
        new_path = askdirectory(
            title="Select Destination Folder", initialdir=initial_dir
        )
        if new_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, new_path)

    def _ok(self):
        self.result = self.path_entry.get()
        self.destroy()

    def get_input(self):
        return self.result
