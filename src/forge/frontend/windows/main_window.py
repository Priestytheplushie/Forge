from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QMenuBar,
    QDockWidget,
    QTextEdit,
    QTabWidget,
    QFileIconProvider,
    QStackedWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
    QToolButton,
    QHBoxLayout,
    QMenu,
    QComboBox,
    QTabBar,
    QSizePolicy,
    QSystemTrayIcon,
)
from PySide6.QtCore import Qt, QFileInfo, Slot, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent, QActionGroup, QColor
import os
from pathlib import Path

from ..components.panels.file_explorer import FileExplorer
from ..components.panels.source_control_panel import SourceControlPanel
from ..components.panels.problems_panel import ProblemsPanel
from ..components.panels.outline_panel import OutlinePanel
from ..components.panels.timeline_panel import TimelinePanel
from ..components.panels.review_panel import ReviewPanel
from ..components.editor.editor_widget import EditorWidget
from ..components.editor.diff_editor_widget import DiffEditorWidget
from ..components.terminal.terminal_widget import TerminalWidget
from ..components.welcome.welcome_widget import WelcomeWidget
from ..components.toolbars.review_toolbar import ReviewToolbar
from ..components.activity_bar import ActivityBar
from ..components.pyforge.console import PyForgeConsole
from ..components.pyforge.active_panel import PyForgeActivePanel
from ...backend.pyforge.manager import PyForgeManager
from ..controllers.pyforge_controller import PyForgeController
from ..assets.icon_map import (
    get_stop_icon,
    get_status_icon,
    get_arrow_up_icon,
    get_arrow_down_icon,
    get_pyforge_icon,
    get_pyforge_script_icon,
    get_colorized_icon,
)
from ..theme_manager import ThemeManager
from ..controllers.main_controller import MainController
from ..controllers.file_manager import FileManager
from ..controllers.workspace_manager import WorkspaceManager
from ..controllers.run_manager import RunManager
from ..controllers.lsp_client import LSPClient
from ..view_manager import ViewManager
from .about_dialog import AboutDialog
from .new_project_dialog import NewProjectDialog
from ..views.search_view import SearchView
from ..views.debug_view import DebugView
from ..views.review_view import ReviewView
from ..views.generic_view import GenericView


class ClickableStatusBarWidget(QWidget):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class WelcomeFileExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(10, 20, 10, 10)
        self.open_folder_button = QPushButton("Open Folder")
        self.clone_repo_button = QPushButton("Clone Repository")
        self.new_project_button = QPushButton("New Project...")
        layout.addWidget(QLabel("You have not yet opened a folder."))
        layout.addSpacing(10)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.clone_repo_button)
        layout.addWidget(self.new_project_button)


