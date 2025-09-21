import os
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QTextEdit,
    QHBoxLayout,
    QSizePolicy,
    QFileIconProvider,
    QToolButton,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QSize, QFileInfo
from PySide6.QtGui import QAction, QActionGroup

from ...assets.icon_map import get_status_icon, get_resolved_icon, get_unresolved_icon


class GitStatusItemWidget(QWidget):
    def __init__(
        self,
        icon_provider: QFileIconProvider,
        file_path: str,
        status: str,
        is_merge_view: bool = False,
        is_resolved: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.status = status

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(6)

        file_info = QFileInfo(file_path)
        file_icon_label = QLabel()
        file_icon_label.setPixmap(icon_provider.icon(file_info).pixmap(16, 16))

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        filename = os.path.basename(file_path)
        directory = os.path.dirname(file_path)
        filename_label = QLabel(filename)
        filename_label.setStyleSheet("font-weight: normal;")
        dir_label = QLabel(directory)
        dir_label.setStyleSheet("color: #888888;")
        text_layout.addWidget(filename_label)
        text_layout.addWidget(dir_label)

        layout.addWidget(file_icon_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        if is_merge_view:
            status_icon_label = QLabel()
            icon = get_resolved_icon() if is_resolved else get_unresolved_icon()
            status_icon_label.setPixmap(icon.pixmap(16, 16))
            layout.addWidget(status_icon_label)
        else:
            status_label = QLabel(status)
            status_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            status_colors = {
                "M": "#E2C087",
                "A": "#73C991",
                "D": "#F77669",
                "R": "#73C991",
                "U": "#C586C0",
                "T": "#73C991",
            }
            color = status_colors.get(status, "#D8DEE9")
            status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            layout.addWidget(status_label)


class SourceControlPanel(QWidget):
    file_selected = Signal(str, str)
    open_file_requested = Signal(str)
    show_history_requested = Signal(str)
    reveal_in_explorer_requested = Signal(str)
    discard_changes_requested = Signal(list)
    stage_requested = Signal(list)
    unstage_requested = Signal(list)
    stage_all_requested = Signal()
    unstage_all_requested = Signal()
    commit_requested = Signal(str, bool)
    commit_merge_requested = Signal(str)
    stash_requested = Signal(str)
    initialize_repo_requested = Signal()
    clone_repo_requested = Signal()
    abort_merge_requested = Signal()

    def __init__(self, icon_provider: QFileIconProvider, parent=None):
        super().__init__(parent)
        self.icon_provider = icon_provider
        self.current_staged_files = []
        self.current_unstaged_files = []

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

        self.stack = QStackedWidget(self)
        self.main_layout.addWidget(self.stack)

        self.no_repo_widget = QWidget()
        no_repo_layout = QVBoxLayout(self.no_repo_widget)
        no_repo_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        no_repo_layout.setContentsMargins(10, 15, 10, 10)
        no_repo_layout.setSpacing(10)
        self.init_repo_button = QPushButton("Initialize Repository")
        self.clone_repo_button = QPushButton("Clone Repository")
        help_label = QLabel(
            "<a href='https://git-scm.com/downloads' style='color: #4E94D7;'>Download Git</a>"
        )
        help_label.setOpenExternalLinks(True)
        no_repo_layout.addWidget(QLabel("No Git repository detected."))
        no_repo_layout.addWidget(self.init_repo_button)
        no_repo_layout.addWidget(self.clone_repo_button)
        no_repo_layout.addStretch()
        no_repo_layout.addWidget(help_label)

        self.repo_widget = QWidget()
        repo_layout = QVBoxLayout(self.repo_widget)
        repo_layout.setContentsMargins(5, 5, 5, 5)

        self.merge_widget = QWidget()
        merge_layout = QVBoxLayout(self.merge_widget)
        merge_layout.setContentsMargins(10, 10, 10, 10)
        merge_label = QLabel("Merge Conflict")
        merge_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        merge_desc = QLabel(
            "Resolve the conflicts below. Files must be staged before you can commit the merge."
        )
        merge_desc.setWordWrap(True)
        self.merge_commit_message = QTextEdit()
        self.merge_commit_message.setPlaceholderText("Merge commit message...")
        self.merge_commit_message.setFixedHeight(80)
        self.commit_merge_button = QPushButton("Commit Merge")
        self.abort_merge_button = QPushButton("Abort Merge")
        self.staged_merge_header = QLabel("Resolved (0)")
        self.staged_merge_list = QListWidget()
        self.unresolved_merge_header = QLabel("Unresolved (0)")
        self.unresolved_merge_list = QListWidget()

        merge_layout.addWidget(merge_label)
        merge_layout.addWidget(merge_desc)
        merge_layout.addWidget(self.merge_commit_message)
        merge_layout.addWidget(self.commit_merge_button)
        merge_layout.addWidget(self.abort_merge_button)
        merge_layout.addWidget(self.staged_merge_header)
        merge_layout.addWidget(self.staged_merge_list)
        merge_layout.addWidget(self.unresolved_merge_header)
        merge_layout.addWidget(self.unresolved_merge_list)

        self.stack.addWidget(self.no_repo_widget)
        self.stack.addWidget(self.repo_widget)
        self.stack.addWidget(self.merge_widget)

        self.commit_message_box = QTextEdit()
        self.commit_message_box.setPlaceholderText("Commit message...")
        self.commit_message_box.setFixedHeight(80)
        commit_button_widget = QWidget()
        commit_button_layout = QHBoxLayout(commit_button_widget)
        commit_button_layout.setContentsMargins(0, 0, 0, 0)
        commit_button_layout.setSpacing(0)
        self.commit_button = QPushButton("Commit")
        self.commit_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.commit_menu_button = QToolButton()
        self.commit_menu_button.setText("▼")
        self.commit_menu_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.commit_menu = QMenu(self)
        self.commit_action_group = QActionGroup(self)
        self.commit_action_group.setExclusive(True)
        self.commit_action = QAction("Commit", self, checkable=True)
        self.commit_and_push_action = QAction("Commit & Push", self, checkable=True)
        self.stash_action = QAction("Stash", self, checkable=True)
        self.commit_action_group.addAction(self.commit_action)
        self.commit_action_group.addAction(self.commit_and_push_action)
        self.commit_action_group.addAction(self.stash_action)
        self.commit_menu.addActions(self.commit_action_group.actions())
        self.commit_menu_button.setMenu(self.commit_menu)
        commit_button_layout.addWidget(self.commit_button)
        commit_button_layout.addWidget(self.commit_menu_button)
        self.staged_header_widget = QWidget()
        staged_header_layout = QHBoxLayout(self.staged_header_widget)
        staged_header_layout.setContentsMargins(0, 0, 0, 0)
        self.staged_header = QLabel("Staged Changes (0)")
        self.unstage_all_button = QToolButton()
        self.unstage_all_button.setIcon(get_status_icon("minus"))
        self.unstage_all_button.setToolTip("Unstage All Changes")
        staged_header_layout.addWidget(self.staged_header)
        staged_header_layout.addStretch()
        staged_header_layout.addWidget(self.unstage_all_button)
        self.staged_list = QListWidget()
        self.staged_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.staged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.unstaged_header = QLabel("Changes (0)")
        self.unstaged_list = QListWidget()
        self.unstaged_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unstaged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        repo_layout.addWidget(self.commit_message_box)
        repo_layout.addWidget(commit_button_widget)
        repo_layout.addWidget(self.staged_header_widget)
        repo_layout.addWidget(self.staged_list)
        repo_layout.addWidget(self.unstaged_header)
        repo_layout.addWidget(self.unstaged_list)

        self.init_repo_button.clicked.connect(self.initialize_repo_requested)
        self.clone_repo_button.clicked.connect(self.clone_repo_requested)
        self.staged_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.unstaged_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.staged_list.customContextMenuRequested.connect(self.on_context_menu)
        self.unstaged_list.customContextMenuRequested.connect(self.on_context_menu)
        self.commit_button.clicked.connect(self.on_commit_button_clicked)
        self.commit_action_group.triggered.connect(self._update_commit_button_state)
        self.unstage_all_button.clicked.connect(self.unstage_all_requested)
        self.abort_merge_button.clicked.connect(self.abort_merge_requested)
        self.commit_merge_button.clicked.connect(self.on_commit_merge_clicked)
        self.unresolved_merge_list.itemDoubleClicked.connect(
            self.on_item_double_clicked
        )
        self.staged_merge_list.itemDoubleClicked.connect(self.on_item_double_clicked)

        self.set_repo_status(False)

    def _populate_list(
        self,
        list_widget: QListWidget,
        files: list,
        is_merge_view=False,
        is_resolved_list=False,
    ):
        list_widget.clear()
        for file_info in files:
            path = file_info.get("path") if isinstance(file_info, dict) else file_info
            status = (
                file_info.get("status", "U") if isinstance(file_info, dict) else "U"
            )
            item = QListWidgetItem(list_widget)
            if is_merge_view:
                widget = GitStatusItemWidget(
                    self.icon_provider,
                    path,
                    status,
                    is_merge_view=True,
                    is_resolved=is_resolved_list,
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {"path": path, "status": "M" if is_resolved_list else "U"},
                )
            else:
                widget = GitStatusItemWidget(self.icon_provider, path, status)
                item.setData(Qt.ItemDataRole.UserRole, {"path": path, "status": status})
            item.setSizeHint(widget.sizeHint())
            list_widget.addItem(item)
            list_widget.setItemWidget(item, widget)

    @Slot(bool)
    def set_repo_status(self, has_repo: bool):
        self.stack.setCurrentIndex(1 if has_repo else 0)

    @Slot(list, list)
    def update_files(self, staged_files: list, unstaged_files: list):
        if self.stack.currentWidget() == self.merge_widget:
            self.staged_merge_header.setText(f"Resolved ({len(staged_files)})")
            self._populate_list(
                self.staged_merge_list,
                staged_files,
                is_merge_view=True,
                is_resolved_list=True,
            )
            self.unresolved_merge_header.setText(
                f"Unresolved Conflicts ({len(unstaged_files)})"
            )
            self._populate_list(
                self.unresolved_merge_list,
                unstaged_files,
                is_merge_view=True,
                is_resolved_list=False,
            )
            self.commit_merge_button.setEnabled(len(unstaged_files) == 0)
            return
        self.current_staged_files = [
            f.get("path") if isinstance(f, dict) else f for f in staged_files
        ]
        self.current_unstaged_files = [
            f.get("path") if isinstance(f, dict) else f for f in unstaged_files
        ]
        show_staged = bool(staged_files)
        self.staged_header_widget.setVisible(show_staged)
        self.staged_list.setVisible(show_staged)
        if show_staged:
            self.staged_header.setText(f"Staged Changes ({len(staged_files)})")
            self._populate_list(self.staged_list, staged_files)
        self.unstaged_header.setText(f"Changes ({len(unstaged_files)})")
        self._populate_list(self.unstaged_list, unstaged_files)
        self._update_commit_button_state()

    def _update_commit_button_state(self, action=None):
        has_staged, has_unstaged = bool(self.current_staged_files), bool(
            self.current_unstaged_files
        )
        if not self.commit_action_group.checkedAction():
            self.commit_action.setChecked(True)
        selected_action = self.commit_action_group.checkedAction()
        if not has_staged and has_unstaged:
            self.commit_button.setText("Stage All")
            self.commit_menu_button.setEnabled(False)
            self.commit_message_box.setEnabled(False)
            self.commit_message_box.setPlaceholderText("")
        else:
            self.commit_menu_button.setEnabled(True)
            self.commit_message_box.setEnabled(True)
            if selected_action is self.stash_action:
                self.commit_button.setText("Stash")
                self.commit_message_box.setPlaceholderText(
                    "Stash message (optional)..."
                )
            else:
                self.commit_button.setText(selected_action.text())
                self.commit_message_box.setPlaceholderText("Commit message...")
        self.commit_button.setEnabled(has_staged or has_unstaged)

    def on_commit_button_clicked(self):
        if not self.current_staged_files and self.current_unstaged_files:
            self.stage_all_requested.emit()
            return
        selected_action, message = (
            self.commit_action_group.checkedAction(),
            self.commit_message_box.toPlainText().strip(),
        )
        if selected_action is self.stash_action:
            self.stash_requested.emit(message)
            self.commit_message_box.clear()
            return
        if not message:
            return
        self.commit_requested.emit(message, False)
        self.commit_message_box.clear()

    def on_commit_merge_clicked(self):
        message = self.merge_commit_message.toPlainText().strip()
        if not message:
            QMessageBox.warning(
                self,
                "Commit Merge",
                "A commit message is required to complete the merge.",
            )
            return
        self.commit_merge_requested.emit(message)

    def on_context_menu(self, point: QPoint):
        sender_list = self.sender()
        selected_items = sender_list.selectedItems()
        if not selected_items:
            return
        file_paths = [
            item.data(Qt.ItemDataRole.UserRole)["path"] for item in selected_items
        ]
        is_staged = sender_list is self.staged_list
        menu = QMenu(self)
        if len(selected_items) == 1:
            file_path = file_paths[0]
            status = selected_items[0].data(Qt.ItemDataRole.UserRole)["status"]
            menu.addAction("Open Changes").triggered.connect(
                lambda: self.file_selected.emit(file_path, status)
            )
            menu.addAction("Open File").triggered.connect(
                lambda: self.open_file_requested.emit(file_path)
            )
            menu.addSeparator()
            menu.addAction("File History").triggered.connect(
                lambda: self.show_history_requested.emit(file_path)
            )
            menu.addAction("Reveal in File Explorer").triggered.connect(
                lambda: self.reveal_in_explorer_requested.emit(file_path)
            )
            menu.addSeparator()
        if is_staged:
            menu.addAction("Unstage Changes").triggered.connect(
                lambda: self.unstage_requested.emit(file_paths)
            )
        else:
            menu.addAction("Stage Changes").triggered.connect(
                lambda: self.stage_requested.emit(file_paths)
            )
        menu.addAction("Discard Changes").triggered.connect(
            lambda: self.discard_changes_requested.emit(file_paths)
        )
        menu.exec(sender_list.mapToGlobal(point))

    @Slot()
    def on_item_double_clicked(self, item: QListWidgetItem):
        file_data = item.data(Qt.ItemDataRole.UserRole)
        if file_data:
            self.file_selected.emit(file_data["path"], file_data["status"])

    @Slot(list)
    def enter_merge_mode(self, conflicted_files: list):
        self._populate_list(
            self.unresolved_merge_list,
            conflicted_files,
            is_merge_view=True,
            is_resolved_list=False,
        )
        self._populate_list(
            self.staged_merge_list, [], is_merge_view=True, is_resolved_list=True
        )
        self.unresolved_merge_header.setText(
            f"Unresolved Conflicts ({len(conflicted_files)})"
        )
        self.staged_merge_header.setText("Resolved (0)")
        self.commit_merge_button.setEnabled(False)
        self.stack.setCurrentWidget(self.merge_widget)

    @Slot()
    def exit_merge_mode(self):
        self.stack.setCurrentWidget(self.repo_widget)
