from PySide6.QtGui import QIcon, QPainter, QColor, QTransform, QPixmap
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtCore import QSize, Qt, QFileInfo
from pathlib import Path
import os

ICON_ROOT = Path(__file__).resolve().parent / "icons"

LSP_KIND_TO_META = {
    5: {"icon": "box.svg", "color": "#DDB451", "tooltip": "Class"},
    12: {"icon": "box.svg", "color": "#DDB451", "tooltip": "Struct"},
    6: {"icon": "code.svg", "color": "#569CD6", "tooltip": "Function"},
    2: {"icon": "code.svg", "color": "#88C0D0", "tooltip": "Method"},
    13: {"icon": "type.svg", "color": "#D8DEE9", "tooltip": "Variable"},
    4: {"icon": "type.svg", "color": "#D8DEE9", "tooltip": "Field"},
    10: {"icon": "type.svg", "color": "#B48EAD", "tooltip": "Property"},
    21: {"icon": "shield.svg", "color": "#BF616A", "tooltip": "Constant"},
    8: {"icon": "book-open.svg", "color": "#A3BE8C", "tooltip": "Interface"},
    9: {"icon": "file-text.svg", "color": "#667082", "tooltip": "Module"},
}

PYFORGE_ICON_MAP = {
    "special_group": {"icon": "database.svg", "color": "#81A1C1"},
    "module": {"icon": "file-text.svg", "color": "#667082"},
    "imports_group": {"icon": "log-in.svg", "color": "#88C0D0"},
    "globals_group": {"icon": "at-sign.svg", "color": "#B48EAD"},
    "builtins_group": {"icon": "at-sign.svg", "color": "#667082"},
    "class_group": {"icon": "folder.svg", "color": "#DDB451"},
    "function_group": {"icon": "folder.svg", "color": "#569CD6"},
    "instance_group": {"icon": "folder.svg", "color": "#A3BE8C"},
    "instance_group_for_class": {"icon": "folder.svg", "color": "#A3BE8C"},
    "attribute_group": {"icon": "folder.svg", "color": "#434C5E"},
    "class_attribute_group": {"icon": "folder.svg", "color": "#434C5E"},
    "method_group": {"icon": "folder.svg", "color": "#88C0D0"},
    "method_group_for_instance": {"icon": "folder.svg", "color": "#88C0D0"},
    "class": {"icon": "box.svg", "color": "#DDB451"},
    "function": {"icon": "code.svg", "color": "#569CD6"},
    "instance": {"icon": "archive.svg", "color": "#A3BE8C"},
    "attribute_simple": {"icon": "type.svg", "color": "#D8DEE9"},
    "attribute_collection": {"icon": "list.svg", "color": "#D8DEE9"},
    "method": {"icon": "code.svg", "color": "#88C0D0"},
    "metric": {"icon": "sliders.svg", "color": "#81A1C1"},
    "hook": {"icon": "git-pull-request.svg", "color": "#B48EAD"},
    "override": {"icon": "alert-triangle.svg", "color": "#DDB451"},
    "event_script": {"icon": "pyforge-script.svg", "color": "#88C0D0"},
}

AUDIT_LOG_ICON_MAP = {
    "SessionStarted": {"icon": "play-circle.svg", "color": "#73C991"},
    "SessionStopped": {"icon": "stop-circle.svg", "color": "#BF616A"},
    "ConsoleCommand": {"icon": "terminal.svg", "color": "#81A1C1"},
    "ScriptExecution": {"icon": "pyforge-script.svg", "color": "#B69CFD"},
    "AttributeChange": {"icon": "edit-3.svg", "color": "#DDB451"},
    "FunctionCall": {"icon": "play-circle.svg", "color": "#A3BE8C"},
    "InstanceCreation": {"icon": "plus-circle.svg", "color": "#A3BE8C"},
    "DeleteObject": {"icon": "trash-2.svg", "color": "#BF616A"},
    "HotReload": {"icon": "zap.svg", "color": "#B48EAD"},
    "ReloadMasterScript": {"icon": "refresh-cw.svg", "color": "#88C0D0"},
    "ValidateMasterScript": {"icon": "check-circle.svg", "color": "#88C0D0"},
    "WatchClass": {"icon": "eye.svg", "color": "#8FBCBB"},
    "UnwatchClass": {"icon": "eye-off.svg", "color": "#8FBCBB"},
    "Default": {"icon": "info.svg", "color": "#D8DEE9"},
}

_icon_cache = {}
_os_icon_provider = QFileIconProvider()


