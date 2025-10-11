from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, QRegularExpression
from PySide6.QtWidgets import QFileSystemModel
from PySide6.QtCore import Qt


class FileSortProxyModel(QSortFilterProxyModel):
    """
    A proxy model that sorts directories before files, filters out specific folders,
    and provides advanced recursive filtering.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hidden_folders = {".git", ".forge", "__pycache__", ".venv", "node_modules"}
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(0)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model = self.sourceModel()
        source_index = source_model.index(source_row, 0, source_parent)

        if not source_index.isValid():
            return False

        file_name = source_model.fileName(source_index)

        if file_name in self.hidden_folders:
            return False

        filter_re = self.filterRegularExpression()
        if not filter_re or filter_re.pattern() == "":
            return True

        if filter_re.match(file_name).hasMatch():
            return True

        if source_model.isDir(source_index):
            return self._has_matching_child(source_index)

        return False

    def _has_matching_child(self, parent_index: QModelIndex) -> bool:
        """Recursively checks if a directory contains any children that match the filter."""
        source_model = self.sourceModel()
        filter_re = self.filterRegularExpression()

        for i in range(source_model.rowCount(parent_index)):
            child_index = source_model.index(i, 0, parent_index)
            if not child_index.isValid():
                continue

            file_name = source_model.fileName(child_index)
            if filter_re.match(file_name).hasMatch():
                return True

            if source_model.isDir(child_index):
                if self._has_matching_child(child_index):
                    return True
        return False

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
