import subprocess
import sys
from PySide6.QtCore import QObject, QThread, Signal, Slot


class ProcessRunner(QThread):
    """
    A worker thread that runs a command in a subprocess and streams its output.
    """

    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(int)

    def __init__(self, command: list[str], cwd: str, parent=None):
        super().__init__(parent)
        self.command = command
        self.cwd = cwd
        self.process = None

    def run(self):
        print(f"[ProcessRunner] Starting command: {' '.join(self.command)}")
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.cwd,
                startupinfo=startupinfo,
            )

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
                    self.stdout_received.emit(line)

            if self.process.stderr:
                for line in iter(self.process.stderr.readline, ""):
                    self.stderr_received.emit(line)

            self.process.wait()
            self.finished.emit(self.process.returncode)
            print(
                f"[ProcessRunner] Command finished with exit code: {self.process.returncode}"
            )

        except Exception as e:
            print(f"[ProcessRunner] Error: {e}")
            self.stderr_received.emit(str(e))
            self.finished.emit(-1)

    def stop(self):
        if self.process and self.process.poll() is None:
            print("[ProcessRunner] Terminating process.")
            self.process.terminate()
