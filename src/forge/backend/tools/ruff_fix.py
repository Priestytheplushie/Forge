TOOL_DEFINITION = {
    "id": "ruff_fix",
    "name": "Fix Lint Issues with Ruff",
    "description": "Uses the extremely fast Ruff linter to automatically fix common programming errors and code smells.",
    "example_before": "import os\n\ndef my_func():\n    # This function does not use the os module\n    return True",
    "example_after": "def my_func():\n    # This function does not use the os module\n    return True\n",
    "handler_type": "external",
    "command": ["ruff", "check", "--fix", "--unsafe-fixes"],
    "summary": "Fixed Lint Issues (Ruff)",
    "scopes": ["file", "directory", "workspace"],
    "category": "Lint & Fix",
    "order": 30,
}
