from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, Signal, Slot

from ...assets.icon_map import (
    get_icon_for_symbol,
    get_tooltip_for_symbol,
    get_status_icon,
)


class OutlinePanel(QWidget):
    """
    A widget that displays a hierarchical view of the symbols in the current document.
    """

    symbol_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)

        self.layout().addWidget(self.tree_view)

        self.conflict_icon = get_status_icon("alert-triangle", "#DDB451")
        self.tree_view.doubleClicked.connect(self.on_symbol_double_clicked)

    def _populate_tree_recursively(self, parent_item, symbols):
        """
        A recursive function to walk the symbol hierarchy and build the tree.
        """
        for symbol in symbols:
            kind = symbol["kind"]

            symbol_range = None
            if "range" in symbol:
                symbol_range = symbol["range"]
            elif "location" in symbol and "range" in symbol["location"]:
                symbol_range = symbol["location"]["range"]
            if not symbol_range:
                continue

            icon = get_icon_for_symbol(kind)

            tree_item = QStandardItem(icon, symbol["name"])
            tree_item.setEditable(False)
            tree_item.setToolTip(get_tooltip_for_symbol(kind))

            start_pos = symbol_range["start"]
            tree_item.setData(
                (start_pos["line"], start_pos["character"]), Qt.ItemDataRole.UserRole
            )

            parent_item.appendRow(tree_item)

            if "children" in symbol and symbol["children"]:
                self._populate_tree_recursively(tree_item, symbol["children"])

    @Slot(list)
    def update_symbols(self, symbols: list):
        self.model.clear()
        if symbols:
            try:
                self._populate_tree_recursively(self.model.invisibleRootItem(), symbols)
                self.tree_view.expandAll()
            except Exception as e:
                print(f"[OutlinePanel] CRITICAL: Failed to parse symbol data: {e}")
                self.model.clear()

    @Slot(list)
    def update_from_hunks(self, hunks: list[dict]):
        self.model.clear()
        if hunks:
            root = self.model.invisibleRootItem()
            for i, hunk in enumerate(hunks):
                item = QStandardItem(self.conflict_icon, f"{hunk['name']} #{i + 1}")
                item.setEditable(False)
                item.setToolTip("Click to jump to conflict")
                item.setData((hunk["line"] - 1, hunk["char"]), Qt.ItemDataRole.UserRole)
                root.appendRow(item)
            self.tree_view.expandAll()
        else:
            self.clear_symbols()

    @Slot()
    def clear_symbols(self):
        self.model.clear()

    @Slot()
    def on_symbol_double_clicked(self, index):
        item = self.model.itemFromIndex(index)
        if not item:
            return
        location_data = item.data(Qt.ItemDataRole.UserRole)
        if location_data:
            line, char = location_data
            self.symbol_clicked.emit(line, char)
