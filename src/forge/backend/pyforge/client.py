import socket
import threading
import queue
import time
import json
from PySide6.QtCore import QObject, Signal, QThread, Slot


class ClientListener(QThread):
    message_received = Signal(dict)
    disconnected = Signal()

    def __init__(self, sock, parent=None):
        super().__init__(parent)
        self.sock = sock
        self._is_running = True

    def run(self):
        buffer = b""
        while self._is_running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    self.disconnected.emit()
                    break

                buffer += data

                while b"\r\n\r\n" in buffer:
                    header_part, _, body_part = buffer.partition(b"\r\n\r\n")
                    headers = dict(
                        line.split(b": ") for line in header_part.split(b"\r\n")
                    )
                    content_length = int(headers[b"Content-Length"])

                    if len(body_part) < content_length:
                        break

                    body_json = body_part[:content_length].decode("utf-8")
                    buffer = body_part[content_length:]
                    self.message_received.emit(json.loads(body_json))

            except (socket.error, ConnectionResetError):
                self.disconnected.emit()
                break

        print("[PyForge Client] Listener thread stopped.")

    def stop(self):
        self._is_running = False


class PyForgeClient(QObject):
    response_received = Signal(int, object)
    session_info_received = Signal(dict)
    log_received = Signal(str)
    subscription_update_received = Signal(dict)
    new_instance_received = Signal(dict)
    status_update_received = Signal(dict)
    status_changed = Signal(str, str)
    disconnected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sock = None
        self.listener_thread = None
        self._next_req_id = 1
        self._is_connected = False
        self.last_known_state = {}

    def connect(self, host="127.0.0.1", port=65432):
        if self._is_connected:
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self._is_connected = True

            self.listener_thread = ClientListener(self.sock, self)
            self.listener_thread.message_received.connect(self._on_message_received)
            self.listener_thread.disconnected.connect(self.on_disconnected)
            self.listener_thread.start()

            self.status_changed.emit(
                "connected", f"Successfully connected to agent at {host}:{port}."
            )
        except Exception as e:
            self.status_changed.emit("error", f"Failed to connect: {e}")

    @Slot(dict)
    def _on_message_received(self, message: dict):
        if "method" in message:
            method = message["method"]
            params = message.get("params", {})
            if method == "pyforge/sessionInfo":
                self.session_info_received.emit(params)
            elif method == "pyforge/log":
                self.log_received.emit(params.get("message", ""))
            elif method == "pyforge/subscription_update":
                self.subscription_update_received.emit(params)
            elif method == "pyforge/new_instance":
                self.new_instance_received.emit(params)
            elif method == "pyforge/statusUpdate":
                self.last_known_state = params.get("last_known_state", {})
                self.status_update_received.emit(params)
        elif "id" in message:
            self.response_received.emit(
                message["id"], message.get("result", message.get("error"))
            )

    def on_disconnected(self):
        self._is_connected = False
        self.status_changed.emit("disconnected", "Connection to agent lost.")
        self.disconnected.emit()
        self.disconnect()

    def _send_request(self, method: str, params: dict = None) -> int:
        if not self._is_connected:
            self.status_changed.emit("error", f"Cannot send '{method}': not connected.")
            return -1

        try:
            req_id = self._next_req_id
            self._next_req_id += 1

            request = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params or {},
            }

            req_bytes = json.dumps(request).encode("utf-8")
            header = f"Content-Length: {len(req_bytes)}\r\n\r\n".encode("utf-8")
            self.sock.sendall(header + req_bytes)
            return req_id
        except socket.error:
            self.on_disconnected()
            return -1

    def send_command(self, command: str):
        return self._send_request("pyforge/execute", {"command": command})

    def execute_script(self, script: str):
        return self._send_request("pyforge/execute_script", {"script": script})

    def get_completions(self, text: str):
        return self._send_request("pyforge/get_completions", {"text": text})

    def discover_roots(self, workspace_path: str):
        return self._send_request(
            "pyforge/discover", {"workspace_path": workspace_path}
        )

    def get_details(self, path: str):
        return self._send_request("pyforge/get_details", {"path": path})

    def deep_inspect(self, path: str):
        return self._send_request("pyforge/deep_inspect", {"path": path})

    def get_all_known_objects(self):
        return self._send_request("pyforge/get_all_known_objects")

    def create_instance(
        self, class_path: str, variable_name: str, args: list, kwargs: dict
    ):
        return self._send_request(
            "pyforge/create_instance",
            {
                "class_path": class_path,
                "variable_name": variable_name,
                "args": args,
                "kwargs": kwargs,
            },
        )

    def set_attribute(self, path: str, new_value_str: str):
        return self._send_request(
            "pyforge/set_attribute", {"path": path, "value": new_value_str}
        )

    def subscribe(self, path: str, is_pinned: bool):
        return self._send_request(
            "pyforge/subscribe", {"path": path, "pinned": is_pinned}
        )

    def unsubscribe(self, path: str):
        return self._send_request("pyforge/unsubscribe", {"path": path})

    def execute_callable(self, path: str, args: list, kwargs: dict):
        return self._send_request(
            "pyforge/execute_callable", {"path": path, "args": args, "kwargs": kwargs}
        )

    def watch_class(self, class_path: str):
        return self._send_request("pyforge/watch_class", {"class_path": class_path})

    def unwatch_class(self, class_path: str):
        return self._send_request("pyforge/unwatch_class", {"class_path": class_path})

    def delete_object(self, path: str):
        return self._send_request("pyforge/delete_object", {"path": path})

    def restore_object(self, object_id: str):
        return self._send_request("pyforge/restore_object", {"id": object_id})

    def hot_reload_module(self, module_name: str, new_source: str):
        return self._send_request(
            "pyforge/hot_reload_module",
            {"module_name": module_name, "new_source": new_source},
        )

    def reload_master_script(self, content: str):
        return self._send_request("pyforge/reload_master_script", {"content": content})

    def validate_master_script(self, content: str):
        return self._send_request(
            "pyforge/validate_master_script", {"content": content}
        )

    def disconnect(self):
        if self.listener_thread:
            self.listener_thread.stop()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self._is_connected = False
