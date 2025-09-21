from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtCore import QSize
from pathlib import Path

KIND_FILE = 1
KIND_MODULE = 2
KIND_NAMESPACE = 3
KIND_PACKAGE = 4
KIND_CLASS = 5
KIND_METHOD = 6
KIND_PROPERTY = 7
KIND_FIELD = 8
KIND_CONSTRUCTOR = 9
KIND_ENUM = 10
KIND_INTERFACE = 11
KIND_FUNCTION = 12
KIND_VARIABLE = 13
KIND_CONSTANT = 14
KIND_KEYWORD = 14
KIND_STRING = 15
KIND_NUMBER = 16
KIND_BOOLEAN = 17
KIND_ARRAY = 18
KIND_OBJECT = 19
KIND_KEY = 20
KIND_NULL = 21
KIND_ENUMMEMBER = 22
KIND_STRUCT = 23
KIND_EVENT = 24
KIND_OPERATOR = 25
KIND_TYPEPARAMETER = 26

ICON_ROOT = Path(__file__).resolve().parent / "icons"

SYMBOL_META_DATA = {
    KIND_CLASS: {"icon": "box.svg", "color": "#4E94D7", "tooltip": "Class"},
    KIND_CONSTRUCTOR: {
        "icon": "code.svg",
        "color": "#DDB451",
        "tooltip": "Constructor",
    },
    KIND_FUNCTION: {"icon": "code.svg", "color": "#DDB451", "tooltip": "Function"},
    KIND_METHOD: {"icon": "code.svg", "color": "#DDB451", "tooltip": "Method"},
    KIND_VARIABLE: {"icon": "type.svg", "color": "#4E94D7", "tooltip": "Variable"},
    KIND_FIELD: {"icon": "type.svg", "color": "#4E94D7", "tooltip": "Field"},
    KIND_PROPERTY: {"icon": "type.svg", "color": "#4E94D7", "tooltip": "Property"},
    KIND_CONSTANT: {"icon": "shield.svg", "color": "#A3BE8C", "tooltip": "Constant"},
    KIND_MODULE: {"icon": "package.svg", "color": "#667082", "tooltip": "Module"},
    KIND_PACKAGE: {"icon": "package.svg", "color": "#667082", "tooltip": "Package"},
    KIND_NAMESPACE: {"icon": "package.svg", "color": "#667082", "tooltip": "Namespace"},
    KIND_KEYWORD: {"icon": "bookmark.svg", "color": "#D9880F", "tooltip": "Keyword"},
}

_icon_cache = {}


def _get_colorized_icon(icon_filename: str, color: QColor) -> QIcon:
    """A generic helper to create and cache colorized icons."""
    cache_key = (icon_filename, color.name())
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    icon_path = ICON_ROOT / icon_filename
    if not icon_path.exists():
        return QIcon()

    original_icon = QIcon(str(icon_path))
    pixmap = original_icon.pixmap(QSize(16, 16))

    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()

    colorized_icon = QIcon(pixmap)
    _icon_cache[cache_key] = colorized_icon

    return colorized_icon


def get_icon_for_symbol(kind: int) -> QIcon:
    """Gets a colorized QIcon for a given LSP DocumentSymbolKind."""
    meta = SYMBOL_META_DATA.get(kind, SYMBOL_META_DATA[KIND_KEYWORD])
    color = QColor(meta["color"])
    return _get_colorized_icon(meta["icon"], color)


def get_run_icon() -> QIcon:
    return _get_colorized_icon("play.svg", QColor("#6AF699"))


def get_run_output_icon() -> QIcon:
    return _get_colorized_icon("play.svg", QColor("#4E94D7"))


def get_stop_icon() -> QIcon:
    return _get_colorized_icon("stop-circle.svg", QColor("#F77669"))


def get_status_icon(name: str, color: str = "#D8DEE9") -> QIcon:
    return _get_colorized_icon(f"{name}.svg", QColor(color))


def get_bookmark_icon() -> QIcon:
    """Gets the colorized 'bookmark' icon for pinned history items."""
    return _get_colorized_icon("bookmark.svg", QColor("#DDB451"))


def get_resolved_icon() -> QIcon:
    return _get_colorized_icon("check-circle.svg", QColor("#73C991"))


def get_unresolved_icon() -> QIcon:
    return _get_colorized_icon("alert-triangle.svg", QColor("#DDB451"))


def get_tooltip_for_symbol(kind: int) -> str:
    meta = SYMBOL_META_DATA.get(kind, SYMBOL_META_DATA[KIND_KEYWORD])
    return meta["tooltip"]
