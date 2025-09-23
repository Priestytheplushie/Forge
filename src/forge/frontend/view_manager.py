from PySide6.QtCore import QObject, Slot


class ViewManager(QObject):
    """Manages the visibility of dock widgets based on application views."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.views = {}
        self.all_docks = []
        self._register_views()

    def _register_views(self):
        mw = self.main_window

        self.views = {
            "Explorer": [mw.file_explorer_dock, mw.outline_dock, mw.timeline_dock],
            "Source Control": [
                mw.source_control_dock,
            ],
            "Search": [],
            "Debug": [mw.debug_console_dock],
            "Review": [mw.review_dock],
            "AI": [],
            "Account": [],
            "Settings": [],
        }

        self.all_docks = [
            mw.file_explorer_dock,
            mw.outline_dock,
            mw.timeline_dock,
            mw.source_control_dock,
            mw.debug_console_dock,
            mw.review_dock,
        ]

    @Slot(str)
    def set_view(self, view_name: str):
        """Shows docks for the selected view and hides all others."""
        if view_name not in self.views:
            return

        visible_docks = self.views[view_name]

        for dock in self.all_docks:
            dock.setVisible(dock in visible_docks)

        if visible_docks:
            primary_dock = visible_docks[0]
            primary_dock.raise_()
