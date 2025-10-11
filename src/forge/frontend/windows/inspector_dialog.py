from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTreeView,
    QDialogButtonBox,
    QApplication,
    QMenu,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction
from PySide6.QtCore import Qt, QPoint


class InspectorDialog(QDialog):
    """A dialog to display a deep, read-only inspection of a live object."""

    def __init__(self, inspection_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Object Inspector")
        self.setMinimumSize(600, 500)

        main_layout = QVBoxLayout(self)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)

        if "error" in inspection_data:
            self.model.appendRow(QStandardItem(f"Error: {inspection_data['error']}"))
        else:
            self._populate_tree(self.model.invisibleRootItem(), inspection_data)
            self.tree_view.expandToDepth(1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)

        main_layout.addWidget(self.tree_view)
        main_layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        self.tree_view.customContextMenuRequested.connect(self.on_context_menu)
        self.tree_view.doubleClicked.connect(
            lambda index: self.tree_view.isExpanded(index)
            or self.tree_view.expand(index)
        )

    def _populate_tree(self, parent_item: QStandardItem, data: dict):
        for child_data in data.get("children", []):
            name = child_data.get("name", "")
            value = child_data.get("value")

            display_text = name
            if value is not None:
                display_text = f"{name}: {value}"

            item = QStandardItem(display_text)
            item.setToolTip(display_text)
            item.setData(value, Qt.ItemDataRole.UserRole)
            parent_item.appendRow(item)

            if child_data.get("expandable", False) and "children" in child_data:
                self._populate_tree(item, child_data)

    def on_context_menu(self, point: QPoint):
        index = self.tree_view.indexAt(point)
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        value = item.data(Qt.ItemDataRole.UserRole)
        full_text = item.text()

        menu = QMenu(self)
        if value is not None:
            menu.addAction("Copy Value").triggered.connect(
                lambda: QApplication.clipboard().setText(str(value))
            )

        menu.addAction("Copy Row").triggered.connect(
            lambda: QApplication.clipboard().setText(full_text)
        )
        menu.exec(self.tree_view.viewport().mapToGlobal(point))
