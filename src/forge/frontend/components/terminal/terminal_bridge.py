from PySide6.QtCore import QObject, Signal, Slot


class TerminalBridge(QObject):
    """Bridge object for the xterm.js terminal component."""

    js_ready = Signal()
    data_to_backend = Signal(str)
    resize_requested = Signal(int, int)

    start_backend_requested = Signal(int, int)

    @Slot()
    def js_loaded(self):
        """Called from JS when the frontend is initialized."""
        self.js_ready.emit()

    @Slot(str)
    def receive_data_from_js(self, data):
        """Receives user input from the JS terminal."""
        self.data_to_backend.emit(data)

    @Slot(int, int)
    def resize_pty(self, cols, rows):
        """Receives resize events from JS for an active session."""
        self.resize_requested.emit(cols, rows)

    @Slot(int, int)
    def receive_initial_size(self, cols: int, rows: int):
        """
        Receives the initial terminal size from JS and emits the internal
        Python signal to start the backend process.
        """
        print(
            f"[Bridge] Received initial size from JS: {cols}x{rows}. Emitting start_backend_requested."
        )
        self.start_backend_requested.emit(cols, rows)
