import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

APP_ROOT_PATH = Path(__file__).resolve().parent.parent.parent


def _bootstrap_path():
    """Adds the 'src' directory to the Python path."""
    src_path = APP_ROOT_PATH / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_bootstrap_path()

from forge.frontend.windows.main_window import MainWindow


def main():
    """Initializes and runs the Forge application."""
    app = QApplication(sys.argv)
    window = MainWindow(app_root=str(APP_ROOT_PATH))

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
