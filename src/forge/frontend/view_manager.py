from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QLabel


class ViewManager(QObject):
    """Manages the visibility of dock widgets based on the selected activity."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.current_view = ""

        self.view_map = {
            "Explorer": [
                main_window.file_explorer_dock,
                main_window.outline_dock,
                main_window.timeline_dock,
            ],
            "Source Control": [main_window.source_control_dock],
            "Search": [main_window.search_placeholder_dock],
            "Debug": [main_window.debug_placeholder_dock],
            "Review": [main_window.review_dock],
            "AI": [main_window.ai_placeholder_dock],
            "Account": [main_window.account_placeholder_dock],
            "Settings": [main_window.settings_placeholder_dock],
        }

        self.all_docks = [dock for docks in self.view_map.values() for dock in docks]

    @Slot(str)
    def set_view(self, view_name: str):
        if view_name not in self.view_map:
            return

        is_same_view = self.current_view == view_name
        docks_for_view = self.view_map.get(view_name, [])

        if is_same_view:
            are_any_visible = (
                any(d.isVisible() for d in docks_for_view) if docks_for_view else False
            )
            if are_any_visible:

                for dock in docks_for_view:
                    dock.hide()
                self.current_view = ""
            else:

                for dock in docks_for_view:
                    dock.show()
                if docks_for_view:
                    docks_for_view[0].raise_()
                self.current_view = view_name
            return

        self.current_view = view_name
        for dock in self.all_docks:
            dock.setVisible(dock in docks_for_view)

        if docks_for_view:
            docks_for_view[0].raise_()

    def set_modal_view(self, view_name: str, is_modal: bool):
        for action in self.main_window.activity_bar.action_group.actions():
            if action.data() != view_name:
                action.setEnabled(not is_modal)

        if is_modal:
            self.set_view(view_name)
