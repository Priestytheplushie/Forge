import re

COMMENT_PATTERNS = re.compile(
    r"^\s*#\s*(?:TODO|FIXME|NEW|FIX|NOTE|HACK):.*$", re.MULTILINE | re.IGNORECASE
)


def run_cleanup_on_content(content: str) -> str | None:
    """
    Finds and removes common temporary/scaffolding comments from code content.
    """
    cleaned_content = COMMENT_PATTERNS.sub("", content)
    cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content).strip()

    if cleaned_content != content.strip():
        return cleaned_content + "\n" if content.endswith("\n") else cleaned_content
    return None


TOOL_DEFINITION = {
    "id": "comment_cleanup",
    "name": "Clean Up Comments",
    "description": "Removes common development comments like #TODO, #FIXME, #NOTE, etc., to prepare code for production.",
    "example_before": "def my_func():\n    # TODO: Implement this later\n    return True",
    "example_after": "def my_func():\n    return True\n",
    "handler_type": "programmatic",
    "handler_function": run_cleanup_on_content,
    "summary": "Removed temporary comments",
    "scopes": ["file", "directory", "workspace"],
    "order": 10,
}
