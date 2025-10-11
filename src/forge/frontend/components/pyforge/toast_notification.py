from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor


class ToastNotification(QFrame):
    """A non-intrusive notification widget that appears at the bottom of a parent widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("ToastNotification")
        self.setStyleSheet("""
            #ToastNotification {
                background-color: #3c3f41;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)

        self.message_label = QLabel()
        self.action_button = QPushButton()
        self.action_button.setFlat(True)
        self.action_button.setStyleSheet("color: #4E94D7;")

        self.layout.addWidget(self.message_label)
        self.layout.addStretch()
        self.layout.addWidget(self.action_button)

        self.hide()

        self._opacity = 0.0
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def getOpacity(self):
        return self._opacity

    def setOpacity(self, opacity):
        self._opacity = opacity
        self.update()

    opacity = Property(float, getOpacity, setOpacity)

    def paintEvent(self, event):

        if self._opacity < 1.0:
            painter = QPainter(self)
            painter.setOpacity(self._opacity)
            painter.fillRect(self.rect(), self.palette().color(self.backgroundRole()))
        super().paintEvent(event)

    def show_message(
        self, message: str, action_text: str = "", on_action=None, duration: int = 5000
    ):
        self.message_label.setText(message)

        if action_text and on_action:
            self.action_button.setText(action_text)
            self.action_button.setVisible(True)
            try:
                self.action_button.clicked.disconnect()
            except RuntimeError:
                pass
            self.action_button.clicked.connect(on_action)
            self.action_button.clicked.connect(self.fade_out)
        else:
            self.action_button.setVisible(False)

        self.fade_in()

        if duration > 0:
            QTimer.singleShot(duration, self.fade_out)

    def fade_in(self):
        self.show()
        self.animation.setDirection(QPropertyAnimation.Direction.Forward)
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()
        self.animation.setStartValue(self._opacity)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def fade_out(self):
        self.animation.setDirection(QPropertyAnimation.Direction.Backward)
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()

        try:
            self.animation.finished.disconnect(self.hide)
        except RuntimeError:
            pass
        self.animation.setStartValue(self._opacity)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.hide)
        self.animation.start()
