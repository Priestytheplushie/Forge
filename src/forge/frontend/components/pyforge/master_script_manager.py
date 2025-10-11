from PySide6.QtWidgets import QTreeView, QWidget, QVBoxLayout, QMenu, QMessageBox
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Signal, Qt, QPoint, QModelIndex, Slot

from ...assets.icon_map import (
    get_pyforge_object_icon,
    get_pyforge_script_icon,
    get_status_icon,
)


class MasterScriptManager(QWidget):
    """A tree view for visually managing the master.pfscript file."""

    add_hook_requested = Signal()
    add_override_requested = Signal()
    add_snippet_requested = Signal()
    attach_new_script_requested = Signal(str)
    attach_existing_script_requested = Signal(str)
    remove_script_requested = Signal(str, str)
    inline_script_requested = Signal(str, str)
    edit_in_text_requested = Signal(int)
    run_script_now_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)

        main_layout.addWidget(self.tree_view)

        self.global_root = self._create_root_item(
            "Global Scope", "folder", "Code that runs once on script load."
        )
        self.hooks_root = self._create_root_item(
            "Hooks", "folder", "Functions that run on specific agent events."
        )
        self.overrides_root = self._create_root_item(
            "Overrides",
            "alert-triangle",
            "Warning: Overrides can alter core agent behavior.",
        )
        self.overrides_root.setForeground(Qt.GlobalColor.yellow)

        self.model.appendRow(self.global_root)
        self.model.appendRow(self.hooks_root)
        self.model.appendRow(self.overrides_root)

        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        self.tree_view.doubleClicked.connect(self.on_double_clicked)

    def _create_root_item(self, text, icon_name, tooltip):
        item = QStandardItem(get_status_icon(icon_name), text)
        item.setEditable(False)
        item.setToolTip(tooltip)
        item.setData(
            {"type": "root", "name": text.lower().replace(" ", "_")},
            Qt.ItemDataRole.UserRole,
        )
        return item

    def update_from_ast(self, ast_data: dict):
        """Populates the tree using data parsed from the master script's AST."""
        self.hooks_root.removeRows(0, self.hooks_root.rowCount())
        self.global_root.removeRows(0, self.global_root.rowCount())
        self.overrides_root.removeRows(0, self.overrides_root.rowCount())

        for hook in ast_data.get("hooks", []):
            hook_item = QStandardItem(get_pyforge_object_icon("hook"), hook["name"])
            hook_item.setEditable(False)
            hook_item.setToolTip(
                f"Hook: {hook['name']}\nRuns on a specific agent event.\nDouble-click to edit."
            )
            hook_item.setData(
                {"type": "hook", "name": hook["name"], "lineno": hook["lineno"]},
                Qt.ItemDataRole.UserRole,
            )
            self.hooks_root.appendRow(hook_item)
            for script in hook.get("scripts", []):
                script_item = QStandardItem(get_pyforge_script_icon(), script["path"])
                script_item.setEditable(False)
                script_item.setToolTip(
                    f"Event Script\nPath: {script['full_path']}\nDouble-click to edit."
                )
                script_item.setData(
                    {
                        "type": "script",
                        "path": script["full_path"],
                        "hook": hook["name"],
                        "lineno": script["lineno"],
                    },
                    Qt.ItemDataRole.UserRole,
                )
                hook_item.appendRow(script_item)

        for override in ast_data.get("overrides", []):
            override_item = QStandardItem(
                get_status_icon("alert-triangle", "#EBCB8B"), override["target"]
            )
            override_item.setEditable(False)
            override_item.setToolTip(
                f"Override: {override['target']}\nFunction: {override['func_name']}\nDouble-click to edit."
            )
            override_item.setData(
                {
                    "type": "override",
                    "name": override["target"],
                    "lineno": override["lineno"],
                },
                Qt.ItemDataRole.UserRole,
            )
            self.overrides_root.appendRow(override_item)

        for snippet in ast_data.get("global_scope", []):
            snippet_item = QStandardItem(get_status_icon("code"), snippet["summary"])
            snippet_item.setEditable(False)
            snippet_item.setToolTip(
                f"Global Code Snippet\n'{snippet['summary']}'\nDouble-click to edit."
            )
            snippet_item.setData(
                {
                    "type": "snippet",
                    "summary": snippet["summary"],
                    "lineno": snippet["lineno"],
                },
                Qt.ItemDataRole.UserRole,
            )
            self.global_root.appendRow(snippet_item)

        self.tree_view.expandAll()

    @Slot(QPoint)
    def on_context_menu(self, point: QPoint):
        index = self.tree_view.indexAt(point)
        item = self.model.itemFromIndex(index) or self.model.invisibleRootItem()

        root_item = item
        while root_item and root_item.parent():
            root_item = root_item.parent()

        item_data = item.data(Qt.ItemDataRole.UserRole) or {}
        item_type = item_data.get("type")

        menu = QMenu(self)

        if root_item is self.global_root:
            menu.addAction("Add Code Snippet...").triggered.connect(
                self.add_snippet_requested
            )

        elif root_item is self.hooks_root:
            if item_type == "root" or (item and item.parent() is None):
                menu.addAction("Add Hook Definition...").triggered.connect(
                    self.add_hook_requested
                )
            elif item_type == "hook":
                hook_name = item_data["name"]
                menu.addAction("Attach New Event Script...").triggered.connect(
                    lambda: self.attach_new_script_requested.emit(hook_name)
                )
                menu.addAction("Attach Existing Event Script...").triggered.connect(
                    lambda: self.attach_existing_script_requested.emit(hook_name)
                )
            elif item_type == "script":
                menu.addAction("Remove Event Script").triggered.connect(
                    lambda: self.remove_script_requested.emit(
                        item_data["hook"], item_data["path"]
                    )
                )
                menu.addAction("Inline Script").triggered.connect(
                    lambda: self.inline_script_requested.emit(
                        item_data["hook"], item_data["path"]
                    )
                )

        elif root_item is self.overrides_root:
            menu.addAction("Add Override from Template...").triggered.connect(
                self.add_override_requested
            )

        if not menu.actions():
            action = menu.addAction("(No actions available)")
            action.setEnabled(False)

        menu.exec(self.tree_view.viewport().mapToGlobal(point))

    @Slot(QModelIndex)
    def on_double_clicked(self, index: QModelIndex):
        item = self.model.itemFromIndex(index)
        if not item:
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data and isinstance(item_data, dict) and "lineno" in item_data:
            self.edit_in_text_requested.emit(item_data["lineno"])
