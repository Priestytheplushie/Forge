from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    QModelIndex,
    QSortFilterProxyModel,
    QRegularExpression,
    QMimeData,
)
from ...assets.icon_map import get_pyforge_object_icon, get_status_icon
import re


class ObjectTreeItem(QStandardItem):
    def __init__(self, text, icon=None):
        if icon:
            super().__init__(icon, text)
        else:
            super().__init__(text)
        self.is_fetching = False
        self.node_type = None
        self.node_path = None
        self.full_data = {}
        self.is_pinned = False


class ObjectTreeModel(QSortFilterProxyModel):
    attribute_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSourceModel(QStandardItemModel(self))
        self.item_map = {}
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(0)
        self.setRecursiveFilteringEnabled(True)

    def setFilterWildcard(self, wildcard: str):
        self.setFilterRegularExpression(
            QRegularExpression(
                wildcard, QRegularExpression.PatternOption.CaseInsensitiveOption
            )
        )

    def get_path_for_item(self, item: QStandardItem) -> str:
        return getattr(item, "node_path", None)

    def flags(self, index):
        flags = super().flags(index)
        source_index = self.mapToSource(index)
        item = self.sourceModel().itemFromIndex(source_index)
        if isinstance(item, ObjectTreeItem) and item.node_type == "attribute_simple":
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role):
        if role == Qt.ItemDataRole.EditRole:
            source_index = self.mapToSource(index)
            item = self.sourceModel().itemFromIndex(source_index)
            if (
                isinstance(item, ObjectTreeItem)
                and item.node_type == "attribute_simple"
            ):
                self.attribute_changed.emit(item.node_path, value, item)
                return True
        return super().setData(index, value, role)

    def mimeData(self, indexes):
        if not indexes:
            return None

        index = indexes[0]
        source_index = self.mapToSource(index)
        item = self.sourceModel().itemFromIndex(source_index)

        if not isinstance(item, ObjectTreeItem) or not item.node_path:
            return None

        mime_data = QMimeData()
        node_path = item.node_path
        path_type, _, path_data = node_path.partition(":")

        snippet = ""
        if path_type == "instance":
            snippet = f'pf.get("{path_data}")'
        elif path_type == "attribute":
            obj_id_str, _, attr_name = path_data.partition(".")
            snippet = f'pf.get("{obj_id_str}").{attr_name}'
        else:
            item_name = item.full_data.get("name", "").partition("(")[0].strip()
            if item_name:
                snippet = f'pf.get("{item_name}")'

        if snippet:
            mime_data.setText(snippet)

        mime_data.setData(
            "application/x-pyforge-object-reference", node_path.encode("utf-8")
        )
        return mime_data

    def update_item_value(self, item: ObjectTreeItem, new_value_repr: str):
        if not new_value_repr:
            return
        item.full_data["value"] = new_value_repr
        display_text = f"{item.full_data['name']}: {new_value_repr}"
        item.setText(display_text)
        item.setToolTip(
            f"type: {item.full_data.get('type')}\npath: {item.node_path}\n\n{new_value_repr}"
        )

    def remove_item(self, item: ObjectTreeItem):
        if item.parent():
            self.item_map.pop(item.node_path, None)
            item.parent().removeRow(item.row())

    def clear(self):
        self.sourceModel().clear()
        self.item_map.clear()

    def _update_item_data(self, item, node_data):
        """Helper to update an existing item's data and appearance."""
        icon = get_pyforge_object_icon(
            node_data["type"], node_data.get("file_path", "")
        )
        display_text = node_data["name"]
        if "value" in node_data:
            display_text = f"{node_data['name']}: {node_data['value']}"

        item.setText(display_text)
        item.setIcon(icon)

        item.node_type = node_data["type"]
        item.node_path = node_data["path"]
        item.full_data = node_data

        tooltip = f"type: {node_data['type']}\npath: {node_data['path']}"
        if "value" in node_data:
            tooltip += f"\n\n{node_data['value']}"
        if "doc" in node_data and node_data["doc"]:
            tooltip += f"\n\n{node_data.get('doc', '')}"
        item.setToolTip(tooltip)

        if item.node_path:
            self.item_map[item.node_path] = item

    def update_toplevel(self, data: list):
        self.clear()
        parent = self.sourceModel().invisibleRootItem()
        for node in data:
            self._add_child_node(parent, node)

    def update_children(self, parent_item: ObjectTreeItem, children_data: list):
        parent_item.is_fetching = False
        parent_item.removeRows(0, parent_item.rowCount())

        if children_data:
            for node in children_data:
                self._add_child_node(parent_item, node)
        elif parent_item.full_data.get("expandable", False):
            empty_child = ObjectTreeItem("(empty)")
            empty_child.setEnabled(False)
            parent_item.appendRow(empty_child)

    def _add_child_node(self, parent_item, node_data):
        item = ObjectTreeItem("")
        self._update_item_data(item, node_data)
        item.setEditable(False)

        if node_data.get("expandable", False):
            if "children" in node_data:
                for child_node in node_data["children"]:
                    self._add_child_node(item, child_node)
            else:
                dummy_child = ObjectTreeItem("Loading...")
                dummy_child.setEnabled(False)
                item.appendRow(dummy_child)
                item.is_fetching = True

        parent_item.appendRow(item)
        return item

    def handle_subscription_update(self, update_data: dict):
        update_type = update_data.get("type")
        path = update_data.get("path")

        if update_type == "update":
            item_to_update = self.item_map.get(path)
            if item_to_update:
                self.update_item_value(item_to_update, update_data.get("new_value", ""))

        elif update_type == "delete":
            item_to_delete = self.item_map.get(path)
            if item_to_delete:
                self.remove_item(item_to_delete)

    def handle_new_instance(self, new_instance_data: dict):
        class_path = new_instance_data.get("class_path")
        instance_data = new_instance_data.get("instance")
        if not class_path or not instance_data:
            return

        parent_path = f"instance_group_for_class:{class_path}"
        parent_item = self.item_map.get(parent_path)

        if parent_item:
            if parent_item.is_fetching:
                return

            if parent_item.rowCount() > 0 and parent_item.child(0).text() == "(empty)":
                parent_item.removeRow(0)

            new_node_data = {
                "name": f"{instance_data['type']} @ {hex(instance_data['id'])}",
                "type": "instance",
                "path": f"instance:{instance_data['id']}",
                "expandable": True,
            }
            self._add_child_node(parent_item, new_node_data)

        instance_group_path = f"instance_group:{class_path}"
        instance_group_item = self.item_map.get(instance_group_path)
        if instance_group_item:
            current_text = instance_group_item.text()
            match = re.match(r"(.*) \((\d+)\)", current_text)
            if match:
                name, count = match.groups()
                instance_group_item.setText(f"{name} ({int(count) + 1})")

    def find_item_by_path(self, path):
        item = self.item_map.get(path)
        if item:
            try:
                source_index = self.sourceModel().indexFromItem(item)
                return self.mapFromSource(source_index)
            except RuntimeError:
                return QModelIndex()
        return QModelIndex()
