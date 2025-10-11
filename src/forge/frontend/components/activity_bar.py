from PySide6.QtWidgets import QToolBar, QWidget, QVBoxLayout, QToolButton, QSizePolicy
from PySide6.QtGui import QAction, QActionGroup, QColor
from PySide6.QtCore import Qt, Signal, QSize, Slot

from ..assets.icon_map import (
    get_explorer_icon,
    get_search_icon,
    get_git_icon,
    get_debug_icon,
    get_review_icon,
    get_ai_icon,
    get_account_icon,
    get_settings_icon,
    get_colorized_icon,
)


class ActivityBar(QToolBar):
    """A vertical toolbar for switching between different application views."""

    view_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(24, 24))
        self.action_group = QActionGroup(self)
        self.action_group.setExclusive(True)

        self.default_icon_color = QColor("#D8DEE9")

        self.add_action("Explorer", "file-text.svg", True)
        self.add_action("Source Control", "git-branch.svg")
        self.add_action("Search", "search.svg")
        self.add_action("Debug", "target.svg")
        self.add_action("Review", "check-square.svg")
        self.add_action("AI", "cpu.svg")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.addWidget(spacer)

        self.add_action("Account", "user.svg")
        self.add_action("Settings", "settings.svg")

        self.action_group.triggered.connect(self._on_action_triggered)

    def add_action(self, name: str, icon_filename: str, is_checked=False):
        icon = get_colorized_icon(icon_filename, self.default_icon_color)
        action = QAction(icon, name, self)
        action.setCheckable(True)
        action.setChecked(is_checked)

        action.setData({"name": name, "icon": icon_filename})
        self.action_group.addAction(action)
        super().addAction(action)

    @Slot(QAction)
    def _on_action_triggered(self, action: QAction):
        self.view_selected.emit(action.data()["name"])

    def set_action_icon_color(self, name: str, color: QColor | None):
        """Finds an action by name and updates its icon color."""
        for action in self.action_group.actions():
            action_data = action.data()
            if action_data["name"] == name:
                target_color = color if color is not None else self.default_icon_color
                new_icon = get_colorized_icon(action_data["icon"], target_color)
                action.setIcon(new_icon)
                break

    def set_modal(self, view_name: str, is_modal: bool):
        for action in self.action_group.actions():
            if action.data()["name"] != view_name:
                action.setEnabled(not is_modal)

    def check_action(self, view_name: str):
        """Programmatically checks the action corresponding to the view name."""
        for action in self.action_group.actions():
            if action.data()["name"] == view_name:
                action.setChecked(True)
                break
