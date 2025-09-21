from PySide6.QtWidgets import QTreeView, QFileSystemModel, QMenu
from PySide6.QtCore import QDir, Signal, QModelIndex, Qt
from PySide6.QtGui import QAction
import os

from .file_sort_proxy_model import FileSortProxyModel


class FileExplorer(QTreeView):
    """
    An interactive file system tree view with a right-click context menu
    and functional drag-and-drop.
    """

    file_double_clicked = Signal(str)
    new_file_requested = Signal(str)
    new_folder_requested = Signal(str)
    rename_item_requested = Signal(str)
    delete_item_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.source_model = QFileSystemModel()
        self.proxy_model = FileSortProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)

        self.setModel(self.proxy_model)

        self.source_model.setRootPath(QDir.currentPath())
        self.source_model.setFilter(
            QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs | QDir.Filter.Files
        )

        self.source_model.setReadOnly(False)

        root_index = self.proxy_model.mapFromSource(
            self.source_model.index(QDir.currentPath())
        )
        self.setRootIndex(root_index)

        self.setAnimated(False)
        self.setIndentation(20)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.hideColumn(1)
        self.hideColumn(2)
        self.hideColumn(3)

        self.setWindowTitle("File Explorer")

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)

        self.doubleClicked.connect(self.on_double_clicked)

    def on_double_clicked(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        if self.source_model.isDir(source_index):
            return
        file_path = self.source_model.filePath(source_index)
        self.file_double_clicked.emit(file_path)

    def on_context_menu(self, point):
        """Creates and shows the context menu."""
        proxy_index = self.indexAt(point)
        if not proxy_index.isValid():
            source_index = self.source_model.index(self.source_model.rootPath())
        else:
            source_index = self.proxy_model.mapToSource(proxy_index)

        path = self.source_model.filePath(source_index)
        is_dir = self.source_model.isDir(source_index)

        menu = QMenu(self)

        action_new_file = QAction("New File...", self)
        action_new_folder = QAction("New Folder...", self)
        action_rename = QAction("Rename...", self)
        action_delete = QAction("Delete", self)

        new_item_parent_dir = path if is_dir else os.path.dirname(path)

        action_new_file.triggered.connect(
            lambda: self.new_file_requested.emit(new_item_parent_dir)
        )
        action_new_folder.triggered.connect(
            lambda: self.new_folder_requested.emit(new_item_parent_dir)
        )
        action_rename.triggered.connect(lambda: self.rename_item_requested.emit(path))
        action_delete.triggered.connect(lambda: self.delete_item_requested.emit(path))

        menu.addAction(action_new_file)
        menu.addAction(action_new_folder)

        if proxy_index.isValid():
            menu.addSeparator()
            menu.addAction(action_rename)
            menu.addAction(action_delete)

        menu.exec(self.viewport().mapToGlobal(point))

    def set_root_path(self, path):
        """Sets the root directory to display in the explorer."""
        self.source_model.setRootPath(path)
        root_index = self.proxy_model.mapFromSource(self.source_model.index(path))
        self.setRootIndex(root_index)
