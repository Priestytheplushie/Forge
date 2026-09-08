from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import QPointF, Qt


class GitDiagramWidget(QWidget):
    """A widget for drawing static 'before' and 'after' Git branch diagrams."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.main_color = QColor("#569CD6")
        self.feature_color = QColor("#4EC9B0")
        self.squash_color = QColor("#C586C0")
        self.label_color = QColor("#888888")
        self.diagram_type = "create"

    def set_diagram_type(self, diagram_type: str):
        self.diagram_type = diagram_type
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont()
        font.setPointSize(9)
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(self.label_color)
        painter.drawText(10, 15, "Before:")
        painter.drawText(self.width() - 50, 15, "After:")

        if self.diagram_type == "create":
            self._draw_create_diagram(painter)
        elif self.diagram_type == "merge":
            self._draw_merge_diagram(painter)
        elif self.diagram_type == "squash":
            self._draw_squash_diagram(painter)
        elif self.diagram_type == "rebase":
            self._draw_rebase_diagram(painter)

    def _draw_branch(
        self,
        painter: QPainter,
        color: QColor,
        y_offset: int,
        start_x: int,
        num_commits: int,
        commit_offset: int = 40,
    ):
        painter.setPen(QPen(color, 2))
        painter.setBrush(QBrush(color))
        end_x = start_x + (num_commits - 1) * commit_offset
        painter.drawLine(start_x, y_offset, end_x, y_offset)
        for i in range(num_commits):
            painter.drawEllipse(QPointF(start_x + i * commit_offset, y_offset), 4, 4)

    def _draw_create_diagram(self, painter: QPainter):

        self._draw_branch(painter, self.main_color, 60, 20, 4)

        after_x = self.width() 
        self._draw_branch(painter, self.main_color, 60, after_x, 4)
        self._draw_branch(painter, self.feature_color, 40, after_x + 80, 2)
        painter.setPen(QPen(self.label_color, 1, Qt.PenStyle.DashLine))
        painter.drawLine(after_x + 80, 58, after_x + 80, 42)

    def _draw_merge_diagram(self, painter: QPainter):

        self._draw_branch(painter, self.main_color, 60, 20, 3)
        self._draw_branch(painter, self.feature_color, 40, 60, 2)

        after_x = self.width() 
        self._draw_branch(painter, self.main_color, 60, after_x, 3)
        self._draw_branch(painter, self.feature_color, 40, after_x + 40, 2)

        painter.setPen(QPen(self.main_color, 2))
        painter.setBrush(QBrush(self.main_color))
        painter.drawLine(after_x + 80, 60, after_x + 120, 60)
        painter.drawEllipse(QPointF(after_x + 120, 60), 4, 4)

        painter.setPen(QPen(self.label_color, 1, Qt.PenStyle.DashLine))
        painter.drawLine(after_x + 120, 58, after_x + 82, 42)
        painter.drawLine(after_x + 82, 60, after_x + 118, 60)

    def _draw_squash_diagram(self, painter: QPainter):

        self._draw_branch(painter, self.main_color, 60, 20, 3)
        self._draw_branch(painter, self.feature_color, 40, 60, 2)

        after_x = self.width() 

        self._draw_branch(painter, self.main_color, 60, after_x, 3)

        self._draw_branch(painter, self.feature_color, 40, after_x + 40, 2)

        painter.setPen(QPen(self.main_color, 2))
        painter.drawLine(after_x + 80, 60, after_x + 120, 60)
        painter.setBrush(QBrush(self.squash_color))
        painter.drawEllipse(QPointF(after_x + 120, 60), 4, 4)

    def _draw_rebase_diagram(self, painter: QPainter):

        self._draw_branch(painter, self.main_color, 60, 20, 3)
        self._draw_branch(painter, self.feature_color, 40, 60, 2)

        after_x = self.width() 
        self._draw_branch(painter, self.main_color, 60, after_x, 3)

        self._draw_branch(painter, self.feature_color, 60, after_x + 80, 2)