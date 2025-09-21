TOOL_DEFINITION = {
    "id": "ruff_format",
    "name": "Organize Imports with Ruff",
    "description": "Uses the extremely fast Ruff formatter to sort and organize Python imports.",
    "example_before": "import sys\nimport os\n\nprint(os.getcwd())",
    "example_after": "import os\nimport sys\n\nprint(os.getcwd())\n",
    "handler_type": "external",
    "command": ["ruff", "format"],
    "summary": "Organized Imports (Ruff)",
    "scopes": ["file", "directory", "workspace"],
    "category": "Format",
    "order": 25,
}