def get_audit_log_icon(action_type: str = "Default") -> QIcon:
    """Gets a colorized icon for a specific audit log action type."""
    meta = AUDIT_LOG_ICON_MAP.get(action_type, AUDIT_LOG_ICON_MAP["Default"])
    return get_colorized_icon(meta["icon"], QColor(meta["color"]))


def get_pyforge_script_icon() -> QIcon:
    return get_colorized_icon("pyforge-script.svg", QColor("#B69CFD"))


def get_pyforge_object_icon(node_type: str, file_path: str = "") -> QIcon:
    if node_type == "module" and file_path:
        file_info = QFileInfo(file_path)
        return _os_icon_provider.icon(file_info)

    meta = PYFORGE_ICON_MAP.get(node_type, {"icon": "circle.svg", "color": "#D8DEE9"})
    return get_colorized_icon(meta["icon"], QColor(meta["color"]))


def get_colorized_icon(icon_filename: str, color: QColor) -> QIcon:
    cache_key = (icon_filename, color.name())
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    icon_path = ICON_ROOT / icon_filename
    if not icon_path.exists():
        return QIcon()

    original_icon = QIcon(str(icon_path))
    pixmap = original_icon.pixmap(QSize(24, 24))

    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()

    colorized_icon = QIcon(pixmap)
    _icon_cache[cache_key] = colorized_icon

    return colorized_icon


def get_themed_icon(icon_filename: str, color_hex: str) -> Path:
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
    cache_key = (icon_filename, color.name(), degrees)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    base_pixmap = get_colorized_icon(icon_filename, color).pixmap(QSize(16, 16))

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
    meta = LSP_KIND_TO_META.get(kind, {"icon": "circle.svg", "color": "#D8DEE9"})
    color = QColor(meta["color"])
    return get_colorized_icon(meta["icon"], color)


def get_tooltip_for_symbol(kind: int) -> str:
    return LSP_KIND_TO_META.get(kind, {}).get("tooltip", "Symbol")


def get_run_icon() -> QIcon:
    return get_colorized_icon("play.svg", QColor("#6AF699"))


def get_pyforge_icon() -> QIcon:
    return get_colorized_icon("play.svg", QColor("#B69CFD"))


def get_run_output_icon() -> QIcon:
    return get_colorized_icon("play.svg", QColor("#4E94D7"))


def get_stop_icon() -> QIcon:
    return get_colorized_icon("stop-circle.svg", QColor("#F77669"))


def get_status_icon(name: str, color: str = "#D8DEE9") -> QIcon:
    if not name.endswith(".svg"):
        name += ".svg"
    return get_colorized_icon(name, QColor(color))


def get_commit_icon(rotated: bool = False) -> QIcon:
    color = QColor("#81A1C1")
    if rotated:
        return get_rotated_icon("git-commit.svg", color, 90)
    return get_colorized_icon("git-commit.svg", color)


def get_bookmark_icon() -> QIcon:
    return get_colorized_icon("bookmark.svg", QColor("#DDB451"))


def get_resolved_icon() -> QIcon:
    return get_colorized_icon("check-circle.svg", QColor("#73C991"))


def get_unresolved_icon() -> QIcon:
    return get_colorized_icon("alert-triangle.svg", QColor("#DDB451"))


def get_arrow_up_icon() -> QIcon:
    return get_colorized_icon("arrow-up.svg", QColor("#D8DEE9"))


def get_arrow_down_icon() -> QIcon:
    return get_colorized_icon("arrow-down.svg", QColor("#D8DEE9"))


def get_cloud_icon() -> QIcon:
    return get_colorized_icon("cloud.svg", QColor("#D8DEE9"))


def get_check_icon() -> QIcon:
    return get_colorized_icon("check.svg", QColor("#6AF699"))


def get_trash_icon() -> QIcon:
    return get_colorized_icon("trash-2.svg", QColor("#F77669"))


def get_plus_icon() -> QIcon:
    return get_colorized_icon("plus.svg", QColor("#D8DEE9"))


def get_split_icon() -> QIcon:
    return get_colorized_icon("layout.svg", QColor("#D8DEE9"))


def get_explorer_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("file-text.svg", QColor(color))


def get_search_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("search.svg", QColor(color))


def get_git_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("git-branch.svg", QColor(color))


def get_debug_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("target.svg", QColor(color))


def get_review_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("check-square.svg", QColor(color))


def get_ai_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("cpu.svg", QColor(color))


def get_account_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("user.svg", QColor(color))


def get_settings_icon(color: str = "#D8DEE9"):
    return get_colorized_icon("settings.svg", QColor(color))
