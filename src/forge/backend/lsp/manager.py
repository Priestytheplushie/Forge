import sys
import subprocess
import threading
import os
from pathlib import Path
from PySide6.QtCore import QObject, Signal

from .protocol import encode_message, decode_message


class LSPManager(QObject):
    lsp_ready = Signal()
    lsp_response_received = Signal(dict)
    lsp_notification_received = Signal(dict)
    command_received = Signal(str, list)

    def __init__(
        self,
        app_root: str,
        workspace_path: str,
        initialization_options: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.app_root = Path(app_root)
        self.workspace_path = workspace_path
        self.settings_payload = initialization_options
        self.server_process = None
        self.reader_thread = None
        self._next_id = 1

    def start_server(self):
        command_name = (
            "basedpyright-langserver.cmd"
            if sys.platform == "win32"
            else "basedpyright-langserver"
        )
        command = [command_name, "--stdio"]

        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)
        node_modules_bin = self.app_root / "node_modules" / ".bin"
        env["PATH"] = str(node_modules_bin) + os.pathsep + env["PATH"]

        print("[LSPManager] Starting basedpyright with custom settings...")

        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            self.server_process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace_path,
                env=env,
                startupinfo=startupinfo,
                shell=(sys.platform == "win32"),
            )

            self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.reader_thread.start()
            threading.Thread(target=self._log_stderr, daemon=True).start()

            self._initialize_server()
        except Exception as e:
            print(f"[LSPManager] Failed to start server: {e}")

    def _log_stderr(self):
        for line in iter(self.server_process.stderr.readline, b""):
            print(f"[basedpyright STDERR] {line.decode('utf-8').strip()}")

    def _read_loop(self):
        while True:
            try:
                message = decode_message(self.server_process.stdout)

                if message.get("method") == "workspace/executeCommand":
                    command = message.get("params", {}).get("command")
                    if command and command.startswith("forge."):
                        print(f"[LSPManager] Intercepted custom command: {command}")
                        self.command_received.emit(
                            command, message.get("params", {}).get("arguments", [])
                        )
                        continue

                if "id" in message:
                    if message.get("id") == 1 and "result" in message:
                        print("[LSPManager] Received 'initialize' response.")
                        self.send_notification("initialized", {})
                        print("[LSPManager] Sent 'initialized' notification.")

                        self.send_notification(
                            "workspace/didChangeConfiguration",
                            {"settings": self.settings_payload},
                        )
                        print(
                            "[LSPManager] Sent 'workspace/didChangeConfiguration' with custom settings."
                        )

                        self.lsp_ready.emit()

                    self.lsp_response_received.emit(message)
                else:
                    self.lsp_notification_received.emit(message)

            except EOFError:
                print("[LSPManager] LSP server connection closed.")
                break
            except Exception as e:
                print(f"[LSPManager] Error decoding message: {e}")
                break

    def send_request(self, method: str, params: dict):
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params,
        }
        self._next_id += 1
        self._send_message(request)
        return request["id"]

    def send_notification(self, method: str, params: dict):
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        self._send_message(notification)

    def _send_message(self, message: dict):
        if self.server_process and self.server_process.stdin:
            try:
                self.server_process.stdin.write(encode_message(message))
                self.server_process.stdin.flush()
            except Exception as e:
                print(f"[LSPManager] Could not send message: {e}")

    def _initialize_server(self):
        workspace_uri = Path(self.workspace_path).as_uri()
        params = {
            "processId": os.getpid(),
            "capabilities": {
                "workspace": {"didChangeConfiguration": {}},
                "textDocument": {
                    "codeAction": {"dynamicRegistration": True},
                    "semanticTokens": {
                        "dynamicRegistration": False,
                        "requests": {"full": True},
                        "tokenTypes": [
                            "namespace",
                            "type",
                            "class",
                            "enum",
                            "interface",
                            "struct",
                            "typeParameter",
                            "parameter",
                            "variable",
                            "property",
                            "enumMember",
                            "event",
                            "function",
                            "method",
                            "macro",
                            "keyword",
                            "modifier",
                            "comment",
                            "string",
                            "number",
                            "regexp",
                            "operator",
                        ],
                        "tokenModifiers": [
                            "declaration",
                            "definition",
                            "readonly",
                            "static",
                            "deprecated",
                            "abstract",
                            "async",
                            "modification",
                            "documentation",
                            "defaultLibrary",
                        ],
                    },
                },
            },
            "trace": "off",
            "initializationOptions": {},
            "workspaceFolders": [
                {"uri": workspace_uri, "name": Path(self.workspace_path).name}
            ],
            "rootUri": workspace_uri,
        }
        self.send_request("initialize", params)

    def shutdown(self):
        if self.server_process:
            self.send_request("shutdown", None)
            self.send_notification("exit", None)
            self.server_process.terminate()
            self.server_process.wait(timeout=2)
