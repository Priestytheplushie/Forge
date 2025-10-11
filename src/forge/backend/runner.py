import subprocess
import sys
import threading
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
                bufsize=1,
            )

            def stream_reader(pipe, signal):
                try:
                    for line in iter(pipe.readline, ""):
                        signal.emit(line)
                finally:
                    pipe.close()

            stdout_thread = threading.Thread(
                target=stream_reader, args=(self.process.stdout, self.stdout_received)
            )
            stderr_thread = threading.Thread(
                target=stream_reader, args=(self.process.stderr, self.stderr_received)
            )

            stdout_thread.start()
            stderr_thread.start()

            stdout_thread.join()
            stderr_thread.join()

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
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                print("[ProcessRunner] Process did not terminate, killing.")
                self.process.kill()
