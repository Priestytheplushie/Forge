from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDialogButtonBox,
    QFrame,
    QWidget,
)
from PySide6.QtGui import QFont
from ..components.editor.editor_widget import EditorWidget
from ..theme_manager import ThemeManager


class ToolConfirmationDialog(QDialog):
    """
    A dialog to explain a refactoring tool's action with before/after examples.
    """

    def __init__(
        self,
        tool_definition: dict,
        scope: str,
        theme_manager: ThemeManager,
        parent=None,
    ):
        super().__init__(parent)
        self.tool = tool_definition
        self.theme_manager = theme_manager

        self.setWindowTitle(f"Run '{self.tool['name']}'")
        self.setMinimumSize(800, 600)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        title_label = QLabel(self.tool["name"])
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)

        desc_label = QLabel(self.tool["description"])
        desc_label.setWordWrap(True)

        scope_label = QLabel(f"<b>Scope:</b> {scope}")
        scope_label.setWordWrap(True)

        main_layout.addWidget(title_label)
        main_layout.addWidget(desc_label)
        main_layout.addWidget(scope_label)

        editors_widget = QWidget()
        editors_layout = QHBoxLayout(editors_widget)
        editors_layout.setContentsMargins(0, 10, 0, 10)
        editors_layout.setSpacing(10)

        before_widget = self._create_editor_group(
            "Before:", self.tool["example_before"]
        )
        after_widget = self._create_editor_group("After:", self.tool["example_after"])

        editors_layout.addWidget(before_widget)
        editors_layout.addWidget(after_widget)
        main_layout.addWidget(editors_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(f"Run {self.tool['name']}")

        main_layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _create_editor_group(self, title: str, content: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(title)
        layout.addWidget(label)

        editor = EditorWidget(self.theme_manager.get_current_theme_data(), self)
        editor.setMinimumHeight(200)

        def on_editor_ready():
            editor.set_read_only(True)

        editor.set_content(content, "python", "file:///example.py", on_editor_ready)

        layout.addWidget(editor)
        return container
