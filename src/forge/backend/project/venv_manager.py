import sys
from pathlib import Path


class VenvManager:
    """A utility class to detect and manage Python virtual environments."""

    @staticmethod
    def find_venv_python(workspace_path: str) -> str:
        """
        Finds the Python executable within a .venv in the workspace.
        Falls back to the global Python executable if not found.
        """
        if not workspace_path:
            return sys.executable

        workspace = Path(workspace_path)
        venv_path = workspace / ".venv"

        if venv_path.is_dir():
            if sys.platform == "win32":
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                python_exe = venv_path / "bin" / "python"

            if python_exe.exists():
                print(f"[VenvManager] Found virtual environment Python: {python_exe}")
                return str(python_exe)

        print(
            f"[VenvManager] No virtual environment found. Using global Python: {sys.executable}"
        )
        return sys.executable
