from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QSizePolicy
from .pyforge_launch_view import PyForgeLaunchView


class DebugView(QWidget):
    """
    The default view for the Debug activity, allowing the user to
    choose between starting a DAP session or a PyForge session.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.tab_widget = QTabWidget()

        run_debug_tab = QWidget()
        run_debug_layout = QVBoxLayout(run_debug_tab)
        dap_label = QLabel(
            "Start a DAP debug session to use breakpoints, step through code, and inspect variables."
        )
        dap_label.setWordWrap(True)
        dap_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
        )
        run_debug_layout.addWidget(dap_label)
        run_debug_layout.addStretch()

        self.pyforge_launch_view = PyForgeLaunchView(self)

        self.tab_widget.addTab(run_debug_tab, "Run & Debug")
        self.tab_widget.addTab(self.pyforge_launch_view, "PyForge")

        layout.addWidget(self.tab_widget)
