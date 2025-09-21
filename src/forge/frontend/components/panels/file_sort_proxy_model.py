from PySide6.QtCore import QSortFilterProxyModel, QModelIndex
from PySide6.QtWidgets import QFileSystemModel


class FileSortProxyModel(QSortFilterProxyModel):
    """
    A proxy model that sorts directories before files and filters out specific folders.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hidden_folders = {".git", ".forge", "__pycache__", ".venv", "node_modules"}

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        if source_index.isValid():
            file_name = self.sourceModel().fileName(source_index)
            if file_name in self.hidden_folders:
                return False
        return super().filterAcceptsRow(source_row, source_parent)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """
        Custom sorting logic.
        - Directories are always "less than" (come before) files.
        - Otherwise, falls back to the default alphabetical sort.
        """

        source_model = self.sourceModel()

        left_is_dir = source_model.isDir(left)
        right_is_dir = source_model.isDir(right)

        if left_is_dir and not right_is_dir:
            return True

        if not left_is_dir and right_is_dir:
            return False

        return super().lessThan(left, right)
