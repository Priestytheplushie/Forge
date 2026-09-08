from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QColor, QPalette, QPainter
from PySide6.QtCore import Qt, QRect
from .object_tree_model import ObjectTreeItem
from ...assets.icon_map import get_status_icon


class ObjectTreeDelegate(QStyledItemDelegate):
    """A custom delegate to control the appearance and editing of the object tree."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pin_icon = get_status_icon("pin", "#DDB451")
        self.eye_icon = get_status_icon("eye", "#88C0D0")

    def createEditor(self, parent, option, index):
        """Creates an editor only for items that are designated as attributes."""

        proxy_model = index.model()
        source_index = proxy_model.mapToSource(index)
        source_model = proxy_model.sourceModel()
        item = source_model.itemFromIndex(source_index)

        if isinstance(item, ObjectTreeItem) and item.node_type == "attribute_simple":
            return super().createEditor(parent, option, index)
        return None

    def setEditorData(self, editor, index):
        """Populates the editor with the attribute's current value."""

        proxy_model = index.model()
        source_index = proxy_model.mapToSource(index)
        source_model = proxy_model.sourceModel()
        item = source_model.itemFromIndex(source_index)

        if isinstance(item, ObjectTreeItem) and "value" in item.full_data:
            value_str = item.full_data["value"]

            if value_str.startswith("'") and value_str.endswith("'"):
                editor.setText(value_str[1:-1])
            elif value_str.startswith('"') and value_str.endswith('"'):
                editor.setText(value_str[1:-1])
            else:
                editor.setText(value_str)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Commits the new data from the editor back to the model."""

        super().setModelData(editor, model, index)

    def paint(self, painter, option, index):

        super().paint(painter, option, index)

        proxy_model = index.model()
        source_index = proxy_model.mapToSource(index)
        source_model = proxy_model.sourceModel()
        item = source_model.itemFromIndex(source_index)

        if not isinstance(item, ObjectTreeItem) or item.node_type != "instance":
            return

        parent = self.parent()
        tree_view_widget = None
        if parent is not None and hasattr(parent, "tree_view"):
            tree_view_widget = parent.tree_view
        else:
            tree_view_widget = parent

        is_expanded = False
        try:
            if tree_view_widget is not None and hasattr(tree_view_widget, "isExpanded"):
                is_expanded = tree_view_widget.isExpanded(index)
        except Exception:

            is_expanded = False

        icon_to_draw = None
        if item.is_pinned:
            icon_to_draw = self.pin_icon
        elif is_expanded:
            icon_to_draw = self.eye_icon

        if icon_to_draw:

            icon_size = 12
            icon_rect = QRect(
                option.rect.right() - icon_size - 4,
                option.rect.top() + (option.rect.height() - icon_size) // 2,
                icon_size,
                icon_size,
            )
            icon_to_draw.paint(painter, icon_rect)
