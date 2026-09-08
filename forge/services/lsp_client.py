import subprocess, threading, json, time, sys, os
from pathlib import Path
from queue import Queue
from collections import defaultdict

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ForgeLspClient:
    def __init__(self, master_app, ide_python_executable, project_python_executable):
        self.master_app = master_app
        self.ide_python = ide_python_executable
        self.project_python = project_python_executable
        self.process = None
        self.message_id_counter = 1
        self.requests = {}
        self.lock = threading.Lock()

        self.notification_queues = defaultdict(Queue)
        self.worker_threads = {}
        self.shutdown_event = threading.Event()

        self.start_lsp_server()
        if self.process:
            self.reader_thread = threading.Thread(
                target=self._read_from_server, daemon=True
            )
            self.stderr_thread = threading.Thread(
                target=self._read_from_stderr, daemon=True
            )
            self.reader_thread.start()
            self.stderr_thread.start()

    def _read_from_server(self):
        while self.process and self.process.poll() is None:
            try:
                headers = {}
                content_length = 0
                while True:
                    line = self.process.stdout.readline()
                    if not line or self.shutdown_event.is_set():
                        return
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        break
                    key, value = line_str.split(": ", 1)
                    if key == "Content-Length":
                        content_length = int(value)
                if not content_length:
                    continue
                body = self.process.stdout.read(content_length)
                response = json.loads(body.decode("utf-8"))

                if "id" in response and response["id"] in self.requests:
                    callback = self.requests.pop(response["id"], None)
                    if callback:
                        self.master_app.after(0, callback, response.get("result"))

                elif (
                    "method" in response
                    and response["method"] == "textDocument/publishDiagnostics"
                ):
                    params = response.get("params", {})
                    uri = params.get("uri", "")
                    diagnostics = params.get("diagnostics", [])
                    self.master_app.on_diagnostics(uri, diagnostics)
            except Exception as e:
                if not self.shutdown_event.is_set():
                    print(f"LSP Read Error: {e}")
                    time.sleep(0.1)

    def initialize(self, root_uri):
        initialization_options = {
            "pylsp": {"plugins": {"jedi": {"environment": self.project_python}}}
        }
        params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "capabilities": {},
            "initializationOptions": initialization_options,
        }

        def initialized_callback(result):
            print("LSP Server Initialized: True")
            self._send_notification_internal("initialized", {})

        self._send_request("initialize", params, initialized_callback)

    def did_open(self, file_uri, content):
        params = {
            "textDocument": {
                "uri": file_uri,
                "languageId": "python",
                "version": 1,
                "text": content,
            }
        }
        self._enqueue_notification(file_uri, "textDocument/didOpen", params)

    def _notification_worker(self, uri):
        q = self.notification_queues[uri]
        while not self.shutdown_event.is_set():
            try:
                method, params = q.get(timeout=1)
                self._send_notification_internal(method, params)
                q.task_done()
            except Exception:
                continue
        with self.lock:
            if uri in self.worker_threads:
                del self.worker_threads[uri]

    def _send_notification_internal(self, method, params):
        if not self.process or self.process.poll() is not None:
            return
        request = {"jsonrpc": "2.0", "method": method, "params": params}
        body = json.dumps(request).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        try:
            with self.lock:
                self.process.stdin.write(header)
                self.process.stdin.write(body)
                self.process.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            print(f"LSP notify failed: {e}")
            self.process = None

    def _enqueue_notification(self, uri, method, params):
        with self.lock:
            if uri not in self.worker_threads:
                thread = threading.Thread(
                    target=self._notification_worker, args=(uri,), daemon=True
                )
                self.worker_threads[uri] = thread
                thread.start()
        self.notification_queues[uri].put((method, params))

    def did_change(self, file_uri, version, content):
        params = {
            "textDocument": {"uri": file_uri, "version": version},
            "contentChanges": [{"text": content}],
        }
        self._enqueue_notification(file_uri, "textDocument/didChange", params)

    def shutdown(self):
        print("Shutting down LSP server...")
        self.shutdown_event.set()
        for thread in list(self.worker_threads.values()):
            thread.join(timeout=0.5)
        if self.process and self.process.poll() is None:
            self._send_request("shutdown", {}, callback=None)
            self._send_notification_internal("exit", {})
            print("LSP shutdown signals sent.")
        time.sleep(0.05)
        self.process = None
        print("LSP client finished.")

    def start_lsp_server(self):
        command = [self.ide_python, "-m", "pylsp"]
        print(f"Starting LSP server with command: {' '.join(command)}")
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=CREATE_NO_WINDOW,
            )
        except FileNotFoundError:
            print(
                f"LSP Error: Could not find pylsp. Make sure it's installed in {self.ide_python}"
            )

    def _read_from_stderr(self):
        while self.process and self.process.poll() is None:
            try:
                error_line = (
                    self.process.stderr.readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                if error_line and not self.shutdown_event.is_set():
                    print(f"[LSP stderr] {error_line}")
            except Exception:
                break

    def _send_request(self, method, params, callback=None):
        if not self.process or self.process.poll() is not None:
            return
        with self.lock:
            message_id = self.message_id_counter
            self.message_id_counter += 1
        request = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params,
        }
        if callback:
            self.requests[message_id] = callback
        body = json.dumps(request).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        try:
            with self.lock:
                self.process.stdin.write(header)
                self.process.stdin.write(body)
                self.process.stdin.flush()
        except (OSError, BrokenPipeError) as e:
            print(f"LSP send failed: {e}")
            self.process = None

    def get_completions(self, file_uri, line, char, callback):
        params = {
            "textDocument": {"uri": file_uri},
            "position": {"line": line, "character": char},
        }

        def completion_result_handler(result):
            items = []
            if result:
                items = result if isinstance(result, list) else result.get("items", [])
            callback(items)

        self._send_request("textDocument/completion", params, completion_result_handler)

    def did_save(self, file_uri):
        params = {"textDocument": {"uri": file_uri}}
        self._enqueue_notification(file_uri, "textDocument/didSave", params)
