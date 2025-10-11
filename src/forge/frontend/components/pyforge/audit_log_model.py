from PySide6.QtGui import QStandardItem, QIcon


class AuditLogItem(QStandardItem):
    """A custom item to hold the full data for a log entry."""

    def __init__(self, *args):
        super().__init__(*args)
        self.full_data = {}
        self.item_type = None
