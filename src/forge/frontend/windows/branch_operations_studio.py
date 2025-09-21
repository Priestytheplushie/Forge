from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QLabel,
    QSplitter,
    QListWidgetItem,
    QInputDialog,
    QFrame,
    QTextEdit,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from ..assets.icon_map import get_status_icon, get_cloud_icon, get_check_icon
from ..components.diagrams.git_diagram import GitDiagramWidget


class ActionViewWidget(QWidget):
    """Base class for the views in the right-hand panel."""

    action_confirmed = Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.title_label = QLabel(title)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)

        self.explanation_label = QLabel("Explanation will be shown here.")
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setStyleSheet(
            "color: #888888; margin-top: 10px; margin-bottom: 20px;"
        )

        self.diagram_widget = GitDiagramWidget(self)

        self.confirm_button = QPushButton("Confirm Action")

        layout.addWidget(self.title_label)
        layout.addWidget(self.explanation_label)
        layout.addWidget(self.diagram_widget)
        layout.addStretch()
        layout.addWidget(self.confirm_button)

    def set_context(self, context_data: dict):
        pass


class CreateBranchActionView(ActionViewWidget):
    def __init__(self, parent=None):
        super().__init__("Create a New Branch", parent)
        self.confirm_button.setText("Choose Name and Base...")
        self.diagram_widget.set_diagram_type("create")
        self.set_context({})

        self.confirm_button.clicked.connect(self.action_confirmed)

    def set_context(self, context_data: dict):
        current = context_data.get("current_branch", "your current branch")
        explanation = (
            f"This will open a dialog to create a new branch. A branch is like an alternate universe for your code, "
            f"allowing you to work on new features without affecting the main version.\n\n"
            f"Your new branch will start as a copy of '{current}'."
        )
        self.explanation_label.setText(explanation)


class MergeActionView(ActionViewWidget):
    action_confirmed = Signal(str)

    def __init__(self, squash=False, parent=None):
        self.is_squash = squash
        action_name = "Squash Merge" if squash else "Merge"
        super().__init__(f"Confirm {action_name}", parent)
        self.confirm_button.setText(action_name)
        self.diagram_widget.set_diagram_type("squash" if squash else "merge")

        self.commit_message_edit = QTextEdit()
        self.commit_message_edit.setFixedHeight(60)
        self.layout().insertWidget(3, self.commit_message_edit)

        self.confirm_button.clicked.connect(self._on_confirm)

    def set_context(self, context_data: dict):
        target = context_data["target_branch"]
        current = context_data["current_branch"]
        self.title_label.setText(
            f"{self.confirm_button.text()} '{target}' into '{current}'"
        )

        if self.is_squash:
            num_commits = 2
            self.commit_message_edit.setPlaceholderText(
                f"Commit message (squashing {num_commits} commits)..."
            )
            explanation = (
                f"This will combine all commits from '{target}' into a single new commit on your current branch, '{current}'. "
                f"Warning: The individual commit history from '{target}' will be lost.\n\nThis creates a cleaner, more linear history."
            )
        else:
            self.commit_message_edit.setPlaceholderText(
                f"Merge branch '{target}' into '{current}'"
            )
            explanation = (
                f"This will integrate the changes from the '{target}' branch into your current branch, '{current}'.\n\n"
                "This will create a new 'merge commit' to tie the two branch histories together. Note: merge commits can create a messy history."
            )
        self.explanation_label.setText(explanation)

    def _on_confirm(self):
        self.action_confirmed.emit(self.commit_message_edit.toPlainText())


class RebaseActionView(ActionViewWidget):
    def __init__(self, parent=None):
        super().__init__("Confirm Rebase", parent)
        self.confirm_button.setText("Rebase")
        self.diagram_widget.set_diagram_type("rebase")

        self.confirm_button.clicked.connect(self.action_confirmed)

    def set_context(self, context_data: dict):
        target = context_data["target_branch"]
        current = context_data["current_branch"]
        self.title_label.setText(f"Rebase '{current}' onto '{target}'")
        explanation = (
            f"This will rebase your current branch '{current}' onto '{target}'.\n\n"
            "Warning: this action will re-write history and change commit SHA1s. Use with caution, especially on shared branches."
        )
        self.explanation_label.setText(explanation)


