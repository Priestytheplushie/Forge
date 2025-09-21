from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Signal, Slot
import re


class CreateBranchDialog(QDialog):
    """A dialog for creating a new Git branch."""

    create_branch_requested = Signal(str, str)

    INVALID_BRANCH_CHARS_RE = re.compile(
        r"[\s~^:?*\[\\ G]" r"|\.\." r"|/\." r"|/$" r"|\.lock$" r"|@\{"
    )

    def __init__(self, branches: list, current_branch: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Branch")
        self.setMinimumWidth(450)

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        explanation = QLabel(
            "A branch is like an alternate universe for your code. "
            "Create a new branch to work on features or fixes without affecting the main version. "
            "You can merge your changes back in later."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #888888; margin-bottom: 15px;")

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("new-feature-branch")

        self.base_combo = QComboBox()
        self.base_combo.addItems(sorted(branches))
        if current_branch in branches:
            self.base_combo.setCurrentText(current_branch)

        self.dynamic_explanation_label = QLabel()
        self.dynamic_explanation_label.setWordWrap(True)
        self.dynamic_explanation_label.setStyleSheet(
            "color: #888888; font-style: italic; margin-top: 5px;"
        )

        form_layout.addRow(QLabel("New Branch Name:"), self.name_edit)
        form_layout.addRow(QLabel("Create From:"), self.base_combo)
        form_layout.addRow(self.dynamic_explanation_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Create Branch")
        self.ok_button.setEnabled(False)

        main_layout.addWidget(explanation)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        self.name_edit.textChanged.connect(self._validate_and_update)
        self.base_combo.currentTextChanged.connect(self._update_dynamic_explanation)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        self._update_dynamic_explanation()

    @Slot()
    def _validate_and_update(self):
        name = self.name_edit.text()
        is_valid = bool(name.strip()) and not self.INVALID_BRANCH_CHARS_RE.search(name)

        self.ok_button.setEnabled(is_valid)

        if not is_valid and bool(name):
            self.dynamic_explanation_label.setText(
                "<font color='#F77669'>Branch name cannot contain spaces or invalid characters (~, ^, :, ?, *, [).</font>"
            )
        else:
            self._update_dynamic_explanation()

    @Slot()
    def _update_dynamic_explanation(self):
        new_branch_name = self.name_edit.text().strip() or "[new-branch-name]"
        base_branch = self.base_combo.currentText()
        text = (
            f"You are creating a new branch '{new_branch_name}' diverging from the '{base_branch}' branch. "
            f"All code on '{base_branch}' will be copied to your new branch to start."
        )
        self.dynamic_explanation_label.setText(text)

        if self.INVALID_BRANCH_CHARS_RE.search(self.name_edit.text()):
            self.dynamic_explanation_label.setText(
                "<font color='#F77669'>Branch name cannot contain spaces or invalid characters (~, ^, :, ?, *, [).</font>"
            )

    def on_accept(self):
        name = self.name_edit.text().strip()
        base = self.base_combo.currentText()
        if name and base:
            self.create_branch_requested.emit(name, base)
            self.accept()
