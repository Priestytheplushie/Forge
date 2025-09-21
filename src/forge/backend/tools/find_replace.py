import re


def run_find_replace_on_content(content: str, **kwargs) -> str | None:
    """
    Performs find and replace on a string of content based on provided parameters.
    """
    find_text = kwargs.get("find_text")
    replace_text = kwargs.get("replace_text")
    case_sensitive = kwargs.get("case_sensitive", False)
    is_regex = kwargs.get("is_regex", False)
    whole_word = kwargs.get("whole_word", False)

    if not find_text:
        return None

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = find_text

    if not is_regex:
        pattern = re.escape(find_text)

    if whole_word and not is_regex:
        pattern = r"\b" + pattern + r"\b"

    try:
        new_content, num_replacements = re.subn(
            pattern, replace_text, content, flags=flags
        )
        if num_replacements > 0:
            return new_content
    except re.error as e:

        print(f"[FindReplace] Regex error: {e}")
        return None

    return None


TOOL_DEFINITION = {
    "id": "find_replace",
    "name": "Find and Replace in Files",
    "description": "Searches for text or regular expressions across multiple files and replaces them, showing all proposed changes in a review session.",
    "handler_type": "programmatic_with_dialog",
    "handler_function": run_find_replace_on_content,
    "summary": "Performed find and replace",
    "scopes": ["directory", "workspace"],
    "order": 5,
}