class BranchOperationsStudio(QDialog):
    create_branch_requested = Signal(str, str)
    merge_branch_requested = Signal(str, bool, str)
    rebase_branch_requested = Signal(str)
    rename_branch_requested = Signal(str, str)
    delete_branch_requested = Signal(str, bool)

    def __init__(self, branch_data, current_branch, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Branch Management Studio")
        self.setMinimumSize(800, 500)
        self.branch_data = branch_data
        self.current_branch = current_branch
        self.selected_branch = None

        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter branches...")
        self.branch_list = QListWidget()
        left_layout.addWidget(self.filter_edit)
        left_layout.addWidget(self.branch_list)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_panel.setFixedWidth(150)
        self.new_branch_button = QPushButton("New Branch...")
        self.merge_button = QPushButton("Merge into Current...")
        self.squash_merge_button = QPushButton("Squash into Current...")
        self.rebase_button = QPushButton("Rebase Current onto...")
        self.rename_button = QPushButton("Rename...")
        self.delete_button = QPushButton("Delete...")
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        center_layout.addWidget(self.new_branch_button)
        center_layout.addWidget(sep1)
        center_layout.addWidget(self.merge_button)
        center_layout.addWidget(self.squash_merge_button)
        center_layout.addWidget(self.rebase_button)
        center_layout.addWidget(sep2)
        center_layout.addWidget(self.rename_button)
        center_layout.addWidget(self.delete_button)
        center_layout.addStretch()

        self.action_stage = QStackedWidget()
        self.welcome_view = QLabel("Select a branch and choose an action.")
        self.welcome_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.create_branch_view = CreateBranchActionView()
        self.merge_view = MergeActionView(squash=False)
        self.squash_merge_view = MergeActionView(squash=True)
        self.rebase_view = RebaseActionView()
        self.action_stage.addWidget(self.welcome_view)
        self.action_stage.addWidget(self.create_branch_view)
        self.action_stage.addWidget(self.merge_view)
        self.action_stage.addWidget(self.squash_merge_view)
        self.action_stage.addWidget(self.rebase_view)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.action_stage)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(2, 2)
        main_layout.addWidget(splitter)

        self.populate_branch_list()
        self.update_action_buttons()
        self._connect_signals()

    def _connect_signals(self):
        self.filter_edit.textChanged.connect(self.filter_list)
        self.branch_list.currentItemChanged.connect(self.on_branch_selected)
        self.new_branch_button.clicked.connect(self.on_new_branch)
        self.merge_button.clicked.connect(self.on_merge)
        self.squash_merge_button.clicked.connect(self.on_squash_merge)
        self.rebase_button.clicked.connect(self.on_rebase)
        self.rename_button.clicked.connect(self.on_rename)
        self.delete_button.clicked.connect(self.on_delete)

        self.create_branch_view.action_confirmed.connect(
            lambda: self.create_branch_requested.emit("", "")
        )
        self.merge_view.action_confirmed.connect(
            lambda msg: self.merge_branch_requested.emit(
                self.selected_branch["full_name"], False, msg
            )
        )
        self.squash_merge_view.action_confirmed.connect(
            lambda msg: self.merge_branch_requested.emit(
                self.selected_branch["full_name"], True, msg
            )
        )
        self.rebase_view.action_confirmed.connect(
            lambda: self.rebase_branch_requested.emit(self.selected_branch["full_name"])
        )

    def populate_branch_list(self):
        self.branch_list.clear()
        local_icon, remote_icon, check_icon = (
            get_status_icon("git-branch"),
            get_cloud_icon(),
            get_check_icon(),
        )
        for branch_name, _ in self.branch_data.get("local", []):
            item = QListWidgetItem(local_icon, branch_name)
            item.setData(
                Qt.ItemDataRole.UserRole, {"full_name": branch_name, "is_remote": False}
            )
            if branch_name == self.current_branch:
                item.setIcon(check_icon)
            self.branch_list.addItem(item)
        for branch_name, _ in self.branch_data.get("remote", []):
            display_name = branch_name.replace("origin/", "", 1)
            item = QListWidgetItem(remote_icon, display_name)
            item.setData(
                Qt.ItemDataRole.UserRole, {"full_name": branch_name, "is_remote": True}
            )
            self.branch_list.addItem(item)

    @Slot(str)
    def filter_list(self, text: str):
        for i in range(self.branch_list.count()):
            self.branch_list.item(i).setHidden(
                text.lower() not in self.branch_list.item(i).text().lower()
            )

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_branch_selected(self, current, previous):
        self.selected_branch = (
            current.data(Qt.ItemDataRole.UserRole) if current else None
        )
        self.action_stage.setCurrentWidget(self.welcome_view)
        self.update_action_buttons()

    def update_action_buttons(self):
        enabled = self.selected_branch is not None
        is_current = (
            enabled and self.selected_branch["full_name"] == self.current_branch
        )
        is_remote = enabled and self.selected_branch["is_remote"]
        self.merge_button.setEnabled(enabled and not is_current and not is_remote)
        self.squash_merge_button.setEnabled(
            enabled and not is_current and not is_remote
        )
        self.rebase_button.setEnabled(enabled and not is_current and not is_remote)
        self.rename_button.setEnabled(enabled and not is_remote)
        self.delete_button.setEnabled(enabled and not is_current)

    def on_new_branch(self):
        self.create_branch_view.set_context({"current_branch": self.current_branch})
        self.action_stage.setCurrentWidget(self.create_branch_view)

    def on_merge(self):
        context = {
            "target_branch": self.selected_branch["full_name"],
            "current_branch": self.current_branch,
        }
        self.merge_view.set_context(context)
        self.action_stage.setCurrentWidget(self.merge_view)

    def on_squash_merge(self):
        context = {
            "target_branch": self.selected_branch["full_name"],
            "current_branch": self.current_branch,
        }
        self.squash_merge_view.set_context(context)
        self.action_stage.setCurrentWidget(self.squash_merge_view)

    def on_rebase(self):
        context = {
            "target_branch": self.selected_branch["full_name"],
            "current_branch": self.current_branch,
        }
        self.rebase_view.set_context(context)
        self.action_stage.setCurrentWidget(self.rebase_view)

    def on_rename(self):
        old_name = self.selected_branch["full_name"]
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Branch",
            f"Enter new name for branch '{old_name}':",
            text=old_name,
        )
        if ok and new_name and new_name != old_name:
            self.rename_branch_requested.emit(old_name, new_name)

    def on_delete(self):
        data = self.selected_branch
        self.delete_branch_requested.emit(data["full_name"], data["is_remote"])
