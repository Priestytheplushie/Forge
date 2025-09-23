from PySide6.QtWidgets import QToolBar, QWidget, QVBoxLayout, QToolButton, QSizePolicy
from PySide6.QtGui import QAction, QActionGroup
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

        self.add_action("Explorer", get_explorer_icon(), True)
        self.add_action("Source Control", get_git_icon())
        self.add_action("Search", get_search_icon())
        self.add_action("Debug", get_debug_icon())
        self.add_action("Review", get_review_icon())
        self.add_action("AI", get_ai_icon())

        spacer = QWidget()

        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.addWidget(spacer)

        self.add_action("Account", get_account_icon())
        self.add_action("Settings", get_settings_icon())

        self.action_group.triggered.connect(self._on_action_triggered)

    def add_action(self, name: str, icon, is_checked=False):
        action = QAction(icon, name, self)
        action.setCheckable(True)
        action.setChecked(is_checked)
        action.setData(name)
        self.action_group.addAction(action)
        super().addAction(action)

    @Slot(QAction)
    def _on_action_triggered(self, action: QAction):
        self.view_selected.emit(action.data())
