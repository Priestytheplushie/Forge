import time
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QMenu,
    QStackedWidget,
    QLabel,
    QFormLayout,
    QToolButton,
    QHBoxLayout,
    QButtonGroup,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QDesktopServices
from PySide6.QtCore import Qt, Signal, Slot, QPoint, QUrl

from ...assets.icon_map import get_status_icon, get_bookmark_icon


class TimelinePanel(QWidget):
    history_item_selected = Signal(str, str)
    restore_requested = Signal(str)
    delete_requested = Signal(str)
    pin_toggled = Signal(str, bool)
    rename_requested = Signal(str, str)
    compare_with_requested = Signal(str)
    show_contents_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        self.current_file_path = None
        self.current_details_path = None
        self.history_icon = get_status_icon("circle")
        self.pinned_icon = get_bookmark_icon()

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 2, 5, 2)

        self.button_group = QButtonGroup(self)
        self.list_view_button = QToolButton()
        self.list_view_button.setText("Snapshots")
        self.list_view_button.setCheckable(True)
        self.list_view_button.setChecked(True)

        self.details_view_button = QToolButton()
        self.details_view_button.setText("Details")
        self.details_view_button.setCheckable(True)
        self.details_view_button.setEnabled(False)

        self.button_group.addButton(self.list_view_button, 0)
        self.button_group.addButton(self.details_view_button, 1)

        header_layout.addWidget(self.list_view_button)
        header_layout.addWidget(self.details_view_button)
        header_layout.addStretch()
        main_layout.addWidget(header_widget)

        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        self.list_view_widget = QWidget()
        list_layout = QVBoxLayout(self.list_view_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        list_layout.addWidget(self.tree_view)

        self.details_view_widget = QWidget()
        details_layout = QFormLayout(self.details_view_widget)
        details_layout.setContentsMargins(10, 10, 10, 10)

        self.filename_label = QLabel()
        self.saved_at_label = QLabel()
        self.stats_label = QLabel()
        self.full_path_button = QToolButton()
        self.full_path_button.setText("Click to reveal in folder")
        self.full_path_button.setStyleSheet(
            "QToolButton { border: none; text-align: left; color: #4E94D7; }"
        )
        self.full_path_button.clicked.connect(self._on_path_clicked)

        details_layout.addRow("File:", self.filename_label)
        details_layout.addRow("Saved:", self.saved_at_label)
        details_layout.addRow("Changes:", self.stats_label)
        details_layout.addRow("Path:", self.full_path_button)

        self.stack.addWidget(self.list_view_widget)
        self.stack.addWidget(self.details_view_widget)

        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        self.button_group.idToggled.connect(self.stack.setCurrentIndex)

    def _on_path_clicked(self):
        if self.current_details_path:
            folder_path = QUrl.fromLocalFile(
                str(Path(self.current_details_path).parent)
            )
            QDesktopServices.openUrl(folder_path)

    def _format_timestamp(self, ts, relative=True):
        ts_sec = ts / 1000
        if relative:
            diff = time.time() - ts_sec
            if diff < 60:
                return "just now"
            if diff < 3600:
                return f"{int(diff / 60)}m ago"
            if diff < 86400:
                return f"{int(diff / 3600)}h ago"
            return f"{int(diff / 86400)}d ago"
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_sec))

    def show_list_view(self, file_path: str, history_entries: list[tuple]):
        self.details_view_button.setEnabled(False)
        self.list_view_button.setChecked(True)
        self.stack.setCurrentWidget(self.list_view_widget)
        self.model.clear()
        self.current_file_path = file_path

        if not history_entries:
            placeholder = QStandardItem("No local history found.")
            placeholder.setEnabled(False)
            self.model.appendRow(placeholder)
            return

        for path, meta in history_entries:
            name = meta.get("name") or "File Saved"
            relative_time = self._format_timestamp(meta["timestamp"])
            display_text = f"{name} - {relative_time}"
            icon = self.pinned_icon if meta.get("pinned") else self.history_icon

            item = QStandardItem(icon, display_text)
            item.setData((str(path), meta), Qt.ItemDataRole.UserRole)
            item.setToolTip(str(path))
            self.model.appendRow(item)

    def show_details_view(self, metadata: dict):
        self.details_view_button.setEnabled(True)
        self.details_view_button.setChecked(True)
        self.stack.setCurrentWidget(self.details_view_widget)

        self.current_details_path = metadata.get("full_path", "")
        self.filename_label.setText(metadata.get("filename", "N/A"))
        saved_at_str = f"{metadata.get('full_time', 'N/A')} ({metadata.get('relative_time', 'N/A')})"
        self.saved_at_label.setText(saved_at_str)
        stats_str = f"+{metadata.get('additions', 0)} lines, -{metadata.get('deletions', 0)} lines"
        self.stats_label.setText(stats_str)
        self.full_path_button.setToolTip(self.current_details_path)

    def clear_view(self):
        self.details_view_button.setEnabled(False)
        self.list_view_button.setChecked(True)
        self.stack.setCurrentWidget(self.list_view_widget)
        self.model.clear()
        self.current_file_path = None

    @Slot(QPoint)
    def on_context_menu(self, point):
        index = self.tree_view.indexAt(point)
        if not index.isValid():
            return
        item = self.model.itemFromIndex(index)
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        history_path, meta = data

        menu = QMenu(self)
        menu.addAction("View Changes").triggered.connect(
            lambda: self.history_item_selected.emit(
                self.current_file_path, history_path
            )
        )
        menu.addAction("Compare with...").triggered.connect(
            lambda: self.compare_with_requested.emit(history_path)
        )
        menu.addAction("Show Contents").triggered.connect(
            lambda: self.show_contents_requested.emit(history_path)
        )
        menu.addSeparator()
        menu.addAction("Restore This Version").triggered.connect(
            lambda: self.restore_requested.emit(history_path)
        )
        menu.addSeparator()
        menu.addAction("Rename...").triggered.connect(
            lambda: self.rename_requested.emit(history_path, meta.get("name"))
        )
        pin_action = menu.addAction(
            "Unpin Snapshot" if meta.get("pinned") else "Pin Snapshot"
        )
        pin_action.triggered.connect(
            lambda: self.pin_toggled.emit(history_path, not meta.get("pinned"))
        )
        menu.addSeparator()
        menu.addAction("Delete Snapshot").triggered.connect(
            lambda: self.delete_requested.emit(history_path)
        )

        menu.exec(self.tree_view.mapToGlobal(point))

    @Slot(QPoint)
    def on_item_double_clicked(self, index):
        item = self.model.itemFromIndex(index)
        if not item or not self.current_file_path:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            history_path, _ = data
            self.history_item_selected.emit(self.current_file_path, history_path)
