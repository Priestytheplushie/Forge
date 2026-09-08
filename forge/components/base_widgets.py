import customtkinter as ctk


class StableToplevel(ctk.CTkToplevel):
    """
    A more stable version of CTkToplevel that overrides the problematic,
    crashing iconbitmap call. All popups should inherit from this.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def iconbitmap(self, *args, **kwargs):
        """
        Overrides the parent method. Does nothing.
        This prevents the TclError: bitmap not defined crash.
        """
        pass
