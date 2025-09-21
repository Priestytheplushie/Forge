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
    QSizePolicy,
    QHBoxLayout,
    QMenu,
    QComboBox,
)
from PySide6.QtCore import Qt, QFileInfo, Slot, Signal
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent, QActionGroup
import os

from ..components.panels.file_explorer import FileExplorer
from ..components.panels.source_control_panel import SourceControlPanel
from ..components.panels.problems_panel import ProblemsPanel
from ..components.panels.outline_panel import OutlinePanel
from ..components.panels.timeline_panel import TimelinePanel
from ..components.panels.conflicts_panel import ConflictsPanel
from ..components.editor.editor_widget import EditorWidget
from ..components.editor.diff_editor_widget import DiffEditorWidget
from ..components.terminal.terminal_widget import TerminalWidget
from ..components.welcome.welcome_widget import WelcomeWidget
from ..assets.icon_map import (
    get_run_icon,
    get_stop_icon,
    get_status_icon,
    get_arrow_up_icon,
    get_arrow_down_icon,
)
from ..theme_manager import ThemeManager
from ..controllers.main_controller import MainController, ClickableStatusBarWidget
from ..controllers.file_manager import FileManager
from ..controllers.workspace_manager import WorkspaceManager
from ..controllers.run_manager import RunManager
from ..controllers.lsp_client import LSPClient


class WelcomeFileExplorer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(10, 20, 10, 10)
        self.open_folder_button = QPushButton("Open Folder")
        self.clone_repo_button = QPushButton("Clone Repository")
        layout.addWidget(QLabel("You have not yet opened a folder."))
        layout.addSpacing(10)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.clone_repo_button)


