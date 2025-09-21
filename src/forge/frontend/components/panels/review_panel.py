from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QPushButton,
    QLabel,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QMenu,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Signal, Slot, Qt, QFileInfo, QPoint


class ReviewPanel(QWidget):
    """A panel to display and manage files changed during a review session."""

    file_selected = Signal(dict)
    accept_all_requested = Signal()
    discard_all_requested = Signal()
    export_to_branch_requested = Signal()

    accept_file_requested = Signal(dict)
    discard_file_requested = Signal(dict)
    save_as_snapshot_requested = Signal(dict)
    save_as_requested = Signal(dict)

    def __init__(self, icon_provider: QFileIconProvider, parent=None):
        super().__init__(parent)
        self.icon_provider = icon_provider

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 15, 10, 10)
        main_layout.setSpacing(10)

        title = QLabel("Proposed Changes")
        title.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self.summary_label = QLabel("Refactoring tools have proposed changes.")
        self.summary_label.setWordWrap(True)

        instruction_label = QLabel(
            "Double-click a file to review its diff. Use the buttons above or right-click a file for more actions."
        )
        instruction_label.setWordWrap(True)
        instruction_label.setStyleSheet("color: #888888; font-style: italic;")

        self.accept_all_button = QPushButton("Accept All Changes")
        self.export_to_branch_button = QPushButton("Export to New Branch...")

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.discard_all_button = QPushButton("Discard All Changes")

        self.file_list_view = QTreeView()
        self.file_list_view.setHeaderHidden(True)
        self.file_list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.model = QStandardItemModel()
        self.file_list_view.setModel(self.model)

        main_layout.addWidget(title)
        main_layout.addWidget(self.summary_label)
        main_layout.addWidget(instruction_label)
        main_layout.addSpacing(5)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.accept_all_button)
        button_layout.addWidget(self.export_to_branch_button)
        main_layout.addLayout(button_layout)

        main_layout.addWidget(self.discard_all_button)

        main_layout.addWidget(line)
        main_layout.addWidget(self.file_list_view)

        self.file_list_view.doubleClicked.connect(self.on_double_click)
        self.accept_all_button.clicked.connect(self.accept_all_requested)
        self.discard_all_button.clicked.connect(self.discard_all_requested)
        self.export_to_branch_button.clicked.connect(self.export_to_branch_requested)
        self.file_list_view.customContextMenuRequested.connect(self.on_context_menu)

    def set_summary_text(self, summary_text: str):
        self.summary_label.setText(summary_text)

    def update_changes(self, changes: dict):
        self.model.clear()
        for file_path_str, data in changes.items():
            file_info = QFileInfo(file_path_str)
            file_item = QStandardItem(
                self.icon_provider.icon(file_info), file_info.fileName()
            )
            file_item.setData(data, Qt.ItemDataRole.UserRole)
            file_item.setEditable(False)

            for summary in data.get("summaries", []):
                summary_item = QStandardItem(summary)
                summary_item.setEditable(False)
                summary_item.setForeground(Qt.GlobalColor.gray)
                file_item.appendRow(summary_item)

            self.model.appendRow(file_item)
        self.file_list_view.expandAll()

    def get_next_file_data(self, current_file_path: str) -> dict | None:
        found_current = False
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if found_current and item_data:
                return item_data
            if item_data and item_data["original_path"] == current_file_path:
                found_current = True
        return None

    def remove_file(self, file_path_str: str):
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if (
                item
                and item.data(Qt.ItemDataRole.UserRole)["original_path"]
                == file_path_str
            ):
                self.model.removeRow(row)
                break

    def get_item_count(self) -> int:
        return self.model.rowCount()

    @Slot()
    def on_double_click(self, index):
        item = self.model.itemFromIndex(index)
        if item.parent():
            item = item.parent()

        if item and item.data(Qt.ItemDataRole.UserRole):
            self.file_selected.emit(item.data(Qt.ItemDataRole.UserRole))

    @Slot(QPoint)
    def on_context_menu(self, point: QPoint):
        index = self.file_list_view.indexAt(point)
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        if item.parent():
            item = item.parent()

        change_data = item.data(Qt.ItemDataRole.UserRole)
        if not change_data:
            return

        menu = QMenu(self)
        menu.addAction("Accept Changes").triggered.connect(
            lambda: self.accept_file_requested.emit(change_data)
        )
        menu.addAction("Discard Changes").triggered.connect(
            lambda: self.discard_file_requested.emit(change_data)
        )
        menu.addSeparator()
        menu.addAction("Save as Snapshot...").triggered.connect(
            lambda: self.save_as_snapshot_requested.emit(change_data)
        )
        menu.addAction("Save As...").triggered.connect(
            lambda: self.save_as_requested.emit(change_data)
        )

        menu.exec(self.file_list_view.mapToGlobal(point))
