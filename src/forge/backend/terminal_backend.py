import os
import sys
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, Slot

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import winpty
else:
    import pty


class PtyReader(QThread):
    data_ready = Signal(str)

    def __init__(self, pty_process, pty_master_fd, parent=None):
        super().__init__(parent)
        self.pty_process = pty_process
        self.pty_master_fd = pty_master_fd
        self.running = True

    def run(self):
        print("[PtyReader] Thread starting.")
        while self.running:
            try:
                if IS_WINDOWS:
                    data = self.pty_process.read(1024)
                else:
                    data_bytes = os.read(self.pty_master_fd, 1024)
                    data = data_bytes.decode("utf-8", errors="replace")

                if data:
                    self.data_ready.emit(data)
                else:
                    break
            except Exception:
                break
        print("[PtyReader] Thread finished.")
        self.running = False

    def stop(self):
        print("[PtyReader] Stop requested.")
        self.running = False


class TerminalBackend(QObject):
    data_for_frontend = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pty_process = None
        self.pty_master_fd = None
        self.reader_thread = None
        print(f"[TerminalBackend] __init__ (id: {id(self)})")

    def start_pty_process(
        self, workspace_path: str, initial_cols: int, initial_rows: int
    ):
        print(f"[TerminalBackend] Starting pty process in '{workspace_path}'...")
        try:
            if IS_WINDOWS:
                env = os.environ.copy()
                if "VIRTUAL_ENV" in env:
                    del env["VIRTUAL_ENV"]
                venv_activate_script = (
                    Path(workspace_path) / ".venv" / "Scripts" / "Activate.ps1"
                )
                shell_cmd = ["powershell.exe", "-NoLogo"]
                if venv_activate_script.exists():
                    shell_cmd.extend(
                        ["-NoExit", "-Command", f"& '{str(venv_activate_script)}'"]
                    )
                self.pty_process = winpty.PtyProcess.spawn(
                    shell_cmd,
                    dimensions=(initial_rows, initial_cols),
                    env=env,
                    cwd=workspace_path,
                )
                self.pty_master_fd = self.pty_process.fileno()
            else:
                shell_cmd = os.environ.get("SHELL", "bash")
                pid, self.pty_master_fd = pty.fork()
                if pid == 0:
                    os.execvp(shell_cmd, [shell_cmd])
                self.pty_process = pid

            print(f"[TerminalBackend] Pty process started successfully.")
            self.reader_thread = PtyReader(self.pty_process, self.pty_master_fd, self)
            self.reader_thread.data_ready.connect(self.data_for_frontend)
            self.reader_thread.start()
        except Exception as e:
            error_msg = f"FATAL ERROR starting terminal process: {e}\r\n"
            print(error_msg)
            self.data_for_frontend.emit(error_msg)

    @Slot(str)
    def write_to_pty(self, data: str):
        if self.pty_process and self.reader_thread and self.reader_thread.running:
            try:
                if IS_WINDOWS:
                    self.pty_process.write(data)
                else:
                    os.write(self.pty_master_fd, data.encode("utf-8"))
            except Exception:
                pass

    @Slot(int, int)
    def set_pty_size(self, cols: int, rows: int):
        print(f"[TerminalBackend] Resize request received: {cols} cols, {rows} rows")
        if self.pty_process and cols > 0 and rows > 0:
            try:
                if IS_WINDOWS:
                    self.pty_process.setwinsize(rows, cols)
            except Exception as e:
                print(f"[TerminalBackend] Error resizing pty: {e}")

    def close(self):
        print(f"[TerminalBackend] Close called (id: {id(self)})")
        if self.reader_thread:
            self.reader_thread.stop()

        if self.pty_process:
            try:
                if IS_WINDOWS:
                    if self.pty_process.isalive():
                        self.pty_process.close()
                else:
                    import signal

                    os.kill(self.pty_process, signal.SIGKILL)
            except Exception as e:
                print(f"[TerminalBackend] Error during process close: {e}")
            self.pty_process = None

        if self.reader_thread and self.reader_thread.isRunning():
            print("[TerminalBackend] Waiting for reader thread to terminate...")
            self.reader_thread.wait(500)
            if self.reader_thread.isRunning():
                print("[TerminalBackend] Reader thread did not terminate, forcing it.")
                self.reader_thread.terminate()
        self.reader_thread = None
