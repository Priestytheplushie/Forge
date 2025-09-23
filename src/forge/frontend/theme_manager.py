import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from .assets.icon_map import get_themed_icon


class ThemeManager(QObject):
    """Loads, manages, and applies editor and UI themes."""

    theme_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        themes_asset_path = Path(__file__).resolve().parent / "assets" / "themes"
        self.themes_dir = themes_asset_path
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
        """Sets the active theme, applies it globally, and emits a signal."""
        if name in self.themes:
            self.current_theme_name = name
            theme_data = self.get_current_theme_data()
            self._apply_global_stylesheet(theme_data)
            self.theme_changed.emit(theme_data)

    def _adjust_color(self, color_str, factor):
        """Lightens or darkens a color by a factor."""
        color = QColor(color_str)
        h, s, l, a = color.getHsl()
        l = min(max(0, int(l * factor)), 255)
        color.setHsl(h, s, l, a)
        return color.name()

    def _apply_global_stylesheet(self, theme_data: dict):
        """Generates and applies a Qt Style Sheet from the theme data."""
        colors = theme_data.get("colors", {})

        bg = colors.get("editor.background", "#282c34")
        fg = colors.get("editor.foreground", "#abb2bf")

        base = colors.get("sideBar.background", self._adjust_color(bg, 1.1))
        border = colors.get("sideBar.border", self._adjust_color(base, 1.2))
        activity_bar_bg = colors.get(
            "activityBar.background", self._adjust_color(base, 0.95)
        )

        highlight = colors.get("list.activeSelectionBackground", "#3e4451")
        highlight_fg = colors.get("list.activeSelectionForeground", "#ffffff")
        inactive_highlight = colors.get("list.inactiveSelectionBackground", "#3a3f4b")
        inactive_fg = colors.get("list.inactiveSelectionForeground", "#d8deee")

        close_icon_path = get_themed_icon("x.svg", fg).as_posix()

        stylesheet = f"""
            QMainWindow, QDialog, QFrame {{
                background-color: {base};
                color: {fg};
            }}
            #ActivityBar {{
                background-color: {activity_bar_bg};
            }}
            QMainWindow::separator {{
                background-color: {border};
                width: 1px;
                height: 1px;
            }}
            QDockWidget {{
                background-color: {bg};
                color: {fg};
            }}
            QDockWidget::title {{
                background-color: {base};
                padding: 4px;
            }}
            QMenuBar {{
                background-color: {bg};
                color: {fg};
            }}
            QMenuBar::item:selected {{
                background-color: {highlight};
            }}
            QMenu {{
                background-color: {base};
                color: {fg};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{
                background-color: {highlight};
            }}
            QTabWidget::pane {{
                border-top: 1px solid {border};
            }}
            QTabBar::tab {{
                background-color: {base};
                color: {fg};
                padding: 5px 10px;
                border: 1px solid transparent;
            }}
            QTabBar::tab:selected {{
                background-color: {bg};
            }}
            QTabBar::tab:!selected {{
                background-color: {base};
                margin-top: 1px;
            }}
            QTabBar::close-button {{
                /* Revert to default icon, which is theme-aware */
            }}
            QTabBar::close-button:hover {{
                background-color: {highlight};
            }}
            QStatusBar {{
                background-color: {base};
                color: {fg};
                border-top: 1px solid {border};
            }}
            QTreeView, QListView, QListWidget {{
                background-color: {bg};
                color: {fg};
                border: none;
                alternate-background-color: {base};
            }}
            QTreeView::item:selected, QListView::item:selected, QListWidget::item:selected {{
                background-color: {highlight};
                color: {highlight_fg};
            }}
            QTreeView::item:selected:!active, QListView::item:selected:!active, QListWidget::item:selected:!active {{
                background-color: {inactive_highlight};
                color: {inactive_fg};
            }}
            QHeaderView::section {{
                background-color: {base};
                border: 1px solid {border};
                padding: 4px;
            }}
            QPushButton, QToolButton {{
                background-color: {base};
                color: {fg};
                border: 1px solid {border};
                padding: 5px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background-color: {highlight};
            }}
            QPushButton:disabled, QToolButton:disabled {{
                background-color: {base};
                color: #888888;
                border: 1px solid #444444;
            }}
            QTextEdit, QLineEdit {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
            }}
            QComboBox {{
                background-color: {base};
                color: {fg};
                border: 1px solid {border};
                padding: 2px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {base};
                color: {fg};
                border: 1px solid {border};
                selection-background-color: {highlight};
            }}
            QLabel#WelcomeTitle {{
                font-size: 28pt;
                font-weight: bold;
            }}
            QLabel#WelcomeSubtitle {{
                color: #888888;
                font-size: 11pt;
            }}
            QLabel#RecentTitle {{
                font-size: 12pt;
                font-weight: bold;
            }}
            QPushButton#WelcomeButton {{
                text-align: left;
                padding: 10px;
            }}
            QListWidget#RecentList::item {{
                padding: 4px;
            }}
        """
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
