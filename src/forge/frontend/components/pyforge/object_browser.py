from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QToolButton,
    QHBoxLayout,
    QLabel,
    QMenu,
    QLineEdit,
    QFrame,
)
from PySide6.QtGui import QAction, QDrag
from PySide6.QtCore import Signal, QTimer, Qt, QMimeData
from ...assets.icon_map import get_status_icon
from .object_tree_model import ObjectTreeModel, ObjectTreeItem
from .object_tree_delegate import ObjectTreeDelegate
from .toast_notification import ToastNotification


class ObjectBrowser(QWidget):
    discover_requested = Signal(str, object)
    refresh_requested = Signal()
    collapse_requested = Signal()
    run_requested = Signal(object)
    create_instance_requested = Signal(object)
    subscribe_requested = Signal(str, bool)
    unsubscribe_requested = Signal(str)
    copy_reference_requested = Signal(str)
    inspect_requested = Signal(object)
    delete_requested = Signal(object)
    watch_requested = Signal(str, bool, bool)
    show_legend_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("PyForgePanelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.addWidget(QLabel("Object Browser"))

        main_layout.addWidget(header)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter objects...")
        self.filter_edit.setClearButtonEnabled(True)
        toolbar_layout.addWidget(self.filter_edit)

        help_button = QToolButton()
        help_button.setIcon(get_status_icon("help-circle"))
        help_button.setToolTip("Show Object Browser Legend")
        toolbar_layout.addWidget(help_button)

        collapse_button = QToolButton()
        collapse_button.setIcon(get_status_icon("minimize-2"))
        collapse_button.setToolTip("Collapse All")
        toolbar_layout.addWidget(collapse_button)

        refresh_button = QToolButton()
        refresh_button.setIcon(get_status_icon("refresh-cw"))
        refresh_button.setToolTip("Refresh Scope")
        toolbar_layout.addWidget(refresh_button)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setIndentation(15)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.setDragEnabled(True)
        self.tree_view.setDragDropMode(QTreeView.DragDropMode.DragOnly)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)

        self.model = ObjectTreeModel(self)
        self.tree_view.setModel(self.model)

        self.delegate = ObjectTreeDelegate(self)
        self.tree_view.setItemDelegate(self.delegate)

        main_layout.addWidget(toolbar)
        main_layout.addWidget(self.tree_view)

        self.tree_view.expanded.connect(self.on_item_expanded)
        self.tree_view.collapsed.connect(self.on_item_collapsed)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        refresh_button.clicked.connect(
            lambda checked=False: self.refresh_requested.emit()
        )
        collapse_button.clicked.connect(
            lambda checked=False: self.collapse_requested.emit()
        )
        help_button.clicked.connect(
            lambda checked=False: self.show_legend_requested.emit()
        )
        self.filter_edit.textChanged.connect(self.model.setFilterWildcard)

    def on_item_expanded(self, index):
        source_index = self.model.mapToSource(index)
        item = self.model.sourceModel().itemFromIndex(source_index)
        if isinstance(item, ObjectTreeItem):
            if item.is_fetching:
                path = self.model.get_path_for_item(item)
                self.discover_requested.emit(path, item)
            else:
                if (
                    item.rowCount() == 1
                    and not item.child(0).isEnabled()
                    and item.full_data.get("expandable", False)
                ):
                    try:
                        item.removeRow(0)
                    except Exception:
                        pass
                    loading_child = ObjectTreeItem("Loading...")
                    loading_child.setEnabled(False)
                    item.appendRow(loading_child)
                    item.is_fetching = True
                    path = self.model.get_path_for_item(item)
                    self.discover_requested.emit(path, item)
            if item.node_type in ["instance", "attribute_collection"]:
                self.subscribe_requested.emit(item.node_path, False)

            if item.node_type in ["class", "instance_group_for_class"]:
                self.watch_requested.emit(item.node_path, False, False)

    def on_item_collapsed(self, index):
        source_index = self.model.mapToSource(index)
        item = self.model.sourceModel().itemFromIndex(source_index)
        if isinstance(item, ObjectTreeItem) and item.node_type in [
            "instance",
            "attribute_collection",
        ]:
            self.unsubscribe_requested.emit(item.node_path)

    def on_context_menu(self, point):
        index = self.tree_view.indexAt(point)
        if not index.isValid():
            return

        source_index = self.model.mapToSource(index)
        item = self.model.sourceModel().itemFromIndex(source_index)
        if not isinstance(item, ObjectTreeItem):
            return

        menu = QMenu(self)

        menu.addAction("Inspect...").triggered.connect(
            lambda: self.inspect_requested.emit(item)
        )
        menu.addSeparator()

        if item.node_type in ["function", "method"]:
            menu.addAction("Run...").triggered.connect(
                lambda: self.run_requested.emit(item)
            )

        if item.node_type == "instance":
            menu.addAction("Delete...").triggered.connect(
                lambda: self.delete_requested.emit(item)
            )
            is_pinned = item.is_pinned
            pin_action = menu.addAction(
                "Unpin from Subscriptions" if is_pinned else "Pin to Subscriptions"
            )
            pin_action.setIcon(get_status_icon("pin"))
            pin_action.triggered.connect(
                lambda: self.subscribe_requested.emit(item.node_path, not is_pinned)
            )

        if item.node_type == "class":
            is_watched = bool(item.full_data.get("watched", False))
            action_text = (
                "Stop Watching for New Instances"
                if is_watched
                else "Watch for New Instances"
            )
            watch_action = menu.addAction(action_text)
            watch_action.triggered.connect(
                lambda _, p=item.node_path, w=is_watched: self.watch_requested.emit(
                    p, w, True
                )
            )
            menu.addAction("Create New Instance...").triggered.connect(
                lambda: self.create_instance_requested.emit(item)
            )

        if item.node_path:
            menu.addAction("Copy Reference").triggered.connect(
                lambda: self.copy_reference_requested.emit(item.node_path)
            )

        if len(menu.actions()) <= 2:
            menu.addSeparator()
            action = menu.addAction("(No other actions available)")
            action.setEnabled(False)

        menu.exec(self.tree_view.viewport().mapToGlobal(point))

    def get_expansion_state(self):
        expanded = []
        root_index = self.model.mapFromSource(
            self.model.sourceModel().invisibleRootItem().index()
        )
        self._get_expansion_state_recursive(root_index, expanded)
        return expanded

    def _get_expansion_state_recursive(self, parent_index, expanded_list):
        for row in range(self.model.rowCount(parent_index)):
            index = self.model.index(row, 0, parent_index)
            if self.tree_view.isExpanded(index):
                source_index = self.model.mapToSource(index)
                item = self.model.sourceModel().itemFromIndex(source_index)
                path = self.model.get_path_for_item(item)
                if path:
                    expanded_list.append(path)
                self._get_expansion_state_recursive(index, expanded_list)

    def restore_expansion_state(self, expanded_paths):
        for path in expanded_paths:
            index = self.model.find_item_by_path(path)
            if index.isValid() and not self.tree_view.isExpanded(index):
                QTimer.singleShot(0, lambda idx=index: self.tree_view.expand(idx))
