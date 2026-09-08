from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QFont, QFontMetrics
from PySide6.QtCore import QPointF, Qt
from collections import deque


class GraphWidget(QWidget):
    def __init__(self, title: str, unit: str, max_value: float, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.title = title
        self.unit = unit
        self.max_value = max_value
        self.data = deque(maxlen=50)
        self.line_color = QColor("#569CD6")
        self.fill_color = QColor(86, 156, 214, 50)
        self.grid_color = QColor("#444")
        self.text_color = QColor("#D8DEE9")
        self.value_color = QColor("#B5CEA8")

    def add_data_point(self, value):
        self.data.append(float(value))
        if value > self.max_value:
            self.max_value = value * 1.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), self.palette().window().color())

        painter.setPen(self.grid_color)
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.drawLine(0, 0, 0, self.height() - 1)

        if len(self.data) > 1:
            points = QPolygonF()
            points.append(QPointF(0, self.height()))
            step = self.width() / (self.data.maxlen - 1)
            for i, value in enumerate(self.data):
                x = i * step
                y = self.height() - (value / self.max_value) * self.height()
                points.append(QPointF(x, y))
            points.append(QPointF(self.width(), self.height()))

            painter.setBrush(self.fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(points)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.line_color, 2))
            line_points = points.mid(1, len(points) - 2)
            painter.drawPolyline(line_points)

        painter.setPen(self.text_color)
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(5, 15, self.title)

        current_value = self.data[-1] if self.data else 0
        value_text = f"{current_value:.1f} {self.unit}"
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(self.value_color)
        fm = QFontMetrics(font)
        painter.drawText(
            self.width() - fm.horizontalAdvance(value_text) - 5, 20, value_text
        )