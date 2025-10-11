from PySide6.QtWidgets import (
    QTreeView,
    QFileSystemModel,
    QMenu,
    QLineEdit,
    QToolButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)
from PySide6.QtCore import QDir, Signal, QModelIndex, Qt, QRegularExpression, Slot
from PySide6.QtGui import QAction
import os

from .file_sort_proxy_model import FileSortProxyModel
from ...assets.icon_map import get_status_icon
from ..icon_provider import CustomIconProvider


class FileExplorer(QWidget):
    """
    An enhanced file system tree view with filtering and a context menu for
    both regular files and PyForge scripts.
    """

    file_double_clicked = Signal(str)
    new_file_requested = Signal(str)
    new_folder_requested = Signal(str)
    rename_item_requested = Signal(str)
    delete_item_requested = Signal(str)
    refactor_requested = Signal(str, str)

    script_double_clicked = Signal(str)
    new_script_requested = Signal(bool)
    rename_script_requested = Signal(str)
    delete_script_requested = Signal(str)
    duplicate_script_requested = Signal(str)
    move_script_requested = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.refactor_tool_definitions = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter files...")
        self.filter_edit.setClearButtonEnabled(True)

        toolbar_layout.addWidget(self.filter_edit)

        main_layout.addWidget(toolbar)

        self.tree_view = QTreeView()
        self.source_model = QFileSystemModel()

        self.icon_provider = CustomIconProvider()
        self.source_model.setIconProvider(self.icon_provider)

        self.proxy_model = FileSortProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.tree_view.setModel(self.proxy_model)
        main_layout.addWidget(self.tree_view)

        self.source_model.setRootPath(QDir.currentPath())
        self.source_model.setFilter(
            QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files
        )
        self.source_model.setReadOnly(False)

        root_index = self.proxy_model.mapFromSource(
            self.source_model.index(QDir.currentPath())
        )
        self.tree_view.setRootIndex(root_index)

        self.tree_view.setAnimated(False)
        self.tree_view.setIndentation(20)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        for i in range(1, 4):
            self.tree_view.hideColumn(i)

        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setDragDropMode(QTreeView.DragDropMode.InternalMove)

        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        self.tree_view.doubleClicked.connect(self.on_double_clicked)
        self.filter_edit.textChanged.connect(self.on_filter_changed)

    @Slot(str)
    def on_filter_changed(self, text: str):
        self.proxy_model.setFilterRegularExpression(text)

    def set_refactor_tools(self, tools: list):
        self.refactor_tool_definitions = tools

    def on_double_clicked(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        file_path = self.source_model.filePath(source_index)

        if self.source_model.isDir(source_index):
            return

        if file_path.endswith(".pfscript"):
            self.script_double_clicked.emit(file_path)
        else:
            self.file_double_clicked.emit(file_path)

    def on_context_menu(self, point):
        proxy_index = self.tree_view.indexAt(point)
        is_valid_index = proxy_index.isValid()

        if is_valid_index:
            source_index = self.proxy_model.mapToSource(proxy_index)
            path = self.source_model.filePath(source_index)
            is_dir = self.source_model.isDir(source_index)
            new_item_parent_dir = path if is_dir else os.path.dirname(path)
        else:
            path = self.source_model.rootPath()
            is_dir = True
            new_item_parent_dir = path

        menu = QMenu(self)
        is_script = path.endswith(".pfscript")

        if is_script:
            menu.addAction("Rename Script...").triggered.connect(
                lambda: self.rename_script_requested.emit(path)
            )
            menu.addAction("Delete Script...").triggered.connect(
                lambda: self.delete_script_requested.emit(path)
            )
            menu.addAction("Duplicate Script...").triggered.connect(
                lambda: self.duplicate_script_requested.emit(path)
            )
            menu.addSeparator()
            is_global = ".forge/scripts" in path.replace("\\", "/")
            if is_global:
                menu.addAction("Move to Workspace").triggered.connect(
                    lambda: self.move_script_requested.emit(path, False)
                )
            else:
                menu.addAction("Move to Global Scripts").triggered.connect(
                    lambda: self.move_script_requested.emit(path, True)
                )
        else:
            action_new_file = menu.addAction("New File...")
            action_new_folder = menu.addAction("New Folder...")
            action_new_file.triggered.connect(
                lambda: self.new_file_requested.emit(new_item_parent_dir)
            )
            action_new_folder.triggered.connect(
                lambda: self.new_folder_requested.emit(new_item_parent_dir)
            )

            script_menu = menu.addMenu("PyForge Script")
            script_menu.addAction("New Workspace Script").triggered.connect(
                lambda: self.new_script_requested.emit(False)
            )
            script_menu.addAction("New Global Script").triggered.connect(
                lambda: self.new_script_requested.emit(True)
            )

            if is_valid_index:
                menu.addSeparator()
                menu.addAction("Rename...").triggered.connect(
                    lambda: self.rename_item_requested.emit(path)
                )
                menu.addAction("Delete").triggered.connect(
                    lambda: self.delete_item_requested.emit(path)
                )

        if not is_script and is_valid_index:
            menu.addSeparator()
            refactor_menu = menu.addMenu("Refactor")
            can_refactor = is_dir or path.endswith(".py")
            if can_refactor:
                has_tools = False
                for tool in self.refactor_tool_definitions:
                    allowed_scope = ("directory" in tool["scopes"] and is_dir) or (
                        "file" in tool["scopes"] and not is_dir
                    )
                    if allowed_scope:
                        has_tools = True
                        if tool.get("separator_before"):
                            refactor_menu.addSeparator()
                        action = refactor_menu.addAction(tool["name"])
                        action.triggered.connect(
                            lambda checked=False, tool_id=tool[
                                "id"
                            ], p=path: self.refactor_requested.emit(tool_id, p)
                        )
                if not has_tools:
                    refactor_menu.setEnabled(False)
            else:
                refactor_menu.setEnabled(False)

        menu.exec(self.tree_view.viewport().mapToGlobal(point))

    def set_root_path(self, path):
        """Sets the root directory to display in the explorer."""
        self.source_model.setRootPath(path)
        root_index = self.proxy_model.mapFromSource(self.source_model.index(path))
        self.tree_view.setRootIndex(root_index)
