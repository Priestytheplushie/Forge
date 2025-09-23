from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget


class DebugPlaceholder(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tab_widget = QTabWidget()

        run_debug_tab = QLabel(
            "Start a debug session to see variables, call stack, and breakpoints."
        )
        run_debug_tab.setWordWrap(True)

        pyforge_tab = QLabel(
            "Launch a process with PyForge to begin live introspection."
        )
        pyforge_tab.setWordWrap(True)

        tab_widget.addTab(run_debug_tab, "Run & Debug")
        tab_widget.addTab(pyforge_tab, "PyForge")

        layout.addWidget(tab_widget)
