from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QColor
from pathlib import Path


class WelcomePage(QWebEnginePage):
    """Custom QWebEnginePage to intercept action links."""

    action_triggered = Signal(str)

    def acceptNavigationRequest(self, url, _type, _isMainFrame):
        """Overrides the navigation request to handle custom 'action:' scheme."""
        if url.scheme() == "action":
            action = url.path()
            print(f"Welcome screen action triggered: {action}")
            self.action_triggered.emit(action)
            return False
        return True


class WelcomeWidget(QWidget):
    """A widget to display a welcome screen."""

    action_triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        profile = QWebEngineProfile.defaultProfile()
        self.web_view = QWebEngineView()
        page = WelcomePage(profile, self)

        page.setBackgroundColor(QColor("#1e1e1e"))
        self.web_view.setPage(page)
        self.layout().addWidget(self.web_view)

        page.action_triggered.connect(self.action_triggered)

        html_file_path = Path(__file__).resolve().parent / "welcome.html"
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_file_path)))
