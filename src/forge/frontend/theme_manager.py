import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal


class ThemeManager(QObject):
    """Loads, manages, and applies editor themes."""

    theme_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.themes_dir = Path(__file__).resolve().parent / "assets" / "themes"
        self.themes = {}
        self.current_theme_name = "Forge Dark"
        self._load_themes()

    def _load_themes(self):
        """Scans the themes directory and loads all valid .json theme files."""
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file, "r", encoding="utf-8") as f:
                    theme_data = json.load(f)
                    theme_name = theme_data.get("name")
                    if theme_name:
                        self.themes[theme_name] = theme_data
                        print(f"[ThemeManager] Loaded theme: {theme_name}")
            except (IOError, json.JSONDecodeError) as e:
                print(
                    f"[ThemeManager] Failed to load theme file {theme_file.name}: {e}"
                )

    def get_theme_names(self) -> list[str]:
        """Returns a sorted list of available theme names."""
        return sorted(self.themes.keys())

    def get_current_theme_data(self) -> dict:
        """Returns the data for the currently active theme."""
        return self.themes.get(self.current_theme_name, {})

    def set_theme(self, name: str):
        """Sets the active theme and emits a signal if it changed."""
        if name in self.themes and name != self.current_theme_name:
            self.current_theme_name = name
            print(f"[ThemeManager] Switched theme to: {name}")
            self.theme_changed.emit(self.get_current_theme_data())
