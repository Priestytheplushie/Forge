import threading


class Document:
    """
    A pure Python class representing the in-memory state of a file.
    This is the SINGLE SOURCE OF TRUTH for file content. The UI widget
    is just a view that displays this data.
    """

    def __init__(self, file_path, file_uri):
        self.file_path = file_path
        self.file_uri = file_uri
        self.lines = [""]
        self.version = 1
        self.lock = threading.Lock()

        self.is_dirty = False

    def get_content(self):
        """Returns the full text content. Instantaneous operation."""
        with self.lock:
            return "\n".join(self.lines)

    def set_content(self, content):
        """Sets the entire content of the document, usually on initial load."""
        with self.lock:
            self.lines = content.splitlines()
            if not self.lines:
                self.lines = [""]
            self.version += 1

            self.is_dirty = False

    def apply_change(self, text, start_line, start_col, end_line, end_col):
        """
        Applies a change to the document model. This is the primary method
        for all modifications (insert, delete, paste).
        """
        with self.lock:
            new_lines = []
            new_lines.extend(self.lines[:start_line])

            line_before_change = self.lines[start_line][:start_col]
            line_after_change = self.lines[end_line][end_col:]

            modified_line_content = line_before_change + text
            inserted_lines = modified_line_content.split("\n")

            new_lines.append(inserted_lines[0])
            if len(inserted_lines) > 1:
                new_lines.extend(inserted_lines[1:])

            new_lines[-1] += line_after_change
            new_lines.extend(self.lines[end_line + 1 :])

            self.lines = new_lines
            if not self.lines:
                self.lines = [""]
            self.version += 1

            self.is_dirty = True

    def mark_as_saved(self):
        with self.lock:
            self.is_dirty = False