class MainWindow(QMainWindow):
    def __init__(self, app_root: str):
        super().__init__()
        self.app_root = app_root
        self.setWindowTitle("Forge")
        self.setGeometry(100, 100, 1500, 900)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._initial_layout_applied = False
        self.icon_provider = QFileIconProvider()

        self.theme_manager = ThemeManager(self)

        self._create_central_widget()
        self._create_docks()
        self._create_menu_bar()
        self._create_status_bar()

        self.log_to_output("Run", "", clear=True)
        self.log_to_output("Git", "", clear=True)
        self.output_channel_combo.setCurrentIndex(0)

        self.file_manager = FileManager(self, self.theme_manager)

        self.workspace_manager = WorkspaceManager(self, self.app_root)
        self.run_manager = RunManager(self, self.file_manager)
        self.lsp_client = LSPClient(self, self.file_manager)

        self.controller = MainController(
            self,
            self.theme_manager,
            self.file_manager,
            self.workspace_manager,
            self.run_manager,
            self.lsp_client,
        )

        self.file_explorer_dock.raise_()
        self.terminal_dock.raise_()
        self._preload_web_engine()

    def closeEvent(self, event: QCloseEvent):
        print("[MainWindow] Close event triggered. Shutting down subsystems.")
        self.controller.shutdown()
        self.terminal.shutdown()
        event.accept()

    def _create_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

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

        self.status_bar.addWidget(self.git_branch_widget)
        self.status_bar.addWidget(self.commit_info_widget)

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
        print("Pre-loading Web Engine...")
        self._preloaded_editor = EditorWidget(
            self.theme_manager.get_current_theme_data(), self
        )
        self._preloaded_editor.setVisible(False)
        print("Web Engine pre-loading initiated.")

    def _create_central_widget(self):
        self.welcome_screen = WelcomeWidget(self)
        self.tab_widget = self._create_tab_widget()
        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(self.welcome_screen)
        self.central_stack.addWidget(self.tab_widget)
        self.setCentralWidget(self.central_stack)
        self.central_stack.setCurrentWidget(self.welcome_screen)

    def _create_tab_widget(self):
        tab_widget = QTabWidget()
        tab_widget.setTabsClosable(True)
        tab_widget.setMovable(True)
        self.tab_bar_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(self.tab_bar_toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(5)

        self.prev_item_button = QToolButton()
        self.prev_item_button.setIcon(get_arrow_up_icon())
        self.prev_item_button.setVisible(False)
        toolbar_layout.addWidget(self.prev_item_button)

        self.next_item_button = QToolButton()
        self.next_item_button.setIcon(get_arrow_down_icon())
        self.next_item_button.setVisible(False)
        toolbar_layout.addWidget(self.next_item_button)

        self.run_button = QToolButton()
        self.run_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.run_button.setToolTip("Run File")
        toolbar_layout.addWidget(self.run_button)
        tab_widget.setCornerWidget(self.tab_bar_toolbar, Qt.Corner.TopRightCorner)
        return tab_widget

    def add_editor_tab(self, file_path, widget):
        self.show_editor_view()

        is_diff = isinstance(widget, DiffEditorWidget)
        is_merge_editor = bool(widget.property("is_merge_editor"))
        is_readonly_history = getattr(widget, "metadata", {}).get(
            "is_history_view", False
        )

        if is_merge_editor:
            tab_title = f"Resolving: {os.path.basename(file_path)}"
        elif is_diff or is_readonly_history:
            tab_title = file_path
        else:
            tab_title = os.path.basename(file_path)

        widget.setProperty("file_path", file_path)

        icon_path = file_path
        if is_readonly_history:
            icon_path = widget.metadata.get("original_path", file_path)

        file_info = QFileInfo(icon_path)
        icon = self.icon_provider.icon(file_info)

        index = self.tab_widget.addTab(widget, icon, tab_title)
        self.tab_widget.setCurrentIndex(index)
        self.status_bar.showMessage(f"Opened {file_path}", 5000)
        self.controller._update_ui_for_editor(widget)

    def get_current_editor(self):
        if self.central_stack.currentWidget() is self.tab_widget:
            return self.tab_widget.currentWidget()
        return None

    def _create_docks(self):
        self.file_explorer = FileExplorer(self)
        self.welcome_file_explorer = WelcomeFileExplorer(self)
        self.file_explorer_stack = QStackedWidget()
        self.file_explorer_stack.addWidget(self.welcome_file_explorer)
        self.file_explorer_stack.addWidget(self.file_explorer)
        self.file_explorer_dock = QDockWidget("File Explorer", self)
        self.file_explorer_dock.setWidget(self.file_explorer_stack)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self.file_explorer_dock
        )

        self.source_control_panel = SourceControlPanel(self.icon_provider, self)
        self.source_control_dock = QDockWidget("Source Control", self)
        self.source_control_dock.setWidget(self.source_control_panel)

        sc_title_bar = QWidget()
        sc_title_layout = QHBoxLayout(sc_title_bar)
        sc_title_layout.setContentsMargins(5, 0, 5, 0)
        sc_title_layout.addWidget(QLabel("Source Control"))
        sc_title_layout.addStretch()

        self.git_pull_button = QToolButton()
        self.git_pull_button.setIcon(get_status_icon("arrow-down-circle"))
        self.git_pull_button.setToolTip("Pull")
        sc_title_layout.addWidget(self.git_pull_button)

        self.git_push_button = QToolButton()
        self.git_push_button.setIcon(get_status_icon("arrow-up-circle"))
        self.git_push_button.setToolTip("Push")
        sc_title_layout.addWidget(self.git_push_button)

        self.git_refresh_button = QToolButton()
        self.git_refresh_button.setIcon(get_status_icon("refresh-cw"))
        self.git_refresh_button.setToolTip("Fetch and Refresh Status")
        sc_title_layout.addWidget(self.git_refresh_button)

        self.source_control_dock.setTitleBarWidget(sc_title_bar)
        self.tabifyDockWidget(self.file_explorer_dock, self.source_control_dock)

        self.conflicts_panel = ConflictsPanel(self.icon_provider, self)
        self.conflicts_dock = QDockWidget("Conflicts", self)
        self.conflicts_dock.setWidget(self.conflicts_panel)
        self.conflicts_dock.setVisible(False)
        self.tabifyDockWidget(self.file_explorer_dock, self.conflicts_dock)

        self.outline_panel = OutlinePanel(self)
        self.outline_dock = QDockWidget("Outline", self)
        self.outline_dock.setWidget(self.outline_panel)
        self.tabifyDockWidget(self.file_explorer_dock, self.outline_dock)

        self.timeline_panel = TimelinePanel(self)
        self.timeline_dock = QDockWidget("Timeline", self)
        self.timeline_dock.setWidget(self.timeline_panel)
        self.tabifyDockWidget(self.file_explorer_dock, self.timeline_dock)

        self.terminal = TerminalWidget(self)
        self.terminal_dock = QDockWidget("Terminal", self)
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
        self.tabifyDockWidget(self.terminal_dock, self.output_dock)

        self.problems_panel = ProblemsPanel(self.icon_provider, self)
        self.problems_dock = QDockWidget("Problems", self)
        self.problems_dock.setWidget(self.problems_panel)
        self.tabifyDockWidget(self.terminal_dock, self.problems_dock)

        self.debug_console_widget = QTextEdit()
        self.debug_console_widget.setReadOnly(True)
        self.debug_console_dock = QDockWidget("Debug Console", self)
        self.debug_console_dock.setWidget(self.debug_console_widget)
        self.tabifyDockWidget(self.terminal_dock, self.debug_console_dock)

    def _create_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        self._create_file_menu(menu_bar)
        self._create_edit_menu(menu_bar)
        self._create_view_menu(menu_bar)
        self._create_go_menu(menu_bar)
        self.run_menu = menu_bar.addMenu("&Run")
        self._create_help_menu(menu_bar)

    def _create_file_menu(self, menu_bar):
        self.file_menu = menu_bar.addMenu("&File")
        self.file_menu.addAction(QAction("New File", self))
        self.file_menu.addAction(QAction("Open &Folder...", self, shortcut="Ctrl+K"))
        self.file_menu.addAction(QAction("&Open...", self, shortcut=QKeySequence.Open))
        self.file_menu.addAction(QAction("&Save", self, shortcut=QKeySequence.Save))
        self.file_menu.addAction(
            QAction("Save &As...", self, shortcut=QKeySequence.SaveAs)
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction(
            QAction("E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close)
        )

    def _create_edit_menu(self, menu_bar):
        self.edit_menu = menu_bar.addMenu("&Edit")
        self.edit_menu.addAction(QAction("&Undo", self, shortcut=QKeySequence.Undo))
        self.edit_menu.addAction(QAction("&Redo", self, shortcut=QKeySequence.Redo))
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(QAction("Cu&t", self, shortcut=QKeySequence.Cut))
        self.edit_menu.addAction(QAction("&Copy", self, shortcut=QKeySequence.Copy))
        self.edit_menu.addAction(QAction("&Paste", self, shortcut=QKeySequence.Paste))

    def _create_view_menu(self, menu_bar):
        self.view_menu = menu_bar.addMenu("&View")
        appearance_menu = QMenu("Appearance", self)
        self.view_menu.addMenu(appearance_menu)
        theme_menu = QMenu("Theme", self)
        appearance_menu.addMenu(theme_menu)
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for theme_name in self.theme_manager.get_theme_names():
            action = QAction(theme_name, self, checkable=True)
            if theme_name == self.theme_manager.current_theme_name:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked, name=theme_name: self.theme_manager.set_theme(name)
            )
            theme_group.addAction(action)
            theme_menu.addAction(action)
        appearance_menu.addSeparator()
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.file_explorer_dock.toggleViewAction())
        self.view_menu.addAction(self.source_control_dock.toggleViewAction())
        self.view_menu.addAction(self.conflicts_dock.toggleViewAction())
        self.view_menu.addAction(self.outline_dock.toggleViewAction())
        self.view_menu.addAction(self.timeline_dock.toggleViewAction())
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.terminal_dock.toggleViewAction())
        self.view_menu.addAction(self.output_dock.toggleViewAction())
        self.view_menu.addAction(self.problems_dock.toggleViewAction())
        self.view_menu.addAction(self.debug_console_dock.toggleViewAction())

    def _create_go_menu(self, menu_bar):
        self.go_menu = menu_bar.addMenu("&Go")

    def _create_help_menu(self, menu_bar):
        self.help_menu = menu_bar.addMenu("&Help")
        self.help_menu.addAction(QAction("&About Forge", self))

    def show_editor_view(self):
        if self.central_stack.currentWidget() is not self.tab_widget:
            self.central_stack.setCurrentWidget(self.tab_widget)

    def apply_workspace_layout(self):
        window_height = self.height()
        terminal_height = int(window_height * 0.3)
        self.resizeDocks(
            [self.terminal_dock], [terminal_height], Qt.Orientation.Vertical
        )

    def log_to_output(self, channel_name: str, message: str, clear: bool = False):
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
