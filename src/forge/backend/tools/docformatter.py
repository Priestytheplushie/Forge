TOOL_DEFINITION = {
    "id": "docformatter",
    "name": "Format Docstrings",
    "description": "Automatically formats docstrings to be compliant with PEP 257.",
    "example_before": 'def my_func():\n    """This is a docstring\n    that is poorly formatted."""\n    pass',
    "example_after": 'def my_func():\n    """This is a docstring that is poorly formatted."""\n    pass\n',
    "handler_type": "external",
    "command": ["docformatter", "--in-place"],
    "summary": "Formatted Docstrings (docformatter)",
    "scopes": ["file", "directory", "workspace"],
    "order": 50,
}
