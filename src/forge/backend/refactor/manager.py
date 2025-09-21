import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread, Slot
import time
import os

from ..tools import comment_cleanup
from ..tools import find_replace


class ExternalToolWorker(QThread):
    """Worker thread to run external CLI refactoring tools without blocking the UI."""

    finished = Signal(dict)
    log_message = Signal(str)

    def __init__(
        self, file_path_str: str, tools: list[str], session_dir: Path, parent=None
    ):
        super().__init__(parent)
        self.file_path = Path(file_path_str)
        self.tools = tools
        self.session_dir = session_dir

    def run(self):

        result_data = {}
        try:
            temp_path = self.session_dir / self.file_path.name
            shutil.copy2(self.file_path, temp_path)
            original_content = self.file_path.read_text(encoding="utf-8")
            tool_summaries = []

            def run_tool(command, tool_name, summary):
                self.log_message.emit(
                    f"[{tool_name}] Running on {self.file_path.name}..."
                )
                content_before = temp_path.read_text(encoding="utf-8")
                result = subprocess.run(
                    command, capture_output=True, text=True, encoding="utf-8"
                )
                if result.stderr:
                    self.log_message.emit(
                        f"[{tool_name}] STDERR: {result.stderr.strip()}"
                    )
                content_after = temp_path.read_text(encoding="utf-8")
                if content_before != content_after:
                    tool_summaries.append(summary)

            if "ruff_format" in self.tools:
                run_tool(
                    [sys.executable, "-m", "ruff", "format", str(temp_path)],
                    "Ruff Format",
                    "Organized Imports (Ruff)",
                )
            if "ruff_fix" in self.tools:
                run_tool(
                    [
                        sys.executable,
                        "-m",
                        "ruff",
                        "check",
                        str(temp_path),
                        "--fix",
                        "--unsafe-fixes",
                    ],
                    "Ruff Fix",
                    "Fixed Lint Issues (Ruff)",
                )
            if "black" in self.tools:
                run_tool(
                    [sys.executable, "-m", "black", str(temp_path)],
                    "Black",
                    "Formatted Code (Black)",
                )
            if "pyupgrade" in self.tools:
                run_tool(
                    [sys.executable, "-m", "pyupgrade", "--py38-plus", str(temp_path)],
                    "pyupgrade",
                    "Upgraded Syntax (pyupgrade)",
                )
            if "docformatter" in self.tools:
                run_tool(
                    [
                        sys.executable,
                        "-m",
                        "docformatter",
                        "--in-place",
                        str(temp_path),
                    ],
                    "docformatter",
                    "Formatted Docstrings (docformatter)",
                )

            modified_content = temp_path.read_text(encoding="utf-8")

            if original_content != modified_content:
                result_data = {
                    "original_path": str(self.file_path),
                    "temp_path": str(temp_path),
                    "original_content": original_content,
                    "modified_content": modified_content,
                    "summaries": tool_summaries or ["Cleaned up file"],
                }
            else:
                temp_path.unlink()
            self.finished.emit({"path": str(self.file_path), "changes": result_data})
        except Exception as e:
            self.finished.emit({"path": str(self.file_path), "error": str(e)})


