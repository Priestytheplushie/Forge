TOOL_DEFINITION = {
    "id": "pep8_formatter",
    "name": "Format with PEP8",
    "description": "Automatically formats Python code to conform to the PEP8 style guide.",
    "example_before": "def my_func(arg1,arg2):return arg1+arg2\n\nx=1; y=2",
    "example_after": "def my_func(arg1, arg2):\n    return arg1 + arg2\n\n\nx = 1\ny = 2\n",
    "handler_type": "external",
    "command": ["autopep8", "--in-place"],
    "summary": "Formatted Code (PEP8)",
    "scopes": ["file", "directory", "workspace"],
    "category": "Format",
    "order": 22,
}
