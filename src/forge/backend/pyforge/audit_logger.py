import json
import time
from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot
import uuid


class AuditLogger(QObject):
    """
    Manages the creation, finalization, and persistence of PyForge session logs.
    """

    log_entry_added = Signal(dict)
    session_started = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_log_path = None
        self.log_entries = []
        self.in_flight_entries = {}

    @Slot(str)
    def start_session(self, workspace_path: str):
        """Creates a new .pflog file for the session."""
        self.stop_session()

        sessions_dir = Path(workspace_path) / ".forge" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_log_path = sessions_dir / f"{timestamp}.pflog"

        session_start_entry = {
            "action_id": f"session_start_{uuid.uuid4().hex}",
            "timestamp": int(time.time() * 1000),
            "type": "SessionStarted",
            "details": {"log_file": str(self.session_log_path)},
        }
        self.log_entries.append(session_start_entry)
        self._write_to_log(session_start_entry)

        self.session_started.emit(str(self.session_log_path))
        self.log_entry_added.emit(session_start_entry)

    @Slot()
    def stop_session(self):
        """Writes a session end entry to the log file."""
        if self.session_log_path and self.session_log_path.exists():
            session_end_entry = {
                "action_id": f"session_end_{uuid.uuid4().hex}",
                "timestamp": int(time.time() * 1000),
                "type": "SessionStopped",
            }
            self._write_to_log(session_end_entry)

        self.session_log_path = None
        self.log_entries = []
        self.in_flight_entries = {}

    def begin_action(
        self, action_type: str, source: dict, target: dict = None, details: dict = None
    ) -> dict:
        """Creates a new log entry and holds it in an in-flight state."""
        log_entry = {
            "action_id": uuid.uuid4().hex,
            "timestamp": int(time.time() * 1000),
            "type": action_type,
            "source": source,
            "target": target or {},
            "details": details or {},
            "outcome": None,
        }
        return log_entry

    def associate_action(self, req_id: int, log_entry: dict):
        """Links a request ID to a pending log entry."""
        if req_id != -1:
            self.in_flight_entries[req_id] = log_entry

    @Slot(dict, dict)
    def finalize_action(self, log_entry: dict, agent_response: dict):
        """Finalizes a log entry with the agent's response and writes it to disk."""
        log_entry["outcome"] = agent_response
        self.log_entries.append(log_entry)
        self._write_to_log(log_entry)
        self.log_entry_added.emit(log_entry)

    @Slot()
    def finalize_pending_as_crashed(self):
        """
        Finalizes any in-flight requests with a 'Connection Lost' status.
        This is called when the agent disconnects unexpectedly.
        """
        for req_id, log_entry in self.in_flight_entries.items():
            crash_response = {
                "status": "error",
                "payload": {
                    "type": "traceback",
                    "error_type": "ConnectionLost",
                    "error_message": "The agent stopped responding after this action was sent. This may indicate the action caused the agent or target application to crash.",
                },
            }
            self.finalize_action(log_entry, crash_response)
        self.in_flight_entries.clear()

    def _write_to_log(self, entry: dict):
        """Appends a single JSON entry to the log file."""
        if not self.session_log_path:
            return
        try:
            with open(self.session_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError as e:
            print(
                f"[AuditLogger] CRITICAL: Could not write to log file {self.session_log_path}: {e}"
            )
