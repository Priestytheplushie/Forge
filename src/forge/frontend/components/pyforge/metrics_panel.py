from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QMenu,
    QLabel,
    QFormLayout,
    QPushButton,
    QFrame,
    QHBoxLayout,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon
from PySide6.QtCore import Signal, Slot, QPoint, QTime, QElapsedTimer, Qt
from pathlib import Path

from ...assets.icon_map import get_stop_icon, get_status_icon
from ..diagrams.graph_widget import GraphWidget


class MetricsPanel(QWidget):
    stop_requested = Signal()
    create_event_script_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("PyForgePanelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.addWidget(QLabel("Live Metrics"))

        main_layout.addWidget(header)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.graph_container = QWidget()
        self.graph_layout = QHBoxLayout(self.graph_container)
        self.graph_layout.setContentsMargins(0, 0, 0, 0)
        self.cpu_graph = GraphWidget("CPU", "%", 100.0)
        self.mem_graph = GraphWidget("Memory", "MB", 512.0)
        self.graph_layout.addWidget(self.cpu_graph)
        self.graph_layout.addWidget(self.mem_graph)

        tree_label = QLabel("All Metrics")
        tree_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.metrics_tree = QTreeView()
        self.metrics_tree.setHeaderHidden(True)
        self.metrics_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.metrics_tree.setModel(self.model)

        self.system_root = QStandardItem("System Metrics")
        self.system_root.setEditable(False)
        self.model.appendRow(self.system_root)

        self.custom_root = QStandardItem("Custom Metrics")
        self.custom_root.setEditable(False)
        self.model.appendRow(self.custom_root)

        self.metrics_items = {}

        content_layout.addWidget(self.graph_container)
        content_layout.addWidget(tree_label)
        content_layout.addWidget(self.metrics_tree)
        main_layout.addWidget(content_widget)

        self.metrics_tree.customContextMenuRequested.connect(self.on_context_menu)

        self._init_tree()

    def _init_tree(self):
        self.metrics_items["system/cpu"] = self._add_metric_item(
            self.system_root, "CPU Usage", "0.0 %"
        )
        self.metrics_items["system/memory"] = self._add_metric_item(
            self.system_root, "Memory Usage", "0.0 MB"
        )

        gc_root = QStandardItem("Garbage Collector")
        gc_root.setEditable(False)
        self.system_root.appendRow(gc_root)
        self.metrics_items["system/gc/counts0"] = self._add_metric_item(
            gc_root, "Gen 0 Collections", "0"
        )
        self.metrics_items["system/gc/counts1"] = self._add_metric_item(
            gc_root, "Gen 1 Collections", "0"
        )
        self.metrics_items["system/gc/counts2"] = self._add_metric_item(
            gc_root, "Gen 2 Collections", "0"
        )
        self.metrics_items["system/gc/objects"] = self._add_metric_item(
            gc_root, "Live Objects", "0"
        )
        self.metrics_items["system/gc/garbage"] = self._add_metric_item(
            gc_root, "Unreachable", "0"
        )

        self.metrics_tree.expandAll()
        self.metrics_tree.setColumnWidth(0, 150)

    def _add_metric_item(self, parent, name, value):
        name_item = QStandardItem(name)
        value_item = QStandardItem(str(value))
        name_item.setEditable(False)
        value_item.setEditable(False)
        parent.appendRow([name_item, value_item])
        return value_item

    @Slot(list)
    def update_definitions(self, definitions: list):
        self.custom_root.removeRows(0, self.custom_root.rowCount())
        for key in list(self.metrics_items.keys()):
            if key.startswith("custom/"):
                del self.metrics_items[key]

        for definition in definitions:
            metric_name = definition.get("name")
            if metric_name:
                metric_key = f"custom/{metric_name}"
                self.metrics_items[metric_key] = self._add_metric_item(
                    self.custom_root, metric_name, "N/A"
                )

        self.metrics_tree.expand(self.custom_root.index())

    @Slot(dict)
    def update_metrics(self, data: dict):

        cpu = data.get("cpu_usage", 0)
        mem = data.get("memory_rss_mb", 0)
        self.cpu_graph.add_data_point(cpu)
        self.mem_graph.add_data_point(mem)

        if self.metrics_items.get("system/cpu"):
            self.metrics_items["system/cpu"].setText(f"{cpu:.1f} %")
        if self.metrics_items.get("system/memory"):
            self.metrics_items["system/memory"].setText(f"{mem:.2f} MB")

        if "gc_stats" in data and data["gc_stats"]:
            gc = data["gc_stats"]
            if self.metrics_items.get("system/gc/counts0"):
                self.metrics_items["system/gc/counts0"].setText(str(gc["counts"][0]))
            if self.metrics_items.get("system/gc/counts1"):
                self.metrics_items["system/gc/counts1"].setText(str(gc["counts"][1]))
            if self.metrics_items.get("system/gc/counts2"):
                self.metrics_items["system/gc/counts2"].setText(str(gc["counts"][2]))
            if self.metrics_items.get("system/gc/objects"):
                self.metrics_items["system/gc/objects"].setText(str(gc["objects"]))
            if self.metrics_items.get("system/gc/garbage"):
                self.metrics_items["system/gc/garbage"].setText(str(gc["garbage"]))

        custom_metrics = data.get("custom_metrics", {})
        for name, value in custom_metrics.items():
            key = f"custom/{name}"
            if key in self.metrics_items:
                if isinstance(value, float):
                    value_str = f"{value:.4f}"
                else:
                    value_str = str(value)
                self.metrics_items[key].setText(value_str)

    def on_context_menu(self, point: QPoint):
        index = self.metrics_tree.indexAt(point)
        if not index.isValid() or not index.parent().isValid():
            return

        name_item = index.model().itemFromIndex(index.siblingAtColumn(0))
        if not name_item:
            return

        metric_name = name_item.text()
        metric_path = ""
        for path, item in self.metrics_items.items():
            if item.text() == index.siblingAtColumn(1).data(
                Qt.ItemDataRole.DisplayRole
            ):
                metric_path = path
                break

        if not metric_path:
            return

        menu = QMenu(self)
        action = menu.addAction("Create Event Script for Changes...")
        action.triggered.connect(
            lambda: self.create_event_script_requested.emit(metric_path)
        )
        menu.exec(self.metrics_tree.viewport().mapToGlobal(point))
