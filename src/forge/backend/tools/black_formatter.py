TOOL_DEFINITION = {
    "id": "black",
    "name": "Format with Black",
    "description": "An opinionated code formatter that ensures uniform style by parsing your code and re-printing it.",
    "example_before": "def my_func(arg1,arg2):\n    return arg1+arg2",
    "example_after": "def my_func(arg1, arg2):\n    return arg1 + arg2\n",
    "handler_type": "external",
    "command": ["black"],
    "summary": "Formatted Code (Black)",
    "scopes": ["file", "directory", "workspace"],
    "category": "Format",
    "order": 20,
}
