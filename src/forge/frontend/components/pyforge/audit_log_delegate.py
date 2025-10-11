from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QFontMetrics
from PySide6.QtCore import Qt, QSize

from .audit_log_model import AuditLogItem


class AuditLogDelegate(QStyledItemDelegate):
    """A custom delegate to handle multi-line text wrapping for explanation nodes."""

    def sizeHint(self, option, index):

        size = super().sizeHint(option, index)

        proxy_model = index.model()
        if not proxy_model:
            return size
        source_index = proxy_model.mapToSource(index)
        source_model = proxy_model.sourceModel()
        if not source_model:
            return size

        item = source_model.itemFromIndex(source_index)

        if isinstance(item, AuditLogItem) and item.item_type == "explanation_text":

            tree_view = self.parent()
            text_width = tree_view.columnWidth(index.column()) - 30

            if text_width > 0:
                fm = QFontMetrics(option.font)

                brect = fm.boundingRect(
                    0, 0, text_width, 0, Qt.TextFlag.TextWordWrap, item.text()
                )

                size.setHeight(brect.height() + 8)

        return size
