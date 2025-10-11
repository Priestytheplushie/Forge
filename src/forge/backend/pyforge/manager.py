import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThread
import time
import psutil

from .client import PyForgeClient
from ..project.venv_manager import VenvManager


class SystemMonitor(QThread):
    """
    A worker thread that monitors a process's system resource usage
    out-of-process to avoid GIL contention.
    """

    system_metrics_updated = Signal(dict)

    def __init__(self, pid: int, parent=None):
        super().__init__(parent)
        self.pid = pid
        self.is_running = False

    def run(self):
        self.is_running = True
        try:
            process = psutil.Process(self.pid)

            process.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"[SystemMonitor] Failed to attach to process {self.pid}: {e}")
            self.is_running = False
            return

        while self.is_running:
            try:

                cpu = process.cpu_percent(interval=1.0)
                mem = process.memory_info().rss / (1024 * 1024)
                self.system_metrics_updated.emit(
                    {"cpu_usage": cpu, "memory_rss_mb": mem}
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):

                self.is_running = False
            except Exception as e:
                print(f"[SystemMonitor] Error during metric collection: {e}")
                time.sleep(1)

        print(f"[SystemMonitor] Stopped monitoring process {self.pid}.")

    def stop(self):
        self.is_running = False


class PyForgeManager(QObject):
    """Manages the lifecycle of a PyForge session (process and client)."""

    session_started = Signal(str, int)
    session_stopped = Signal()
    status_changed = Signal(str, str)
    process_output_received = Signal(str)
    system_metrics_updated = Signal(dict)

    def __init__(self, app_root: str, parent=None):
        super().__init__(parent)
        self.app_root = app_root
        self.client = PyForgeClient(self)
        self.connection_timer = QTimer(self)
        self.connection_timer.setSingleShot(True)
        self.connection_timer.setInterval(1500)

        self.client.status_changed.connect(self.status_changed)
        self.client.status_changed.connect(self._on_client_status_changed)
        self.client.session_info_received.connect(self.on_session_info_received)
        self.connection_timer.timeout.connect(self.client.connect)

        self.active_script_path = None
        self.active_terminal_instance = None
        self.main_window = None
        self.monitor_thread = None

    def is_session_active(self) -> bool:
        """Checks if a PyForge session is currently running and connected."""
        return self.active_terminal_instance is not None and self.client._is_connected

    @Slot(str, str, object)
    def launch(
        self, python_executable: str, script_path: str, terminal_instance: object
    ):
        if self.active_terminal_instance:
            self.status_changed.emit("error", "A PyForge session is already running.")
            return

        self.active_script_path = script_path
        self.active_terminal_instance = terminal_instance

        if hasattr(self.active_terminal_instance, "backend"):
            self.active_terminal_instance.backend.data_for_frontend.connect(
                self.process_output_received
            )

        workspace_path = self.main_window.controller.workspace_manager.workspace_path
        python_exe = VenvManager.find_venv_python(workspace_path)

        pyforge_launcher = str(
            Path(self.app_root) / "src" / "pyforge" / "core" / "cli.py"
        )
        command_list = [python_exe, "-u", pyforge_launcher, "run", script_path]

        terminal_instance.send_command(command_list)

        self.status_changed.emit(
            "connecting",
            f"Launched process '{Path(script_path).name}'. Waiting for agent...",
        )
        self.connection_timer.start()

    def send_command(self, command: str):
        self.client.send_command(command)

    def stop_session(self):
        if self.active_terminal_instance:
            self.main_window.terminal.kill_terminal_instance(
                self.active_terminal_instance
            )
            self.active_terminal_instance = None

        self.on_session_ended()

    @Slot(str, str)
    def _on_client_status_changed(self, status: str, message: str):
        if status == "connected":
            pass
        if status == "disconnected" and self.active_terminal_instance:
            self.on_session_ended()

    @Slot(dict)
    def on_session_info_received(self, info: dict):
        pid = info.get("pid", -1)
        self.session_started.emit(self.active_script_path, pid)

        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.stop()
            self.monitor_thread.wait()

        if pid != -1:
            self.monitor_thread = SystemMonitor(pid, self)
            self.monitor_thread.system_metrics_updated.connect(
                self.system_metrics_updated
            )
            self.monitor_thread.start()

    def on_session_ended(self):
        """Unified cleanup function."""

        if self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.stop()
            self.monitor_thread.wait()
            self.monitor_thread = None

        if self.active_terminal_instance:
            if hasattr(self.active_terminal_instance, "backend"):
                try:
                    self.active_terminal_instance.backend.data_for_frontend.disconnect(
                        self.process_output_received
                    )
                except RuntimeError:
                    pass
            self.active_terminal_instance = None

        self.client.disconnect()
        self.active_script_path = None
        self.status_changed.emit("idle", "Session stopped.")
        self.session_stopped.emit()

    def set_main_window(self, main_window):
        self.main_window = main_window
