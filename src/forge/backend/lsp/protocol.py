import json
import logging

log = logging.getLogger(__name__)


def encode_message(msg: dict) -> bytes:
    """Encodes a JSON-RPC message with the required LSP headers."""
    content = json.dumps(msg)
    content_length = len(content)

    headers = {
        "Content-Length": content_length,
        "Content-Type": "application/vscode-jsonrpc; charset=utf-8",
    }

    header_str = "\r\n".join(f"{key}: {value}" for key, value in headers.items())

    full_message = f"{header_str}\r\n\r\n{content}"
    return full_message.encode("utf-8")


def decode_message(stream) -> dict:
    """
    Decodes a single JSON-RPC message from a stream.
    Reads headers to determine the content length.
    """
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            raise EOFError("Connection to LSP server lost.")
        if line == b"\r\n":
            break

        header, value = line.decode("utf-8").strip().split(": ")
        headers[header] = int(value)

    content_length = headers["Content-Length"]
    content = stream.read(content_length).decode("utf-8")

    return json.loads(content)
