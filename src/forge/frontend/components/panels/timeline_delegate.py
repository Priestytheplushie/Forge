from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QColor, QPen
from PySide6.QtCore import Qt, QRect


class TimelineDelegate(QStyledItemDelegate):
    """A custom delegate to draw timeline items with connecting lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_color = QColor("#434C5E")
        self.text_color = QColor("#D8DEE9")
        self.subtext_color = QColor("#888888")

    def paint(self, painter, option, index):
        painter.save()

        item_data = index.data(Qt.ItemDataRole.UserRole)
        icon = index.data(Qt.ItemDataRole.DecorationRole)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        pen = QPen(self.line_color, 1.5)
        painter.setPen(pen)
        center_x = option.rect.x() + 16

        if index.row() > 0:
            painter.drawLine(
                center_x, option.rect.top(), center_x, center_x - option.rect.top() - 2
            )

        if index.row() < index.model().rowCount(index.parent()) - 1:
            painter.drawLine(
                center_x,
                option.rect.bottom(),
                center_x,
                center_x - option.rect.top() + 2,
            )

        if icon:
            icon_rect = QRect(
                option.rect.left() + 8,
                option.rect.top() + (option.rect.height() - 16) 
                16,
                16,
            )
            icon.paint(painter, icon_rect)

        if item_data:
            main_text = item_data.get("title", "Unknown Event")
            sub_text = item_data.get("subtitle", "")

            main_text_rect = option.rect.adjusted(36, 4, -4, -4)
            sub_text_rect = option.rect.adjusted(36, 20, -4, -4)

            painter.setPen(self.text_color)
            painter.drawText(
                main_text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                main_text,
            )

            painter.setPen(self.subtext_color)
            painter.drawText(
                sub_text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                sub_text,
            )

        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(40)
        return size
