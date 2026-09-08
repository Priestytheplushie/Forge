import re
from pathlib import Path


class TracebackDatabase:
    DB = {
        "TypeError": {
            "title": "TypeError: Incompatible Types",
            "explanation": "This error occurs when you try to perform an operation on data of a type that doesn't support it.",
            "example": "For example, you cannot add a number to text (`5 + 'hello'`) or try to loop over a single number (`for i in 10:`).",
        },
        "ModuleNotFoundError": {
            "title": "Module Not Found",
            "explanation": "Python could not find the module you are trying to import. This usually means it's not installed in your current Python environment or there's a typo in the import name.",
            "example": "To fix this, you can often run `pip install [module_name]` in the terminal for the correct environment.",
        },
        "NameError": {
            "title": "Name Error",
            "explanation": "This means you tried to use a variable or function name that hasn't been defined in the current scope yet.",
            "example": "Check for typos (e.g., `prnt` instead of `print`) or make sure you have assigned a value to the variable before using it.",
        },
        "SyntaxError": {
            "title": "Syntax Error",
            "explanation": "Python's parser found a line of code it doesn't understand. This is almost always a typo.",
            "example": "Common causes include a missing colon (`:`), mismatched parentheses `()`, or an invalid keyword.",
        },
        "IndexError": {
            "title": "Index Error",
            "explanation": "You tried to access an item in a list or tuple using an index that is out of bounds (e.g., trying to get the 5th item of a 3-item list).",
            "example": "Remember that list indices start at 0. For a list of length 3, the valid indices are 0, 1, and 2.",
        },
        "KeyError": {
            "title": "Key Error",
            "explanation": "You tried to access a value in a dictionary using a key that does not exist.",
            "example": "You can check if a key exists before using it with `if 'my_key' in my_dict:` or use `my_dict.get('my_key')` to get `None` instead of crashing.",
        },
        "FileNotFoundError": {
            "title": "File Not Found Error",
            "explanation": "The file path you specified does not exist or is incorrect.",
            "example": "Check for typos in the file name or path. Ensure you are running the script from the correct working directory.",
        },
        "AttributeError": {
            "title": "Attribute Error",
            "explanation": "You tried to access a method or property on an object that doesn't have it.",
            "example": "For example, calling `my_list.appendd(5)` (a typo for `append`) or trying to use a list method on a string.",
        },
        "ValueError": {
            "title": "Value Error",
            "explanation": "An operation or function received an argument that has the right type but an inappropriate value.",
            "example": "For example, `int('hello')` raises a ValueError because the string 'hello' cannot be converted to a number.",
        },
        "ZeroDivisionError": {
            "title": "Zero Division Error",
            "explanation": "You tried to divide a number by zero.",
            "example": "Ensure the denominator in a division operation is never zero before performing the calculation.",
        },
    }

    @classmethod
    def query(cls, error_name):
        return cls.DB.get(error_name)


class TracebackHandler:
    def __init__(self):
        self.traceback_pattern = re.compile(
            r'^\s*File "(.+)", line (\d+)(?:, in (.+))?'
        )
        self.error_pattern = re.compile(r"^([a-zA-Z_]\w*Error): (.+)")
        self.current_traceback = None

    def process_line(self, line):
        traceback_match = self.traceback_pattern.match(line)
        error_match = self.error_pattern.match(line.strip())

        if traceback_match:
            if not self.current_traceback:
                self.current_traceback = {
                    "type": "pretty_traceback",
                    "lines": [],
                    "error": None,
                    "raw": "",
                }

            file_path, line_num, context = traceback_match.groups()
            self.current_traceback["lines"].append(
                {
                    "file_path": file_path,
                    "line_num": int(line_num),
                    "context": context or "<module>",
                }
            )
            self.current_traceback["raw"] += line
            return None

        elif error_match and self.current_traceback:
            error_name, error_message = error_match.groups()
            self.current_traceback["error"] = {
                "name": error_name,
                "message": error_message,
            }
            self.current_traceback["raw"] += line

            db_entry = TracebackDatabase.query(error_name)
            if db_entry:
                self.current_traceback["explanation"] = db_entry

            completed_traceback = self.current_traceback
            self.current_traceback = None
            return completed_traceback

        else:
            if self.current_traceback:
                raw_buffer = self.current_traceback["raw"]
                self.current_traceback = None
                return [
                    {"type": "raw", "content": raw_buffer},
                    {"type": "raw", "content": line},
                ]

            return {"type": "raw", "content": line}
