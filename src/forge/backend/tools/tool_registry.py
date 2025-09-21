import os
import importlib
from pathlib import Path


class ToolRegistry:
    """
    A singleton class that discovers and manages available refactoring tools.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance.tools = []
            cls._instance.discover_tools()
        return cls._instance

    def discover_tools(self):
        self.tools = []
        tools_dir = Path(__file__).parent

        for filename in os.listdir(tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = f"forge.backend.tools.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    if hasattr(module, "TOOL_DEFINITION"):
                        self.tools.append(module.TOOL_DEFINITION)
                        print(
                            f"[ToolRegistry] Discovered and loaded tool: {module.TOOL_DEFINITION['id']}"
                        )
                except Exception as e:
                    print(f"[ToolRegistry] Failed to load tool from {filename}: {e}")

        self.tools.sort(key=lambda x: x.get("order", 99))

    def get_tool(self, tool_id: str) -> dict | None:
        """Retrieves a tool's definition by its ID."""
        for tool in self.tools:
            if tool["id"] == tool_id:
                return tool
        return None

    def get_all_tools(self) -> list[dict]:
        """Returns a list of all discovered tool definitions."""
        return self.tools
