from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QDialogButtonBox,
    QFormLayout,
    QWidget,
)
from PySide6.QtCore import Signal, Slot
from pathlib import Path


class CloneDialog(QDialog):
    clone_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clone Repository")
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://github.com/user/repo.git")
        form_layout.addRow(QLabel("Repository URL:"), self.url_edit)

        help_label = QLabel(
            "Paste the URL from a web-based Git service like GitHub, GitLab, or Bitbucket.\n"
            "You can usually find it by clicking the 'Code' or 'Clone' button on the repository's page."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #888888; margin-top: 2px; margin-bottom: 8px;")

        form_layout.addRow(help_label)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_for_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_button)
        form_layout.addRow(QLabel("Local Path:"), path_widget)

        self.url_edit.textChanged.connect(self.suggest_local_path)

        self.progress_output = QTextEdit()
        self.progress_output.setReadOnly(True)
        self.progress_output.setVisible(False)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.clone_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.clone_button.setText("Clone")
        self.button_box.accepted.connect(self.on_accept)
        self.button_box.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.progress_output)
        main_layout.addWidget(self.button_box)

    def browse_for_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder to Clone Into")
        if path:
            self.path_edit.setText(path)

    def on_accept(self):
        url = self.url_edit.text().strip()
        path = self.path_edit.text().strip()
        if url and path:
            self.clone_requested.emit(url, path)
            self.clone_button.setEnabled(False)
            self.progress_output.setVisible(True)
            self.progress_output.clear()

    @Slot(str)
    def suggest_local_path(self, url: str):

        if self.path_edit.text():
            return

        try:
            if url.endswith(".git"):
                repo_name = Path(url).stem

                default_dir = Path.home() / "Documents"
                self.path_edit.setText(str(default_dir / repo_name))
        except Exception:

            pass

    @Slot(str)
    def update_progress(self, message: str):
        self.progress_output.append(message)

    @Slot(bool)
    def on_clone_finished(self, success: bool):
        if success:
            self.accept()
        else:
            self.clone_button.setEnabled(True)
