from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QCheckBox,
    QLabel,
    QTabWidget,
)


class SearchView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tab_widget = QTabWidget()

        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.addWidget(QLineEdit(placeholderText="Search in files..."))
        files_layout.addWidget(QLineEdit(placeholderText="Replace..."))
        files_layout.addWidget(QCheckBox("Case Sensitive"))
        files_layout.addWidget(QCheckBox("Use Regular Expression"))
        files_layout.addStretch()

        workspace_widget = QWidget()
        workspace_layout = QVBoxLayout(workspace_widget)
        workspace_layout.addWidget(QLineEdit(placeholderText="Search for symbols..."))
        workspace_layout.addStretch()

        tools_widget = QWidget()
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.addWidget(
            QLineEdit(placeholderText="Search for tools and commands...")
        )
        tools_layout.addStretch()

        tab_widget.addTab(files_widget, "Files")
        tab_widget.addTab(workspace_widget, "Workspace")
        tab_widget.addTab(tools_widget, "Tools")

        layout.addWidget(tab_widget)
