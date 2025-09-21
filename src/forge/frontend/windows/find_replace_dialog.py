from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QCheckBox,
    QFrame,
)
from PySide6.QtCore import Slot, Qt


class FindReplaceDialog(QDialog):
    def __init__(self, scope: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace in Files")
        self.setMinimumWidth(500)

        self.params = {}

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        explanation_label = QLabel(
            "Find and replace text across all files in the current scope. All proposed changes "
            "will be shown in a review session before they are applied."
        )
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("color: #888888; margin-bottom: 15px;")

        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()

        form_layout.addRow(QLabel("Find:"), self.find_edit)
        form_layout.addRow(QLabel("Replace:"), self.replace_edit)

        self.case_sensitive_checkbox = QCheckBox("Case Sensitive")
        case_desc = QLabel("Match case, e.g., 'Foo' will not match 'foo'.")
        case_desc.setStyleSheet("color: #888; font-style: italic;")
        form_layout.addRow(self.case_sensitive_checkbox, case_desc)

        self.whole_word_checkbox = QCheckBox("Match Whole Word")
        whole_word_desc = QLabel(
            "Only match if the text is not part of a larger word, e.g., 'for' will not match 'format'."
        )
        whole_word_desc.setStyleSheet("color: #888; font-style: italic;")
        form_layout.addRow(self.whole_word_checkbox, whole_word_desc)

        self.regex_checkbox = QCheckBox("Use Regular Expression")
        regex_desc = QLabel(
            "Treat the 'Find' text as a regex pattern. This disables 'Match Whole Word'."
        )
        regex_desc.setStyleSheet("color: #888; font-style: italic;")
        form_layout.addRow(self.regex_checkbox, regex_desc)

        self.regex_checkbox.toggled.connect(self.whole_word_checkbox.setDisabled)

        scope_label = QLabel(f"<b>Scope:</b> {scope}")
        scope_label.setWordWrap(True)
        scope_label.setStyleSheet("margin-top: 10px;")

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Find and Review")
        self.ok_button.setEnabled(False)

        main_layout.addWidget(explanation_label)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(scope_label)
        main_layout.addWidget(button_box)

        self.find_edit.textChanged.connect(self._validate)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

    @Slot()
    def _validate(self):
        self.ok_button.setEnabled(bool(self.find_edit.text()))

    def on_accept(self):
        self.params = {
            "find_text": self.find_edit.text(),
            "replace_text": self.replace_edit.text(),
            "case_sensitive": self.case_sensitive_checkbox.isChecked(),
            "whole_word": self.whole_word_checkbox.isChecked(),
            "is_regex": self.regex_checkbox.isChecked(),
        }
        self.accept()