class ProgrammaticToolWorker(QThread):
    """Worker thread to run internal Python-based refactoring tools."""

    finished = Signal(dict)
    log_message = Signal(str)

    def __init__(
        self,
        file_path_str: str,
        tool_function,
        tool_name: str,
        tool_summary: str,
        session_dir: Path,
        tool_kwargs: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = Path(file_path_str)
        self.tool_function = tool_function
        self.tool_name = tool_name
        self.tool_summary = tool_summary
        self.session_dir = session_dir
        self.tool_kwargs = tool_kwargs

    def run(self):
        self.log_message.emit(f"[{self.tool_name}] Scanning {self.file_path.name}...")
        try:
            original_content = self.file_path.read_text(encoding="utf-8")
            modified_content = self.tool_function(original_content, **self.tool_kwargs)

            if modified_content is not None and original_content != modified_content:
                temp_path = self.session_dir / self.file_path.name
                temp_path.write_text(modified_content, encoding="utf-8")
                result_data = {
                    "original_path": str(self.file_path),
                    "temp_path": str(temp_path),
                    "original_content": original_content,
                    "modified_content": modified_content,
                    "summaries": [self.tool_summary],
                }
                self.finished.emit(
                    {"path": str(self.file_path), "changes": result_data}
                )
            else:
                self.finished.emit({"path": str(self.file_path), "changes": {}})
        except Exception as e:
            self.finished.emit({"path": str(self.file_path), "error": str(e)})


class RefactorManager(QObject):
    """Manages code refactoring and cleanup operations."""

    review_session_started = Signal(dict)
    log_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.session_dir = None
        self.pending_files = []
        self.session_changes = {}
        self.worker_class = None
        self.worker_kwargs = {}

    def _start_session(self, files_to_process: list[str], worker_class, **kwargs):
        if self.worker and self.worker.isRunning():
            self.log_message.emit(
                "[Forge Refactor] A refactor operation is already in progress."
            )
            return

        self.session_dir = (
            Path(tempfile.gettempdir()) / f"forge_review_{int(time.time())}"
        )
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.pending_files = files_to_process[:]
        self.session_changes = {}
        self.worker_class = worker_class
        self.worker_kwargs = kwargs

        self.log_message.emit(
            f"[Forge Refactor] Starting operation on {len(files_to_process)} file(s)..."
        )
        self._process_next_file()

    def _process_next_file(self):
        if not self.pending_files:
            self._finish_session()
            return

        file_path = self.pending_files.pop(0)
        self.worker = self.worker_class(
            file_path_str=file_path, session_dir=self.session_dir, **self.worker_kwargs
        )
        self.worker.log_message.connect(self.log_message)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    @Slot(dict)
    def _on_worker_finished(self, result: dict):
        if result.get("error"):
            self.log_message.emit(
                f"[Forge Refactor] ERROR processing {result.get('path')}: {result.get('error')}"
            )

        if result.get("changes"):
            self.session_changes[result["path"]] = result["changes"]

        self._process_next_file()

    def _finish_session(self):
        final_session_data = {
            "session_dir": str(self.session_dir),
            "changes": self.session_changes,
        }
        self.log_message.emit(
            f"[Forge Refactor] Operation complete. Found changes in {len(self.session_changes)} file(s)."
        )
        self.review_session_started.emit(final_session_data)

    def _get_files_from_path(self, path_str: str) -> list[str]:
        path = Path(path_str)
        files_to_process = []
        if path.is_dir():
            for py_file in path.rglob("*.py"):
                if any(
                    part in py_file.parts
                    for part in [".venv", ".git", "__pycache__", ".forge"]
                ):
                    continue
                files_to_process.append(str(py_file))
        elif path.is_file() and path.suffix == ".py":
            files_to_process.append(str(path))
        return files_to_process

    def _run_external_on_path(self, path_str: str, tools: list[str]):
        files = self._get_files_from_path(path_str)
        if files:
            self._start_session(files, ExternalToolWorker, tools=tools)
        else:
            self.review_session_started.emit({"changes": {}})

    def _run_programmatic_on_path(
        self,
        path_str: str,
        tool_function,
        tool_name: str,
        tool_summary: str,
        tool_kwargs: dict,
    ):
        files = self._get_files_from_path(path_str)
        if files:
            self._start_session(
                files,
                ProgrammaticToolWorker,
                tool_function=tool_function,
                tool_name=tool_name,
                tool_summary=tool_summary,
                tool_kwargs=tool_kwargs,
            )
        else:
            self.review_session_started.emit({"changes": {}})

    def run_tool_on_path(self, path_str: str, tool: dict, tool_kwargs: dict = {}):
        if tool["handler_type"] == "external":
            self._run_external_on_path(path_str, tools=[tool["id"]])
        elif tool["handler_type"].startswith("programmatic"):
            self._run_programmatic_on_path(
                path_str,
                tool["handler_function"],
                tool["name"],
                tool["summary"],
                tool_kwargs,
            )
        elif tool["handler_type"] == "composite":
            external_tools = [
                t["id"]
                for t in self.main_window.controller.refactor_controller.tool_registry.get_all_tools()
                if t["id"] in tool["tool_ids"] and t["handler_type"] == "external"
            ]
            if external_tools:
                self._run_external_on_path(path_str, tools=external_tools)

    def accept_changes(self, change_data: dict):

        try:
            original_path = Path(change_data["original_path"])
            temp_path = Path(change_data["temp_path"])
            shutil.copy2(temp_path, original_path)
            temp_path.unlink(missing_ok=True)
            print(f"[RefactorManager] Accepted changes for {original_path.name}")
        except Exception as e:
            print(f"[RefactorManager] Error accepting changes: {e}")

    def discard_changes(self, change_data: dict):

        try:
            temp_path = Path(change_data["temp_path"])
            if temp_path.exists():
                temp_path.unlink()
            print(
                f"[RefactorManager] Discarded changes for {Path(change_data['original_path']).name}"
            )
        except Exception as e:
            print(f"[RefactorManager] Error discarding changes: {e}")

    def cleanup_session(self, session_dir_str: str):

        try:
            session_dir = Path(session_dir_str)
            if session_dir.exists():
                shutil.rmtree(session_dir)
                print(f"[RefactorManager] Cleaned up session directory: {session_dir}")
        except Exception as e:
            print(f"[RefactorManager] Error cleaning up session directory: {e}")
