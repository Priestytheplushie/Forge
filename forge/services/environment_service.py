import customtkinter as ctk
import os
import sys
import subprocess


class EnvironmentService:
    def __init__(self, app_instance):
        self.app = app_instance
        self.project_path = app_instance.project_service.project_path
        self.interpreters = []
        self.active_interpreter = None
        self.discover_interpreters()

    def discover_interpreters(self):
        """Finds system Python interpreters and virtual environments."""
        found_paths = set()
        system_python = sys.executable
        if system_python:
            found_paths.add(os.path.realpath(system_python))

        if self.project_path:
            for name in [".venv", "venv"]:
                venv_path = os.path.join(self.project_path, name)
                if os.path.isdir(venv_path):
                    interp_path = os.path.join(
                        venv_path,
                        "Scripts" if sys.platform == "win32" else "bin",
                        "python",
                    )
                    if os.path.isfile(interp_path):
                        found_paths.add(os.path.realpath(interp_path))

        self.interpreters = sorted(
            list(found_paths), key=lambda x: ("venv" not in x, x)
        )
        if self.interpreters and not self.active_interpreter:
            self.active_interpreter = self.interpreters[0]

        return self.interpreters

    def get_version(self, python_path):
        """Gets the version string of a Python interpreter."""
        try:
            result = subprocess.run(
                [python_path, "--version"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "Error"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return "Unknown"

    def set_active_interpreter(self, path):
        """Sets the specified path as the active interpreter and restarts services."""
        if path in self.interpreters and path != self.active_interpreter:
            self.active_interpreter = path
            print(f"Active interpreter set to: {self.active_interpreter}")

            version = self.get_version(self.active_interpreter)
            self.app.status_bar.update_python_version(version)

            self.app.start_lsp_client()

            self.app.activate_terminal_venv()
        else:
            print(f"Interpreter unchanged or invalid: {path}")

    def select_interpreter(self):
        """Shows a menu to the user to select an interpreter."""
        menu = ctk.CTkMenu(self.app, fg_color="#2b2b2b")
        for interp_path in self.interpreters:
            version = self.get_version(interp_path)
            label = (
                f"{os.path.basename(os.path.dirname(os.path.dirname(interp_path)))} ({version})"
                if "venv" in interp_path
                else version
            )
            menu.add_command(
                label=label,
                command=lambda p=interp_path: self.set_active_interpreter(p),
            )

        button = self.app.status_bar.python_version_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() - (len(self.interpreters) * 30)
        menu.place(x=x, y=y)
