import sys
from PySide6.QtWidgets import QMessageBox, QMenu
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction

from forge.backend.runner import ProcessRunner
from forge.frontend.assets.icon_map import get_run_icon, get_run_output_icon


class RunManager(QObject):
    """Manages the 'Run' actions and process execution."""

    def __init__(self, main_window, file_manager):
        super().__init__(main_window)
        self.main_window = main_window
        self.file_manager = file_manager
        self.process_runner = None
        self.workspace_path = None

        self.run_in_terminal_action = None
        self.run_in_output_action = None

        self._setup_run_actions()
        self._connect_signals()

    def set_workspace_path(self, path: str):
        self.workspace_path = path

    def _setup_run_actions(self):
        run_icon = get_run_icon()

        self.run_in_terminal_action = QAction(
            run_icon, "Run Python File in Terminal", self.main_window
        )
        self.run_in_terminal_action.triggered.connect(
            lambda: self.run_current_file(mode="terminal")
        )

        self.run_in_output_action = QAction(
            get_run_output_icon(), "Run Python File in Output", self.main_window
        )
        self.run_in_output_action.triggered.connect(
            lambda: self.run_current_file(mode="output")
        )

        self.main_window.run_button.setDefaultAction(self.run_in_terminal_action)

        menu = QMenu(self.main_window)
        menu.addAction(self.run_in_terminal_action)
        menu.addAction(self.run_in_output_action)
        self.main_window.run_button.setMenu(menu)

        self.main_window.run_menu.addAction(self.run_in_terminal_action)
        self.main_window.run_menu.addAction(self.run_in_output_action)

        self.run_in_terminal_action.setEnabled(False)
        self.run_in_output_action.setEnabled(False)

    def _connect_signals(self):
        self.main_window.stop_action.triggered.connect(self.stop_output_process)

    def update_run_actions_state(self, editor):
        is_python_file = False
        if editor:
            path = self.file_manager.open_file_paths.get(editor)
            if path and path.endswith(".py"):
                is_python_file = True

        if self.run_in_terminal_action:
            self.run_in_terminal_action.setEnabled(is_python_file)
        if self.run_in_output_action:
            self.run_in_output_action.setEnabled(is_python_file)

    @Slot(str)
    def run_current_file(self, mode="terminal"):
        if not self.workspace_path:
            QMessageBox.warning(
                self.main_window, "No Workspace", "Please open a workspace folder."
            )
            return

        editor = self.main_window.get_current_editor()
        if not editor or editor not in self.file_manager.open_file_paths:
            QMessageBox.warning(
                self.main_window, "No Active File", "Please select a file to run."
            )
            return

        file_path = self.file_manager.open_file_paths[editor]
        if not file_path.endswith(".py"):
            QMessageBox.warning(
                self.main_window,
                "Not a Python File",
                "This can only run Python (.py) files.",
            )
            return

        if mode == "terminal":
            self.main_window.terminal_dock.setVisible(True)
            self.main_window.terminal_dock.raise_()

            new_terminal = self.main_window.terminal.create_new_terminal()

            if new_terminal:
                term_command = f'python -u "{file_path}"\r\n'
                new_terminal.send_command(term_command)

        elif mode == "output":
            if self.process_runner and self.process_runner.isRunning():
                QMessageBox.warning(
                    self.main_window, "Process Running", "A process is already running."
                )
                return

            self.main_window.log_to_output(
                "Run",
                f"Running: {sys.executable} -u {file_path}\n",
                clear=True,
                raise_panel=True,
            )
            command_list = [sys.executable, "-u", file_path]

            self.process_runner = ProcessRunner(command_list, self.workspace_path)
            self.process_runner.stdout_received.connect(self.on_process_stdout)
            self.process_runner.stderr_received.connect(self.on_process_stderr)

            self.process_runner.started.connect(
                lambda: self.main_window.stop_action.setEnabled(True)
            )
            self.process_runner.finished.connect(self.on_process_finished)

            self.process_runner.start()

    @Slot(str)
    def on_process_stdout(self, text: str):
        self.main_window.log_to_output("Run", text, raise_panel=True)

    @Slot(str)
    def on_process_stderr(self, text: str):
        self.main_window.log_to_output("Run", text, raise_panel=True)

    @Slot(int)
    def on_process_finished(self, exit_code: int):
        self.main_window.log_to_output(
            "Run",
            f"\n--- Process finished with exit code {exit_code} ---",
            raise_panel=True,
        )
        self.main_window.stop_action.setEnabled(False)

    @Slot()
    def stop_output_process(self):
        print("[RunManager] Stop button clicked.")
        if self.process_runner and self.process_runner.isRunning():
            self.process_runner.stop()
