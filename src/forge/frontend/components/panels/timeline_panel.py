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
    QLineEdit,
    QMessageBox,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QDesktopServices
from PySide6.QtCore import (
    Qt,
    Signal,
    Slot,
    QPoint,
    QUrl,
    QSortFilterProxyModel,
    QModelIndex,
)

from ...assets.icon_map import (
    get_status_icon,
    get_bookmark_icon,
    get_commit_icon,
    get_trash_icon,
)
from .timeline_delegate import TimelineDelegate


class TimelineFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        item_data = index.data(Qt.ItemDataRole.UserRole)
        filter_text = self.filterRegularExpression().pattern()
        if not filter_text:
            return True
        if item_data:
            title = item_data.get("title", "").lower()
            subtitle = item_data.get("subtitle", "").lower()
            return filter_text.lower() in title or filter_text.lower() in subtitle
        return False


class TimelinePanel(QWidget):
    history_item_selected = Signal(dict)

    item_single_clicked = Signal(dict)
    restore_requested = Signal(str)
    delete_requested = Signal(str)
    delete_all_requested = Signal(str)
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
        self.save_icon = get_status_icon("circle")
        self.commit_icon = get_commit_icon(rotated=True)
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

        self.clear_history_button = QToolButton()
        self.clear_history_button.setIcon(get_trash_icon())
        self.clear_history_button.setToolTip("Clear all local history for this file")
        self.clear_history_button.setVisible(False)
        header_layout.addWidget(self.clear_history_button)

        main_layout.addWidget(header_widget)

        self.stack = QStackedWidget(self)
        main_layout.addWidget(self.stack)

        self.list_view_widget = QWidget()
        list_layout = QVBoxLayout(self.list_view_widget)
        list_layout.setContentsMargins(0, 5, 0, 0)
        list_layout.setSpacing(5)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter timeline...")
        self.filter_edit.setClearButtonEnabled(True)
        list_layout.addWidget(self.filter_edit)
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.delegate = TimelineDelegate(self)
        self.tree_view.setItemDelegate(self.delegate)
        self.tree_view.setIndentation(0)
        self.model = QStandardItemModel()
        self.proxy_model = TimelineFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.tree_view.setModel(self.proxy_model)
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

        self.tree_view.clicked.connect(self.on_item_single_clicked)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        self.button_group.idToggled.connect(self.stack.setCurrentIndex)
        self.filter_edit.textChanged.connect(
            self.proxy_model.setFilterRegularExpression
        )
        self.clear_history_button.clicked.connect(self.on_clear_all_requested)

    def on_clear_all_requested(self):
        if self.current_file_path:
            self.delete_all_requested.emit(self.current_file_path)

    def _on_path_clicked(self):
        if self.current_details_path:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self.current_details_path).parent))
            )

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

    def update_view(self, file_path: str, history_entries: list[dict]):
        self.details_view_button.setEnabled(False)
        self.list_view_button.setChecked(True)
        self.stack.setCurrentWidget(self.list_view_widget)
        self.model.clear()
        self.current_file_path = file_path

        has_local_saves = any(item["type"] == "save" for item in history_entries)
        self.clear_history_button.setVisible(has_local_saves)

        if not history_entries:
            placeholder = QStandardItem("No history found for this file.")
            placeholder.setEnabled(False)
            self.model.appendRow(placeholder)
            return

        for data in history_entries:
            item = QStandardItem()
            item.setEditable(False)
            if data["type"] == "save":
                is_pinned = data.get("meta", {}).get("pinned", False)
                item.setIcon(self.pinned_icon if is_pinned else self.save_icon)
                title = data.get("meta", {}).get("name") or "File Saved"
                subtitle = self._format_timestamp(data["timestamp"])
                tooltip = f"Type: Local Snapshot\nSaved: {subtitle}"
            else:
                item.setIcon(self.commit_icon)
                title = data.get("message", "No commit message")
                subtitle = f"{data.get('author', 'Unknown')} - {self._format_timestamp(data['timestamp'])}"
                tooltip = f"Type: Git Commit\nAuthor: {data.get('author')}\nSHA: {data.get('sha')}\n\n{title}"
            data["title"], data["subtitle"] = title, subtitle
            item.setData(data, Qt.ItemDataRole.UserRole)
            item.setToolTip(tooltip)
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
        self.clear_history_button.setVisible(False)

    @Slot(QPoint)
    def on_context_menu(self, point):
        proxy_index = self.tree_view.indexAt(point)
        if not proxy_index.isValid():
            return
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)
        menu.addAction("View Changes").triggered.connect(
            lambda: self.history_item_selected.emit(data)
        )

        if data["type"] == "save":
            history_path, meta = data["path"], data["meta"]
            menu.addAction("Compare with Current").triggered.connect(
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
                lambda: self.rename_requested.emit(history_path, meta.get("name", ""))
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

    @Slot(QModelIndex)
    def on_item_double_clicked(self, index):
        if not index.isValid():
            return
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if not item or not self.current_file_path:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.history_item_selected.emit(data)

    @Slot(QModelIndex)
    def on_item_single_clicked(self, index):
        if not index.isValid():
            return
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if not item or not self.current_file_path:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.item_single_clicked.emit(data)
