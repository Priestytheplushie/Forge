from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QFileIconProvider,
    QFrame,
)
from PySide6.QtCore import Signal, Slot, QFileInfo


class MergeConflictDialog(QDialog):
    """Dialog to inform the user of a merge conflict and offer resolution options."""

    resolve_in_classic_requested = Signal()
    abort_requested = Signal()

    def __init__(
        self, icon_provider: QFileIconProvider, conflicted_files: list, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Merge Conflict Detected")
        self.setMinimumWidth(550)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("Merge Conflict Detected")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")

        description = QLabel(
            "Git could not automatically merge branches. You must resolve the conflicts in the files listed below before committing."
        )
        description.setWordWrap(True)

        files_label = QLabel("Conflicted Files:")
        self.files_list = QListWidget()
        for file_path in conflicted_files:
            file_info = QFileInfo(file_path)
            item = QListWidgetItem(icon_provider.icon(file_info), file_path)
            self.files_list.addItem(item)
        self.files_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.files_list.setStyleSheet("QListWidget { border: 1px solid #444; }")

        resolve_classic_button = QPushButton("Resolve in Classic Editor")
        resolve_classic_desc = QLabel(
            "Open files with conflict markers (<<<<<, =====, >>>>>) to manually edit."
        )
        resolve_classic_desc.setStyleSheet("color: #888;")

        resolve_3way_button = QPushButton("Resolve in Merge Editor (3-Way)")
        resolve_3way_desc = QLabel(
            "Visually compare and choose between conflicting changes in a dedicated editor."
        )
        resolve_3way_desc.setStyleSheet("color: #888;")
        resolve_3way_button.setEnabled(False)

        resolve_ai_button = QPushButton("Resolve with AI")
        resolve_ai_desc = QLabel(
            "Let the AI attempt to intelligently merge the conflicting changes."
        )
        resolve_ai_desc.setStyleSheet("color: #888;")
        resolve_ai_button.setEnabled(False)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)

        button_box = QDialogButtonBox()
        abort_button = button_box.addButton(
            "Abort Merge", QDialogButtonBox.ButtonRole.RejectRole
        )

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(files_label)
        layout.addWidget(self.files_list)
        layout.addWidget(resolve_classic_button)
        layout.addWidget(resolve_classic_desc)
        layout.addSpacing(10)
        layout.addWidget(resolve_3way_button)
        layout.addWidget(resolve_3way_desc)
        layout.addSpacing(10)
        layout.addWidget(resolve_ai_button)
        layout.addWidget(resolve_ai_desc)
        layout.addWidget(line)
        layout.addWidget(button_box)

        resolve_classic_button.clicked.connect(self.accept)
        self.accepted.connect(self.resolve_in_classic_requested)
        abort_button.clicked.connect(self.abort_requested)
        abort_button.clicked.connect(self.reject)
