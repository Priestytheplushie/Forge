from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QWidget,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
    QTreeView,
)
from PySide6.QtCore import Signal, Slot, QSortFilterProxyModel, QModelIndex, Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from ..assets.icon_map import get_status_icon, get_pyforge_object_icon
import inspect


class ObjectPickerModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(0)

    def filterAcceptsRow(self, source_row, source_parent):
        if not self.filterRegularExpression().pattern():
            return True
        return super().filterAcceptsRow(source_row, source_parent)


class ObjectPickerDialog(QDialog):
    """A dialog with a categorized tree view to select a known live object."""

    object_selected = Signal(str, str)

    def __init__(self, objects_by_type: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Object")
        self.setMinimumSize(450, 400)

        layout = QVBoxLayout(self)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by name or type...")

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)

        self.source_model = QStandardItemModel()
        self.proxy_model = ObjectPickerModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.tree_view.setModel(self.proxy_model)

        root = self.source_model.invisibleRootItem()
        for type_name, objects in sorted(objects_by_type.items()):
            type_item = QStandardItem(get_pyforge_object_icon("class"), type_name)
            type_item.setEditable(False)
            root.appendRow(type_item)
            for obj in objects:
                instance_item = QStandardItem(
                    get_pyforge_object_icon("instance"), obj["name"]
                )
                instance_item.setEditable(False)
                instance_item.setData(obj, Qt.ItemDataRole.UserRole)
                type_item.appendRow(instance_item)

        layout.addWidget(self.filter_edit)
        layout.addWidget(self.tree_view)

        self.filter_edit.textChanged.connect(
            self.proxy_model.setFilterRegularExpression
        )
        self.tree_view.doubleClicked.connect(self.on_accept)

    def on_accept(self, index):
        proxy_index = self.tree_view.currentIndex()
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.source_model.itemFromIndex(source_index)
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return

        selected_obj = item.data(Qt.ItemDataRole.UserRole)
        self.object_selected.emit(selected_obj["name"], selected_obj["path"])
        self.accept()


class FunctionRunnerDialog(QDialog):
    """A dialog to dynamically build a form to run a function with arguments."""

    run_requested = Signal(list, dict, str)

    def __init__(
        self,
        function_name: str,
        parameters: list,
        docstring: str,
        all_objects: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(function_name)
        self.setMinimumWidth(450)

        self.all_objects = all_objects
        self.parameters = parameters
        self.arg_widgets = {}
        self.required_fields = []
        self.is_constructor = function_name.startswith("new ")

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        if docstring:
            doc_label = QLabel(docstring)
            doc_label.setWordWrap(True)
            doc_label.setStyleSheet(
                "color: #888888; margin-bottom: 10px; font-style: italic;"
            )
            main_layout.addWidget(doc_label)

        explanation = QLabel(
            "Enter arguments as Python expressions (e.g., `'hello'`, `123`).\n"
            "Use the picker button to select live objects as arguments."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #888888; margin-bottom: 15px;")
        main_layout.addWidget(explanation)

        for param in self.parameters:
            name = param["name"]
            if name in ("self", "cls"):
                continue

            kind = param["kind"]
            default = param.get("default", str(inspect.Parameter.empty))

            placeholder = ""
            is_required = default == str(inspect.Parameter.empty)
            if not is_required:
                placeholder = f"default: {default}"

            editor = QLineEdit()
            editor.setPlaceholderText(placeholder)
            editor.textChanged.connect(self._validate_fields)

            if is_required:
                self.required_fields.append(editor)

            picker_button = QPushButton()
            picker_button.setIcon(get_status_icon("crosshair"))
            picker_button.setFixedSize(24, 24)
            picker_button.setToolTip("Select a live object as argument")
            picker_button.clicked.connect(
                lambda checked=False, e=editor: self.open_object_picker(e)
            )

            editor_layout = QHBoxLayout()
            editor_layout.setContentsMargins(0, 0, 0, 0)
            editor_layout.addWidget(editor)
            editor_layout.addWidget(picker_button)

            form_layout.addRow(QLabel(f"{name}:"), editor_layout)
            self.arg_widgets[name] = (editor, kind)

        if not self.arg_widgets and not self.is_constructor:
            no_args_label = QLabel("This function takes no user-provided arguments.")
            main_layout.addWidget(no_args_label)

        if self.is_constructor:
            self.variable_name_edit = QLineEdit()
            self.variable_name_edit.setPlaceholderText("(optional) e.g., 'new_player'")
            form_layout.addRow(QLabel("Assign to variable:"), self.variable_name_edit)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

        self._validate_fields()

    @Slot()
    def _validate_fields(self):
        all_required_filled = all(
            field.text().strip() for field in self.required_fields
        )
        self.ok_button.setEnabled(all_required_filled)

    @Slot(QLineEdit)
    def open_object_picker(self, target_editor):
        dialog = ObjectPickerDialog(self.all_objects, self)
        dialog.object_selected.connect(
            lambda name, path: self.on_object_picked(target_editor, name, path)
        )
        dialog.exec()

    def on_object_picked(self, target_editor, name, path):
        target_editor.setText(name)
        target_editor.setProperty("pyforge_path", path)

    def on_accept(self):
        args = []
        kwargs = {}
        variable_name = (
            self.variable_name_edit.text().strip() if self.is_constructor else ""
        )

        try:
            for name, (editor, kind) in self.arg_widgets.items():
                text = editor.text().strip()
                pyforge_path = editor.property("pyforge_path")

                if not text:
                    continue

                value_to_send = pyforge_path if pyforge_path else text

                if kind == "VAR_POSITIONAL":
                    arg_list = text.split(",")
                    args.extend([a.strip() for a in arg_list])
                elif kind == "VAR_KEYWORD":
                    kwarg_dict = eval(f"dict({text})")
                    kwargs.update({k: str(v) for k, v in kwarg_dict.items()})
                else:
                    kwargs[name] = value_to_send

            self.run_requested.emit(args, kwargs, variable_name)
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Input Error",
                f"Could not parse arguments. Please check your Python syntax.\n\nError: {e}",
            )
