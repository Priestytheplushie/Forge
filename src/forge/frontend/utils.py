import sys
from pathlib import Path
from urllib.parse import urlparse, unquote


def uri_to_path(uri: str) -> Path:
    """Converts a file URI to a resolved Path object."""
    parsed = urlparse(uri)

    path_str = unquote(parsed.path)
    if sys.platform == "win32" and path_str.startswith("/"):
        path_str = path_str[1:]
    return Path(path_str).resolve()
