from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFileIconProvider,
)
from PySide6.QtCore import Slot, Signal, QFileInfo
from ...assets.icon_map import get_unresolved_icon


class ConflictsPanel(QWidget):
    """A panel dedicated to showing files with merge conflicts."""

    file_selected = Signal(str)

    def __init__(self, icon_provider: QFileIconProvider, parent=None):
        super().__init__(parent)
        self.icon_provider = icon_provider
        self.unresolved_icon = get_unresolved_icon()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.conflicts_list = QListWidget()
        self.conflicts_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.conflicts_list)

    @Slot(list)
    def update_conflicts(self, conflicted_files: list):
        """Populates the list with conflicted files."""
        self.conflicts_list.clear()
        for file_path in sorted(conflicted_files):
            item = QListWidgetItem(self.unresolved_icon, file_path)
            self.conflicts_list.addItem(item)

    @Slot(QListWidgetItem)
    def on_item_double_clicked(self, item: QListWidgetItem):
        file_path = item.text()
        self.file_selected.emit(file_path)
