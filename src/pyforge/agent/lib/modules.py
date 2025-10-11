import sys
import importlib
import traceback


def hot_reload_module(module_name: str, new_source: str):
    """
    Attempts to hot-reload a module with new source code.
    :param module_name: The name of the module to reload (e.g., "my_app.player").
    :param new_source: The full new source code for the module.
    :return: A dictionary with the result of the operation.
    """
    if module_name not in sys.modules:
        return {
            "status": "error",
            "payload": f"Module '{module_name}' not found in sys.modules.",
        }

    module = sys.modules[module_name]

    if module_name == "__main__":
        try:

            exec(new_source, module.__dict__)
            return {
                "status": "success",
                "payload": f"Module '{module_name}' was re-executed successfully.",
            }
        except Exception:
            return {
                "status": "error",
                "payload": f"Failed to re-execute __main__:\n\n{traceback.format_exc()}",
            }

    file_path = getattr(module, "__file__", None)
    if not file_path:
        return {
            "status": "error",
            "payload": f"Module '{module_name}' does not have a '__file__' attribute. Cannot hot-reload.",
        }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_source)

        importlib.reload(module)

        return {
            "status": "success",
            "payload": f"Module '{module_name}' reloaded successfully.",
        }

    except Exception as e:
        return {
            "status": "error",
            "payload": f"Failed to reload module '{module_name}':\n\n{traceback.format_exc()}",
        }
