import gc
import inspect
import sys
import os
from types import ModuleType
from pathlib import Path


def find(class_name: str) -> list:
    """
    Finds all live instances of a given class name in memory.
    :param class_name: The string name of the class to find (e.g., "Player").
    :return: A list of all found instances.
    """
    found_objects = []
    if not isinstance(class_name, str):
        return found_objects

    for obj in gc.get_objects():
        if obj.__class__.__name__ == class_name:
            found_objects.append(obj)
    return found_objects


def source_of(obj) -> str:
    """Returns the source code of a Python object."""
    try:
        return inspect.getsource(obj)
    except (TypeError, OSError):
        return f"Source code for '{getattr(obj, '__name__', 'object')}' not available."


def doc_of(obj) -> str:
    """Returns the docstring of a Python object."""
    return inspect.getdoc(obj) or "No docstring found."


def get_referrers(obj) -> list:
    """Finds all live objects that refer to the given object."""
    return gc.get_referrers(obj)


def inspect_object(obj) -> dict:
    """
    Provides a detailed inspection of an object's attributes and methods.
    Returns a dictionary with 'attributes' and 'methods'.
    """
    result = {"attributes": {}, "methods": []}
    for name in dir(obj):
        if name.startswith("__"):
            continue
        try:
            value = getattr(obj, name)
            if inspect.ismethod(value) or inspect.isfunction(value):
                try:
                    sig = str(inspect.signature(value))
                    result["methods"].append(f"{name}{sig}")
                except (ValueError, TypeError):
                    result["methods"].append(f"{name}()")
            else:
                result["attributes"][name] = repr(value)
        except Exception:
            pass
    return result


def get_modules() -> list:
    """
    Gets a list of all loaded, user-defined modules.
    Filters out standard library, site-packages, and PyForge agent modules.
    """
    user_modules = []

    stdlib_path = Path(os.path.dirname(os.__file__)).resolve()

    for name, module in sys.modules.items():
        if not isinstance(module, ModuleType) or name == "__main__":
            continue

        file_path_str = getattr(module, "__file__", None)
        if not file_path_str:
            continue

        file_path = Path(file_path_str).resolve()

        if "pyforge" in file_path.parts and "agent" in file_path.parts:
            continue

        try:

            if (
                stdlib_path in file_path.parents
                or "site-packages" in file_path.parts
                or "dist-packages" in file_path.parts
            ):
                continue
        except Exception:
            continue

        user_modules.append({"name": name, "file_path": file_path_str})

    return sorted(user_modules, key=lambda x: x["name"])
