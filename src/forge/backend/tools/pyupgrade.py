TOOL_DEFINITION = {
    "id": "pyupgrade",
    "name": "Upgrade Syntax",
    "description": "Automatically upgrades Python syntax to use newer, more modern features.",
    "example_before": "my_dict = dict(a=1, b=2)\nprint('%s %s' % ('a', 'b'))",
    "example_after": 'my_dict = {"a": 1, "b": 2}\nprint(f\'{"a"} {"b"}\')\n',
    "handler_type": "external",
    "command": ["pyupgrade", "--py38-plus"],
    "summary": "Upgraded Syntax (pyupgrade)",
    "scopes": ["file", "directory", "workspace"],
    "category": "Modernize",
    "order": 40,
}
