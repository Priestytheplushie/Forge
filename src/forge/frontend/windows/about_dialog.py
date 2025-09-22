from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QWidget,
    QTextBrowser,
    QDialogButtonBox,
)
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl, Qt
from pathlib import Path


class AboutDialog(QDialog):
    def __init__(self, app_root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Forge")
        self.setMinimumSize(600, 450)

        main_layout = QVBoxLayout(self)

        tab_widget = QTabWidget()

        about_widget = self._create_about_tab()
        tab_widget.addTab(about_widget, "About Forge")

        licenses_widget = self._create_licenses_tab(app_root)
        tab_widget.addTab(licenses_widget, "Licenses")

        acknowledgements_widget = self._create_acknowledgements_tab()
        tab_widget.addTab(acknowledgements_widget, "Acknowledgements")

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)

        main_layout.addWidget(tab_widget)
        main_layout.addWidget(button_box)

    def _create_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(15)

        logo_label = QLabel("FORGE")
        logo_font = QFont()
        logo_font.setPointSize(36)
        logo_font.setBold(True)
        logo_label.setFont(logo_font)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_label = QLabel("Version 1.0.0")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline_label = QLabel("Your AI Collaborative Partner")
        tagline_label.setStyleSheet("font-style: italic; color: #888888;")
        tagline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        philosophy_text = (
            "Forge is an Integrated Development Environment built on the principle that AI should be a "
            "deeply integrated pair programmer, not just an assistant. By combining a professional-grade "
            "toolset with a context-aware intelligence layer, Forge empowers the developer as the "
            "senior partner in a collaborative coding experience."
        )
        philosophy_label = QLabel(philosophy_text)
        philosophy_label.setWordWrap(True)

        tech_text = (
            "Built with Python and Qt (PySide6). Featuring the Monaco Editor, xterm.js, "
            "and the power of Feather Icons."
        )
        tech_label = QLabel(tech_text)
        tech_label.setWordWrap(True)
        tech_label.setStyleSheet("color: #888888;")

        copyright_label = QLabel("Copyright © 2025 Priesty. All rights reserved.")

        layout.addWidget(logo_label)
        layout.addWidget(version_label)
        layout.addWidget(tagline_label)
        layout.addStretch(1)
        layout.addWidget(philosophy_label)
        layout.addWidget(tech_label)
        layout.addStretch(2)
        layout.addWidget(copyright_label)

        return widget

    def _create_licenses_tab(self, app_root: Path) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)

        notice_file = app_root / "NOTICE.md"
        if notice_file.exists():
            try:
                with open(notice_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    text_browser.setMarkdown(content)
            except Exception as e:
                text_browser.setPlainText(f"Could not load NOTICE.md: {e}")
        else:
            text_browser.setPlainText("NOTICE.md file not found.")

        layout.addWidget(text_browser)
        return widget

    def _create_acknowledgements_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        ack_text = (
            "<h2>Acknowledgements</h2>"
            "<p>We extend our sincere gratitude to the teams and communities behind the following "
            "cornerstone projects that make Forge possible:</p>"
            "<ul>"
            "<li>The Python Software Foundation</li>"
            "<li>The Qt Company (for their work on Qt and PySide)</li>"
            "<li>Microsoft (for the Monaco Editor and Visual Studio Code, which serves as an inspiration)</li>"
            "<li>The xterm.js Team</li>"
            "<li>Brandkarl (for the beautiful Forge Logo)</li>"
            "<li>Cole Bemis (for the beautiful Feather Icons)</li>"
            "<li>And all the developers of the Python libraries we rely on.</li>"
            "</ul>"
        )

        label = QLabel(ack_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)

        layout.addWidget(label)
        return widget
