from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from ...assets.icon_map import get_status_icon


class WelcomeWidget(QWidget):
    """A native Qt widget for the welcome screen."""

    action_triggered = Signal(str)
    open_recent_requested = Signal(str)

    def __init__(self, recent_projects: list, parent=None):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(50, 50, 50, 50)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Forge")
        title.setObjectName("WelcomeTitle")
        subtitle = QLabel("Your AI Collaborative Partner")
        subtitle.setObjectName("WelcomeSubtitle")

        self.new_file_button = self._create_action_button(
            "New File...", "file-plus.svg"
        )
        self.open_folder_button = self._create_action_button(
            "Open Folder...", "folder.svg"
        )
        self.clone_repo_button = self._create_action_button(
            "Clone Repository...", "github.svg"
        )

        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)
        left_layout.addSpacing(30)
        left_layout.addWidget(self.new_file_button)
        left_layout.addWidget(self.open_folder_button)
        left_layout.addWidget(self.clone_repo_button)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        recent_title = QLabel("Recent")
        recent_title.setObjectName("RecentTitle")

        self.recent_list = QListWidget()
        for project_path in recent_projects:
            self.recent_list.addItem(project_path)

        right_layout.addWidget(recent_title)
        right_layout.addWidget(self.recent_list)

        main_layout.addWidget(left_widget, 60)
        main_layout.addWidget(right_widget, 40)

        self.open_folder_button.clicked.connect(
            lambda: self.action_triggered.emit("open_folder")
        )
        self.clone_repo_button.clicked.connect(
            lambda: self.action_triggered.emit("clone_repo")
        )
        self.recent_list.itemClicked.connect(
            lambda item: self.open_recent_requested.emit(item.text())
        )

    def _create_action_button(self, text: str, icon_name: str) -> QPushButton:
        button = QPushButton(f" {text}")
        button.setIcon(get_status_icon(icon_name))
        button.setObjectName("WelcomeButton")
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return button

    def apply_theme(self, theme_data: dict):

        pass
