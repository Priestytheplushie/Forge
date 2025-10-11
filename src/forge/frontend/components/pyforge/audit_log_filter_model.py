from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, QRegularExpression
from PySide6.QtGui import QStandardItemModel


class AuditLogFilterProxyModel(QSortFilterProxyModel):
    """A recursive filter for the audit log tree view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """
        Accepts a row if the item itself matches, or if any of its
        descendants match the filter.
        """
        source_model = self.sourceModel()
        source_index = source_model.index(source_row, 0, source_parent)

        if not self.filterRegularExpression().pattern():
            return True

        return self.has_matching_descendant(source_index)

    def has_matching_descendant(self, source_index: QModelIndex) -> bool:
        """
        Recursively checks if an item or any of its children match the filter text.
        """
        source_model = self.sourceModel()

        text = source_model.data(source_index, self.filterRole())
        if self.filterRegularExpression().match(text).hasMatch():
            return True

        for i in range(source_model.rowCount(source_index)):
            child_index = source_model.index(i, 0, source_index)
            if self.has_matching_descendant(child_index):
                return True

        return False
