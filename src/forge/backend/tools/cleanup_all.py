TOOL_DEFINITION = {
    "id": "cleanup",
    "name": "Clean Up and Review",
    "description": "Runs a comprehensive suite of formatters and linters (Ruff, Black, pyupgrade, etc.) to automatically clean up your code.",
    "example_before": "import sys, os # TODO: Fix this later\n\ndef my_func(arg1,arg2):\n    return arg1+arg2",
    "example_after": "import os\nimport sys\n\n\ndef my_func(arg1, arg2):\n    return arg1 + arg2\n",
    "handler_type": "composite",
    "tool_ids": [
        "comment_cleanup",
        "ruff_format",
        "ruff_fix",
        "black",
        "pyupgrade",
        "docformatter",
    ],
    "scopes": ["file", "directory", "workspace"],
    "order": 1,
}