class MainWindow(QMainWindow):
    def __init__(self, app_root: str):
        super().__init__()
        self.app_root = app_root
        self.setWindowTitle("Forge")
        self.setGeometry(100, 100, 1500, 900)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._initial_layout_applied = False
        self.icon_provider = QFileIconProvider()

        self.tray_icon = QSystemTrayIcon(get_pyforge_script_icon(), self)
        self.tray_icon.setToolTip("Forge IDE")
        self.tray_icon.show()

        self.activity_bar = ActivityBar(self)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.activity_bar)

        self.theme_manager = ThemeManager(self)
        self.workspace_manager = WorkspaceManager(self, self.app_root)

        self._create_central_widget(self.workspace_manager.recent_projects)
        self._create_docks()
        self._create_menu_bar()
        self._create_status_bar()

        self.view_manager = ViewManager(self)
        self.activity_bar.view_selected.connect(self.view_manager.set_view)

        self.file_manager = FileManager(self, self.theme_manager)
        self.run_manager = RunManager(self, self.file_manager)
        self.lsp_client = LSPClient(self, self.file_manager)

        self.pyforge_manager = PyForgeManager(self.app_root, self)
        self.pyforge_controller = PyForgeController(self, self.pyforge_manager)

        self.pyforge_active_panel.set_controller(self.pyforge_controller)

        self.controller = MainController(
            self,
            self.theme_manager,
            self.file_manager,
            self.workspace_manager,
            self.run_manager,
            self.lsp_client,
            self.pyforge_controller,
        )

        self.log_to_output("Run", "", clear=True)
        self.log_to_output("Git", "", clear=True)
        self.log_to_output("PyForge", "", clear=True)
        self.output_channel_combo.setCurrentIndex(0)

        self.workspace_manager.workspace_will_change.connect(
            self.controller.git_controller.exit_merge_mode
        )

        self.view_manager.set_view("Explorer")
        self._preload_web_engine()

        self.theme_manager.set_theme(self.theme_manager.current_theme_name)

        self.set_bottom_panel_enabled(False)

    def closeEvent(self, event: QCloseEvent):
        self.controller.shutdown()
        self.terminal.shutdown_all()
        event.accept()

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.git_branch_widget = ClickableStatusBarWidget()
        self.git_branch_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self.git_branch_widget.setToolTip(
            "Current branch. Click to view all branches or create a new one."
        )
        git_layout = QHBoxLayout(self.git_branch_widget)
        git_layout.setContentsMargins(5, 0, 5, 0)
        git_layout.setSpacing(3)
        self.git_status_icon_label = QLabel()
        self.git_status_icon_label.setPixmap(
            get_status_icon("git-branch").pixmap(16, 16)
        )
        self.git_branch_label = QLabel("main")
        git_layout.addWidget(self.git_status_icon_label)
        git_layout.addWidget(self.git_branch_label)
        self.git_remote_status_label = QLabel()
        self.git_remote_status_label.setToolTip("Commits ahead/behind remote branch")
        git_layout.addWidget(self.git_remote_status_label)

        self.commit_info_widget = QWidget()
        commit_layout = QHBoxLayout(self.commit_info_widget)
        commit_layout.setContentsMargins(5, 0, 5, 0)
        commit_layout.setSpacing(3)
        self.commit_icon_label = QLabel()
        self.commit_icon_label.setPixmap(get_status_icon("git-commit").pixmap(16, 16))
        self.commit_info_label = QLabel()
        self.commit_info_label.setToolTip("Latest commit details")
        commit_layout.addWidget(self.commit_icon_label)
        commit_layout.addWidget(self.commit_info_label)

        self.pyforge_status_label = QLabel("PyForge: Idle")
        self.pyforge_status_label.setPixmap(get_pyforge_icon().pixmap(16, 16))

        left_layout.addWidget(self.git_branch_widget)
        left_layout.addWidget(self.commit_info_widget)
        left_layout.addWidget(self.pyforge_status_label)

        self.status_bar.addWidget(left_widget)
        self.git_branch_widget.setVisible(False)
        self.commit_info_widget.setVisible(False)

        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 5, 0)
        right_layout.setSpacing(10)
        self.autosave_status_label = QLabel("Autosave Enabled")
        right_layout.addWidget(self.autosave_status_label)
        self.cursor_pos_label = QLabel("Ln 1, Col 1")
        right_layout.addWidget(self.cursor_pos_label)

        problems_widget = QWidget()
        problems_layout = QHBoxLayout(problems_widget)
        problems_layout.setContentsMargins(0, 0, 0, 0)
        problems_layout.setSpacing(3)
        self.error_icon_label = QLabel()
        self.error_icon_label.setPixmap(
            get_status_icon("x-circle", "#F77669").pixmap(14, 14)
        )
        self.error_label = QLabel("0")
        self.warning_icon_label = QLabel()
        self.warning_icon_label.setPixmap(
            get_status_icon("alert-triangle", "#DDB451").pixmap(14, 14)
        )
        self.warning_label = QLabel("0")
        self.hint_icon_label = QLabel()
        self.hint_icon_label.setPixmap(
            get_status_icon("info", "#4E94D7").pixmap(14, 14)
        )
        self.hint_label = QLabel("0")
        problems_layout.addWidget(self.error_icon_label)
        problems_layout.addWidget(self.error_label)
        problems_layout.addSpacing(5)
        problems_layout.addWidget(self.warning_icon_label)
        problems_layout.addWidget(self.warning_label)
        problems_layout.addSpacing(5)
        problems_layout.addWidget(self.hint_icon_label)
        problems_layout.addWidget(self.hint_label)
        right_layout.addWidget(problems_widget)

        self.lsp_status_label = QLabel("LSP: Idle")
        self.lsp_status_label.setPixmap(get_status_icon("cpu").pixmap(16, 16))
        right_layout.addWidget(self.lsp_status_label)
        self.ai_status_label = QLabel("AI: Disabled")
        self.ai_status_label.setPixmap(get_status_icon("pen-tool").pixmap(16, 16))
        right_layout.addWidget(self.ai_status_label)

        self.status_bar.addPermanentWidget(right_widget)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_layout_applied:
            self.apply_workspace_layout()
            self._initial_layout_applied = True

    def _preload_web_engine(self):
        self._preloaded_editor = EditorWidget(
            self.theme_manager.get_current_theme_data(), self
        )
        self._preloaded_editor.setParent(self)
        self._preloaded_editor.setVisible(False)

    def _create_central_widget(self, recent_projects: list):
        self.welcome_screen = WelcomeWidget(recent_projects, self)
        self.tab_widget = self._create_tab_widget()
        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(self.welcome_screen)
        self.central_stack.addWidget(self.tab_widget)
        self.central_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setCentralWidget(self.central_stack)

    def _create_tab_widget(self):
        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        self.corner_stack = QStackedWidget()

        self.normal_corner_widget = QWidget()
        normal_layout = QHBoxLayout(self.normal_corner_widget)
        normal_layout.setContentsMargins(5, 0, 5, 0)
        normal_layout.setSpacing(5)
        self.prev_item_button = QToolButton()
        self.prev_item_button.setIcon(get_arrow_up_icon())
        self.prev_item_button.setVisible(False)
        self.next_item_button = QToolButton()
        self.next_item_button.setIcon(get_arrow_down_icon())
        self.next_item_button.setVisible(False)
        self.run_button = QToolButton()
        self.run_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.run_button.setToolTip("Run File")
        normal_layout.addWidget(self.prev_item_button)
        normal_layout.addWidget(self.next_item_button)
        normal_layout.addStretch()
        normal_layout.addWidget(self.run_button)

        self.review_toolbar = ReviewToolbar()

        self.live_edit_widget = QWidget()
        live_edit_layout = QHBoxLayout(self.live_edit_widget)
        live_edit_layout.setContentsMargins(5, 0, 5, 0)
        self.hot_reload_button = QToolButton()
        self.hot_reload_button.setText("Hot Reload")
        self.hot_reload_button.setIcon(get_colorized_icon("zap.svg", QColor("#B69CFD")))
        self.hot_reload_button.setToolTip("Apply changes to the running application.")
        live_edit_layout.addStretch()
        live_edit_layout.addWidget(self.hot_reload_button)

        self.master_script_widget = QWidget()
        master_script_layout = QHBoxLayout(self.master_script_widget)
        master_script_layout.setContentsMargins(5, 0, 5, 0)
        self.validate_reload_button = QToolButton()
        self.validate_reload_button.setText("Validate")
        self.validate_reload_button.setIcon(
            get_colorized_icon("zap.svg", QColor("#DDB451"))
        )
        self.validate_reload_button.setToolTip(
            "Validate and/or Hot Reload the Master Script."
        )
        master_script_layout.addStretch()
        master_script_layout.addWidget(self.validate_reload_button)

        self.corner_stack.addWidget(self.normal_corner_widget)
        self.corner_stack.addWidget(self.review_toolbar)
        self.corner_stack.addWidget(self.live_edit_widget)
        self.corner_stack.addWidget(self.master_script_widget)

        tab_widget.setCornerWidget(self.corner_stack, Qt.Corner.TopRightCorner)
        return tab_widget

    def add_editor_tab(self, file_path, widget):
        self.show_editor_view()
        is_diff = isinstance(widget, DiffEditorWidget)
        is_merge_editor = bool(widget.property("is_merge_editor"))
        is_readonly_history = getattr(widget, "metadata", {}).get(
            "is_history_view", False
        )
        is_review_diff = getattr(widget, "is_review_diff", False)
        is_live_edit = getattr(widget, "is_live_edit", False)

        if is_live_edit:
            tab_title = f"[LIVE] {os.path.basename(file_path)}"
        elif is_review_diff:
            tab_title = f"Review: {os.path.basename(file_path)}"
        elif is_merge_editor:
            tab_title = f"Resolving: {os.path.basename(file_path)}"
        elif is_diff or is_readonly_history:
            tab_title = file_path
        else:
            tab_title = os.path.basename(file_path)

        widget.setProperty("file_path", file_path)
        icon_path = (
            widget.metadata.get("original_path", file_path)
            if is_readonly_history
            else file_path
        )

        if file_path and file_path.endswith(".pfscript"):
            icon = get_pyforge_script_icon()
        else:
            file_info = QFileInfo(icon_path)
            icon = self.icon_provider.icon(file_info)

        if is_live_edit:
            icon = get_colorized_icon("zap.svg", QColor("#B69CFD"))

        index = self.tab_widget.addTab(widget, icon, tab_title)
        self.tab_widget.setCurrentIndex(index)
        self.controller._update_ui_for_editor(widget)

    def get_current_editor(self):
        if self.central_stack.currentWidget() is self.tab_widget:
            return self.tab_widget.currentWidget()
        return None

    def _create_docks(self):

        self.file_explorer_dock = QDockWidget("File Explorer", self)
        self.file_explorer = FileExplorer(self)
        self.welcome_file_explorer = WelcomeFileExplorer(self)
        self.file_explorer_stack = QStackedWidget()
        self.file_explorer_stack.addWidget(self.welcome_file_explorer)
        self.file_explorer_stack.addWidget(self.file_explorer)
        self.file_explorer_dock.setWidget(self.file_explorer_stack)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.file_explorer_dock
        )

        self.source_control_dock = QDockWidget("Source Control", self)
        sc_title_bar = QWidget()
        sc_title_layout = QHBoxLayout(sc_title_bar)
        sc_title_layout.setContentsMargins(5, 0, 5, 0)
        sc_title_layout.addWidget(QLabel("Source Control"))
        sc_title_layout.addStretch()
        self.git_pull_button = QToolButton()
        self.git_pull_button.setIcon(get_status_icon("arrow-down-circle"))
        self.git_pull_button.setToolTip("Pull")
        self.git_push_button = QToolButton()
        self.git_push_button.setIcon(get_status_icon("arrow-up-circle"))
        self.git_push_button.setToolTip("Push")
        self.git_refresh_button = QToolButton()
        self.git_refresh_button.setIcon(get_status_icon("refresh-cw"))
        self.git_refresh_button.setToolTip("Fetch and Refresh Status")
        sc_title_layout.addWidget(self.git_pull_button)
        sc_title_layout.addWidget(self.git_push_button)
        sc_title_layout.addWidget(self.git_refresh_button)
        self.source_control_dock.setTitleBarWidget(sc_title_bar)
        self.source_control_panel = SourceControlPanel(
            self.icon_provider, self.source_control_dock
        )
        self.source_control_dock.setWidget(self.source_control_panel)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.source_control_dock
        )

        self.outline_dock = QDockWidget("Outline", self)
        self.outline_panel = OutlinePanel(self)
        self.outline_dock.setWidget(self.outline_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.outline_dock)
        self.timeline_dock = QDockWidget("Timeline", self)
        self.timeline_panel = TimelinePanel(self)
        self.timeline_dock.setWidget(self.timeline_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.timeline_dock)
        self.review_dock = QDockWidget("Review", self)
        self.review_view = ReviewView(self)
        self.review_panel = ReviewPanel(self.icon_provider, self)
        self.review_stack = QStackedWidget()
        self.review_stack.addWidget(self.review_view)
        self.review_stack.addWidget(self.review_panel)
        self.review_dock.setWidget(self.review_stack)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.review_dock)

        self.search_dock = QDockWidget("Search", self)
        self.search_dock.setWidget(SearchView(self))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.search_dock)

        self.debug_dock = QDockWidget("Debug", self)
        self.debug_stack = QStackedWidget()
        self.debug_view = DebugView(self)
        self.pyforge_active_panel = PyForgeActivePanel(self)
        self.debug_stack.addWidget(self.debug_view)
        self.debug_stack.addWidget(self.pyforge_active_panel)
        self.debug_dock.setWidget(self.debug_stack)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.debug_dock)

        self.ai_dock = QDockWidget("AI", self)
        self.ai_dock.setWidget(GenericView("AI", self))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.ai_dock)
        self.account_dock = QDockWidget("Account", self)
        self.account_dock.setWidget(GenericView("Account", self))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.account_dock)
        self.settings_dock = QDockWidget("Settings", self)
        self.settings_dock.setWidget(GenericView("Settings", self))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.settings_dock)

        self.tabifyDockWidget(self.file_explorer_dock, self.source_control_dock)
        self.tabifyDockWidget(self.source_control_dock, self.outline_dock)
        self.tabifyDockWidget(self.outline_dock, self.timeline_dock)
        self.tabifyDockWidget(self.timeline_dock, self.review_dock)
        self.tabifyDockWidget(self.review_dock, self.search_dock)
        self.tabifyDockWidget(self.search_dock, self.debug_dock)
        self.tabifyDockWidget(self.debug_dock, self.ai_dock)
        self.tabifyDockWidget(self.ai_dock, self.account_dock)
        self.tabifyDockWidget(self.account_dock, self.settings_dock)

        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal = TerminalWidget(self)
        self.terminal_dock.setWidget(self.terminal)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.output_dock = QDockWidget("Output", self)
        self.output_channels = {}
        self.output_stack = QStackedWidget()
        output_panel_widget = QWidget()
        output_panel_layout = QVBoxLayout(output_panel_widget)
        output_panel_layout.setContentsMargins(0, 0, 0, 0)
        output_panel_layout.setSpacing(0)
        output_header = QWidget()
        output_header_layout = QHBoxLayout(output_header)
        output_header_layout.setContentsMargins(5, 2, 5, 2)
        self.output_channel_combo = QComboBox()
        self.output_channel_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_channel_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        output_header_layout.addWidget(self.output_channel_combo)
        output_header_layout.addStretch()
        self.stop_action = QAction(get_stop_icon(), "Stop Process", self)
        self.stop_action.setEnabled(False)
        stop_button = QToolButton()
        stop_button.setDefaultAction(self.stop_action)
        output_header_layout.addWidget(stop_button)
        self.clear_output_button = QToolButton()
        self.clear_output_button.setIcon(get_status_icon("x-circle"))
        self.clear_output_button.setToolTip("Clear Output")
        output_header_layout.addWidget(self.clear_output_button)
        output_panel_layout.addWidget(output_header)
        output_panel_layout.addWidget(self.output_stack)
        self.output_dock.setWidget(output_panel_widget)
        self.output_channel_combo.currentIndexChanged.connect(
            self.output_stack.setCurrentIndex
        )
        self.clear_output_button.clicked.connect(self.on_clear_output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)
        self.problems_dock = QDockWidget("Problems", self)
        self.problems_panel = ProblemsPanel(self.icon_provider, self)
        self.problems_dock.setWidget(self.problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_dock)
        self.debug_console_dock = QDockWidget("Debug Console", self)
        self.debug_console_widget = QTextEdit()
        self.debug_console_widget.setReadOnly(True)
        self.debug_console_dock.setWidget(self.debug_console_widget)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.debug_console_dock
        )
        self.pyforge_console_dock = QDockWidget("PyForge Console", self)
        self.pyforge_console = PyForgeConsole(self)
        self.pyforge_console_dock.setWidget(self.pyforge_console)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.pyforge_console_dock
        )

        self.tabifyDockWidget(self.terminal_dock, self.output_dock)
        self.tabifyDockWidget(self.output_dock, self.problems_dock)
        self.tabifyDockWidget(self.problems_dock, self.debug_console_dock)
        self.tabifyDockWidget(self.debug_console_dock, self.pyforge_console_dock)
        self.terminal_dock.raise_()

    def _create_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        self._create_file_menu(menu_bar)
        self._create_edit_menu(menu_bar)
        self.refactor_menu = menu_bar.addMenu("&Refactor")
        self._create_view_menu(menu_bar)
        self._create_go_menu(menu_bar)
        self.run_menu = menu_bar.addMenu("&Run")
        self._create_terminal_menu(menu_bar)
        self._create_help_menu(menu_bar)

    def _create_file_menu(self, menu_bar):
        self.file_menu = menu_bar.addMenu("&File")
        self.new_project_action = QAction("New Project...", self)
        self.new_file_action = QAction("New File", self)
        self.open_folder_action = QAction("Open &Folder...", self, shortcut="Ctrl+K")
        self.open_file_action = QAction("&Open...", self, shortcut=QKeySequence.Open)
        self.save_action = QAction("&Save", self, shortcut=QKeySequence.Save)
        self.save_as_action = QAction("Save &As...", self, shortcut=QKeySequence.SaveAs)
        self.exit_action = QAction("E&xit", self, shortcut=QKeySequence.Quit)

        self.file_menu.addAction(self.new_project_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.new_file_action)
        self.file_menu.addAction(self.open_folder_action)
        self.file_menu.addAction(self.open_file_action)
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction(self.save_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

    def _create_edit_menu(self, menu_bar):
        self.edit_menu = menu_bar.addMenu("&Edit")
        self.edit_menu.addAction(QAction("&Undo", self, shortcut=QKeySequence.Undo))
        self.edit_menu.addAction(QAction("&Redo", self, shortcut=QKeySequence.Redo))
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(QAction("Cu&t", self, shortcut=QKeySequence.Cut))
        self.edit_menu.addAction(QAction("&Copy", self, shortcut=QKeySequence.Copy))
        self.edit_menu.addAction(QAction("&Paste", self, shortcut=QKeySequence.Paste))

    def _create_view_menu(self, menu_bar):
        view_menu = menu_bar.addMenu("&View")
        appearance_menu = QMenu("Appearance", self)
        view_menu.addMenu(appearance_menu)
        theme_menu = QMenu("Theme", self)
        appearance_menu.addMenu(theme_menu)
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for theme_name in self.theme_manager.get_theme_names():
            action = QAction(theme_name, self, checkable=True)
            if theme_name == self.theme_manager.current_theme_name:
                action.setChecked(True)
            theme_group.addAction(action)
            theme_menu.addAction(action)
        appearance_menu.addSeparator()
        view_menu.addSeparator()
        view_menu.addAction(self.file_explorer_dock.toggleViewAction())
        view_menu.addAction(self.source_control_dock.toggleViewAction())
        self.review_action = self.review_dock.toggleViewAction()
        self.review_action.setText("Review")
        self.review_action.setEnabled(False)
        view_menu.addAction(self.review_action)
        view_menu.addAction(self.outline_dock.toggleViewAction())
        view_menu.addAction(self.timeline_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction(self.terminal_dock.toggleViewAction())
        view_menu.addAction(self.output_dock.toggleViewAction())
        view_menu.addAction(self.problems_dock.toggleViewAction())
        view_menu.addAction(self.debug_console_dock.toggleViewAction())
        view_menu.addAction(self.pyforge_console_dock.toggleViewAction())

    def _create_go_menu(self, menu_bar):
        self.go_menu = menu_bar.addMenu("&Go")

    def _create_terminal_menu(self, menu_bar):
        terminal_menu = menu_bar.addMenu("&Terminal")
        self.new_terminal_action = QAction(
            "New Terminal", self, shortcut="Ctrl+Shift+`"
        )
        terminal_menu.addAction(self.new_terminal_action)

    def _create_help_menu(self, menu_bar):
        help_menu = menu_bar.addMenu("&Help")
        self.about_action = QAction("&About Forge", self)
        help_menu.addAction(self.about_action)

    @Slot()
    def on_about(self):
        dialog = AboutDialog(Path(self.app_root), self)
        dialog.exec()

    @Slot()
    def on_new_project(self):
        dialog = NewProjectDialog(self.controller, self)
        if dialog.exec():
            self.workspace_manager.set_workspace(dialog.project_path)

    @Slot(str)
    def on_view_selected(self, view_name: str):
        self.view_manager.set_view(view_name)
        self.terminal.force_resize_current_terminal()

    def show_editor_view(self):
        if self.central_stack.currentWidget() is not self.tab_widget:
            self.central_stack.setCurrentWidget(self.tab_widget)

    def apply_workspace_layout(self):
        window_height = self.height()
        terminal_height = int(window_height * 0.3)
        self.resizeDocks(
            [self.terminal_dock], [terminal_height], Qt.Orientation.Vertical
        )

    @Slot()
    def on_initial_resize(self):
        self.terminal.force_resize_current_terminal()

    def log_to_output(
        self,
        channel_name: str,
        message: str,
        clear: bool = False,
        raise_panel: bool = False,
    ):
        if channel_name not in self.output_channels:
            new_output = QTextEdit()
            new_output.setReadOnly(True)
            new_output.setFontFamily("Consolas")
            index = self.output_stack.addWidget(new_output)
            self.output_channels[channel_name] = new_output
            self.output_channel_combo.addItem(channel_name)
            self.output_channel_combo.setItemData(
                self.output_channel_combo.count() - 1, index
            )
        text_edit = self.output_channels[channel_name]
        if clear:
            text_edit.clear()
        text_edit.append(message)
        combo_index = self.output_channel_combo.findText(channel_name)
        if combo_index != -1:
            self.output_channel_combo.setCurrentIndex(combo_index)
        if raise_panel:
            self.output_dock.setVisible(True)
            self.output_dock.raise_()

    @Slot()
    def on_clear_output(self):
        current_widget = self.output_stack.currentWidget()
        if isinstance(current_widget, QTextEdit):
            current_widget.clear()

    @Slot(str)
    def add_debug_log(self, message: str):
        self.debug_console_widget.append(message)

    def enter_merge_mode(self):
        self.view_manager.set_view("Source Control")
        self.activity_bar.set_modal("Source Control", True)
        self.terminal.force_resize_current_terminal()

    def exit_merge_mode(self):
        self.activity_bar.set_modal("Source Control", False)
        if self.view_manager.current_view == "Source Control":
            self.view_manager.set_view("Explorer")
        self.terminal.force_resize_current_terminal()

    def enter_review_mode(self):
        self.review_stack.setCurrentIndex(1)
        self.view_manager.set_view("Review")
        self.activity_bar.set_modal("Review", True)
        self.terminal.force_resize_current_terminal()

    def exit_review_mode(self):
        self.review_stack.setCurrentIndex(0)
        self.activity_bar.set_modal("Review", False)
        if self.view_manager.current_view == "Review":
            self.view_manager.set_view("Explorer")
        self.terminal.force_resize_current_terminal()

    def set_bottom_panel_enabled(self, enabled: bool):
        for tab_bar in self.findChildren(QTabBar):
            has_terminal = False
            for i in range(tab_bar.count()):
                if tab_bar.tabText(i) == "Terminal":
                    has_terminal = True
                    break
            if has_terminal:
                for i in range(tab_bar.count()):
                    if tab_bar.tabText(i) != "Terminal":
                        tab_bar.setTabEnabled(i, enabled)
                break
