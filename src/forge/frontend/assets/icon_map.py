from PySide6.QtGui import QIcon, QPainter, QColor, QTransform, QPixmap
from PySide6.QtCore import QSize, Qt
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


def get_themed_icon(icon_filename: str, color_hex: str) -> Path:
    """Creates a colorized icon file in a temp dir for QSS usage and returns its path."""
    temp_dir = Path.home() / ".forge" / "temp" / "icons"
    temp_dir.mkdir(parents=True, exist_ok=True)

    safe_color_hex = color_hex.replace("#", "")
    themed_icon_path = temp_dir / f"{Path(icon_filename).stem}_{safe_color_hex}.svg"

    if themed_icon_path.exists():
        return themed_icon_path

    icon_path = ICON_ROOT / icon_filename
    if not icon_path.exists():
        return Path()

    with open(icon_path, "r") as f:
        svg_data = f.read()

    colored_svg = svg_data.replace('stroke="currentColor"', f'stroke="{color_hex}"')

    with open(themed_icon_path, "w") as f:
        f.write(colored_svg)

    return themed_icon_path


def get_rotated_icon(icon_filename: str, color: QColor, degrees: int) -> QIcon:
    """Creates and caches a rotated version of an icon."""
    cache_key = (icon_filename, color.name(), degrees)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    base_pixmap = _get_colorized_icon(icon_filename, color).pixmap(QSize(16, 16))

    size = max(base_pixmap.width(), base_pixmap.height())
    rotated_pixmap = QPixmap(size, size)
    rotated_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rotated_pixmap)
    painter.translate(size / 2, size / 2)
    painter.rotate(degrees)
    painter.translate(-base_pixmap.width() / 2, -base_pixmap.height() / 2)
    painter.drawPixmap(0, 0, base_pixmap)
    painter.end()

    rotated_icon = QIcon(rotated_pixmap)
    _icon_cache[cache_key] = rotated_icon
    return rotated_icon


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


def get_commit_icon(rotated: bool = False) -> QIcon:
    color = QColor("#81A1C1")
    if rotated:
        return get_rotated_icon("git-commit.svg", color, 90)
    return _get_colorized_icon("git-commit.svg", color)


def get_bookmark_icon() -> QIcon:
    return _get_colorized_icon("bookmark.svg", QColor("#DDB451"))


def get_resolved_icon() -> QIcon:
    return _get_colorized_icon("check-circle.svg", QColor("#73C991"))


def get_unresolved_icon() -> QIcon:
    return _get_colorized_icon("alert-triangle.svg", QColor("#DDB451"))


def get_arrow_up_icon() -> QIcon:
    return _get_colorized_icon("arrow-up.svg", QColor("#D8DEE9"))


def get_arrow_down_icon() -> QIcon:
    return _get_colorized_icon("arrow-down.svg", QColor("#D8DEE9"))


def get_cloud_icon() -> QIcon:
    return _get_colorized_icon("cloud.svg", QColor("#D8DEE9"))


def get_check_icon() -> QIcon:
    return _get_colorized_icon("check.svg", QColor("#6AF699"))


def get_trash_icon() -> QIcon:
    return _get_colorized_icon("trash-2.svg", QColor("#F77669"))


def get_plus_icon() -> QIcon:
    return _get_colorized_icon("plus.svg", QColor("#D8DEE9"))


def get_split_icon() -> QIcon:
    return _get_colorized_icon("layout.svg", QColor("#D8DEE9"))


def get_tooltip_for_symbol(kind: int) -> str:
    meta = SYMBOL_META_DATA.get(kind, SYMBOL_META_DATA[KIND_KEYWORD])
    return meta["tooltip"]
