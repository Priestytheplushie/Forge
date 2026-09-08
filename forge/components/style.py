from tkinter import ttk

ICON_MAP = {
    "py": {"icon": "🐍", "color": "#FFD700"},
    "java": {"icon": "☕", "color": "#E76F00"},
    "json": {"icon": "📦", "color": "#FFFFFF"},
    "md": {"icon": "📝", "color": "#FFFFFF"},
    "default_file": {"icon": "📄", "color": "#FFFFFF"},
    "folder": {"icon": "📁", "color": "#808080"},
    "class": {"icon": "C", "color": "#DDA0DD"},
    "method": {"icon": "M", "color": "#9CDCFE"},
    "variable": {"icon": "V", "color": "#4FC1FF"},
    "problem_error": {"icon": "🔴", "color": "#F44747"},
    "problem_warning": {"icon": "⚠️", "color": "#FFD700"},
    "welcome": {"icon": "🔥", "color": "#FFA500"},
    "explorer": {"icon": "▸", "color": "#FFFFFF"},
    "intellisense": {"icon": "💡", "color": "#9CDCFE"},
    "outline": {"icon": "🌳", "color": "#A6E22E"},
    "problems": {"icon": "◆", "color": "#F44747"},
}

KIND_MAP_COLOR = {
    5: {"icon": "ƒ", "color": "#C586C0"},
    6: {"icon": "ƒ", "color": "#C586C0"},
    7: {"icon": "ƒ", "color": "#C586C0"},
    2: {"icon": "📦", "color": "#CE9178"},
    12: {"icon": "●", "color": "#9CDCFE"},
    9: {"icon": "●", "color": "#9CDCFE"},
    14: {"icon": "🔑", "color": "#D19A66"},
    "default": {"icon": "T", "color": "#CCCCCC"},
}

GIT_STATUS_COLOR = {
    "M": "#E2C08D",
    "A": "#A6E22E",
    "D": "#F92672",
}

TAB_COLORS = {
    "bg_color": "#2b2b2b",
    "fg_color": "#242424",
    "hover_color": "#333333",
    "selected_color": "#1e1e1e",
    "selected_hover_color": "#1e1e1e",
    "unselected_hover_color": "#333333",
    "text_color": "#cccccc",
    "selected_text_color": "#ffffff",
    "border_color": "#0078D7",
}


def apply_ttk_styles():
    style = ttk.Style()
    style.theme_use("clam")
