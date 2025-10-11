from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QStackedWidget,
    QToolButton,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Slot, Qt

from .terminal_instance import TerminalInstance
from ...assets.icon_map import get_plus_icon, get_split_icon, get_trash_icon


class TerminalWidget(QWidget):
    """
    A widget that manages multiple, tabbed terminal instances with a VS Code-style UI.
    """

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.workspace_path = None
        self.terminals = []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.terminal_stack = QStackedWidget()

        side_panel_widget = QWidget()
        side_panel_widget.setFixedWidth(180)
        side_panel_widget.setStyleSheet("background-color: #252526;")
        side_panel_layout = QVBoxLayout(side_panel_widget)
        side_panel_layout.setContentsMargins(0, 5, 0, 5)

        button_toolbar = QWidget()
        button_layout = QHBoxLayout(button_toolbar)
        button_layout.setContentsMargins(10, 0, 10, 0)

        add_button = QToolButton()
        add_button.setIcon(get_plus_icon())
        add_button.setToolTip("New Terminal")
        split_button = QToolButton()
        split_button.setIcon(get_split_icon())
        split_button.setToolTip("Split Terminal (coming soon)")
        split_button.setEnabled(False)
        kill_button = QToolButton()
        kill_button.setIcon(get_trash_icon())
        kill_button.setToolTip("Kill Terminal")

        button_layout.addStretch()
        button_layout.addWidget(add_button)
        button_layout.addWidget(split_button)
        button_layout.addWidget(kill_button)

        self.terminal_list = QListWidget()
        self.terminal_list.setStyleSheet("QListWidget { border: none; }")

        side_panel_layout.addWidget(self.terminal_list)
        side_panel_layout.addWidget(button_toolbar)

        main_layout.addWidget(self.terminal_stack)
        main_layout.addWidget(side_panel_widget)

        add_button.clicked.connect(self.create_new_terminal)
        kill_button.clicked.connect(self.kill_current_terminal)
        self.terminal_list.currentItemChanged.connect(
            self.on_terminal_selection_changed
        )

    def start_session(self, workspace_path: str):
        self.workspace_path = workspace_path
        self.shutdown_all()
        self.create_new_terminal()

    @Slot(str)
    def create_new_terminal(self, name: str = "shell") -> TerminalInstance | None:
        if not self.workspace_path:
            return None

        if self.main_window.terminal_dock.isHidden():
            self.main_window.terminal_dock.show()

        instance = TerminalInstance(self)
        instance.start_session(self.workspace_path)

        self.terminals.append(instance)
        self.terminal_stack.addWidget(instance)

        list_item = QListWidgetItem(name)
        list_item.setData(Qt.ItemDataRole.UserRole, instance)
        self.terminal_list.addItem(list_item)
        self.terminal_list.setCurrentItem(list_item)

        instance.name_changed.connect(
            lambda new_name, inst=instance: self.on_terminal_name_changed(
                inst, new_name
            )
        )

        if name != "shell":
            self.on_terminal_name_changed(instance, name)

        return instance

    def force_resize_current_terminal(self):
        current_instance = self.terminal_stack.currentWidget()
        if isinstance(current_instance, TerminalInstance):
            current_instance.force_resize()

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_terminal_selection_changed(self, current, previous):
        if current:
            instance = current.data(Qt.ItemDataRole.UserRole)
            self.terminal_stack.setCurrentWidget(instance)

    def kill_terminal_instance(self, instance_to_kill: TerminalInstance):
        for i in range(self.terminal_list.count()):
            item = self.terminal_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == instance_to_kill:
                self._kill_item(item)
                break

    def _kill_item(self, item_to_kill: QListWidgetItem):
        if not item_to_kill:
            return

        row = self.terminal_list.row(item_to_kill)
        instance = item_to_kill.data(Qt.ItemDataRole.UserRole)

        self.terminal_list.takeItem(row)
        self.terminal_stack.removeWidget(instance)

        self.terminals.remove(instance)

        if instance is self.main_window.pyforge_manager.active_terminal_instance:
            self.main_window.pyforge_manager.on_session_ended()

        instance.shutdown()
        instance.deleteLater()

        if self.terminal_list.count() == 0:
            self.main_window.terminal_dock.hide()

    @Slot()
    def kill_current_terminal(self):
        self._kill_item(self.terminal_list.currentItem())

    @Slot(TerminalInstance, str)
    def on_terminal_name_changed(self, instance, name: str):
        for i in range(self.terminal_list.count()):
            item = self.terminal_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == instance:
                item.setText(name)
                break

    def shutdown_all(self):
        for instance in list(self.terminals):
            instance.shutdown()

        while self.terminal_list.count() > 0:
            self.terminal_list.takeItem(0)
        while self.terminal_stack.count() > 0:
            widget = self.terminal_stack.widget(0)
            self.terminal_stack.removeWidget(widget)
            widget.deleteLater()

        self.terminals.clear()

    def shutdown(self):
        self.shutdown_all()
