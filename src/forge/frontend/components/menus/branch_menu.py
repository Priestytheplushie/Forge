from PySide6.QtWidgets import QMenu, QLineEdit, QWidgetAction
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal, Slot, Qt, QPoint

from ...assets.icon_map import (
    get_status_icon,
    get_cloud_icon,
    get_check_icon,
    get_trash_icon,
)


class BranchMenu(QMenu):
    """A custom menu for viewing, switching, and creating Git branches."""

    checkout_requested = Signal(str)
    create_branch_requested = Signal()
    manage_branches_requested = Signal()
    merge_requested = Signal(str)
    squash_merge_requested = Signal(str)
    rebase_requested = Signal(str)
    rename_requested = Signal(str)
    delete_local_requested = Signal(str)
    delete_remote_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.local_icon = get_status_icon("git-branch")
        self.remote_icon = get_cloud_icon()
        self.check_icon = get_check_icon()
        self.trash_icon = get_trash_icon()

        self.dynamic_actions = []
        self.current_branch = ""

        self.create_action = QAction("Create New Branch...", self)
        self.manage_action = QAction("Manage Branches...", self)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.create_action.triggered.connect(self.create_branch_requested)
        self.manage_action.triggered.connect(self.manage_branches_requested)
        self.triggered.connect(self._on_action_triggered)

    def populate_branches(self, branch_data: dict, current_branch: str):
        self.current_branch = current_branch
        self.clear()

        if branch_data.get("local"):
            self.addSection("Local Branches").setEnabled(False)
            for branch_name, status in branch_data.get("local", []):
                self.addAction(self._create_branch_action(branch_name, is_remote=False))

        if branch_data.get("remote"):
            self.addSeparator()
            self.addSection("Remote Branches").setEnabled(False)
            for branch_name, status in branch_data.get("remote", []):
                self.addAction(self._create_branch_action(branch_name, is_remote=True))

        self.addSeparator()
        self.addAction(self.create_action)
        self.addAction(self.manage_action)

    def _create_branch_action(self, branch_name: str, is_remote: bool) -> QAction:
        display_name = (
            branch_name.replace("origin/", "", 1) if is_remote else branch_name
        )
        action = QAction(display_name, self)
        action.setData({"full_name": branch_name, "is_remote": is_remote})
        action.setIcon(self.remote_icon if is_remote else self.local_icon)
        if branch_name == self.current_branch:
            action.setIcon(self.check_icon)
        return action

    @Slot(QAction)
    def _on_action_triggered(self, action: QAction):
        data = action.data()
        if data and isinstance(data, dict):
            self.checkout_requested.emit(data["full_name"])

    @Slot(QPoint)
    def show_context_menu(self, point: QPoint):
        action = self.actionAt(point)
        if not action or not action.data():
            return

        data = action.data()
        branch_name = data["full_name"]
        is_remote = data["is_remote"]
        is_current = branch_name == self.current_branch

        menu = QMenu(self)
        if is_remote:
            menu.addAction(
                f"Checkout remote branch '{action.text()}'"
            ).triggered.connect(lambda: self.checkout_requested.emit(branch_name))
            menu.addSeparator()
            menu.addAction(
                self.trash_icon, f"Delete remote branch..."
            ).triggered.connect(lambda: self.delete_remote_requested.emit(branch_name))
        else:
            if not is_current:
                menu.addAction(
                    f"Merge '{branch_name}' into '{self.current_branch}'..."
                ).triggered.connect(lambda: self.merge_requested.emit(branch_name))
                menu.addAction(
                    f"Squash Merge '{branch_name}' into '{self.current_branch}'..."
                ).triggered.connect(
                    lambda: self.squash_merge_requested.emit(branch_name)
                )
                menu.addAction(
                    f"Rebase '{self.current_branch}' onto '{branch_name}'..."
                ).triggered.connect(lambda: self.rebase_requested.emit(branch_name))
                menu.addSeparator()

            menu.addAction(f"Rename '{branch_name}'...").triggered.connect(
                lambda: self.rename_requested.emit(branch_name)
            )
            if not is_current:
                menu.addAction(
                    self.trash_icon, f"Delete '{branch_name}'..."
                ).triggered.connect(
                    lambda: self.delete_local_requested.emit(branch_name)
                )

        menu.exec(self.mapToGlobal(point))
