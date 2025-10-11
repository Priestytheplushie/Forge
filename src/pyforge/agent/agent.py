import socket
import threading
import traceback
import sys
import json
import gc
import logging
import inspect
import re
import builtins
import os
import time
import importlib
import types
import rlcompleter
import pprint
from .registry import get_scope, register
from pathlib import Path
from .lib import create_pf_object
from functools import wraps

try:
    import psutil
except ImportError:
    psutil = None


def send_message(conn, message: dict):
    """Encodes and sends a JSON-RPC message over a socket."""
    try:
        response_bytes = json.dumps(message).encode("utf-8")
        response_header = f"Content-Length: {len(response_bytes)}\r\n\r\n".encode(
            "utf-8"
        )
        conn.sendall(response_header + response_bytes)
    except (ConnectionResetError, BrokenPipeError):
        pass


def get_params(func):
    """Gets the parameters of a function, handling potential errors."""
    try:
        params = []
        for name, p in inspect.signature(func).parameters.items():
            param_info = {"name": name, "kind": p.kind.name}
            if p.default is not inspect.Parameter.empty:
                param_info["default"] = repr(p.default)
            params.append(param_info)
        return params
    except (ValueError, TypeError):
        return []


def get_object_type(obj):
    """Determines the PyForge object type for a given Python object."""
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        return "function"
    if isinstance(obj, (int, float, str, bool, type(None))):
        return "attribute_simple"
    if isinstance(obj, (dict, list, set, tuple)):
        return "attribute_collection"
    return "instance"


def serialize_result(result):
    """Generic serializer for object browser data."""
    try:
        if result is None:
            return "None"
        result_type = type(result)
        if isinstance(result, (int, float, str, bool, type(None))):
            return repr(result)
        if isinstance(result, (list, tuple)):
            return f"[{', '.join([serialize_result(item) for item in result])}]"
        if isinstance(result, dict):
            return f"{{{', '.join([f'{k_repr}:{v_repr}' for k_repr, v_repr in ((serialize_result(k), serialize_result(v)) for k, v in result.items())])}}}"
        return {
            "id": id(result),
            "type": result_type.__name__,
            "repr": repr(result),
            "module": result_type.__module__,
        }
    except Exception:
        return f"<Object of type '{type(result).__name__}' id={id(result)}>"


def watch_class_legacy(cls, conn, watched_classes):
    class_path = f"{cls.__module__}.{cls.__name__}"
    if hasattr(cls, "__original_new__"):
        return True
    cls.__original_new__ = cls.__new__
    is_base_new = cls.__original_new__ is object.__new__

    def new_wrapper(wrapped_cls, *args, **kwargs):
        if is_base_new:
            instance = wrapped_cls.__original_new__(wrapped_cls)
        else:
            instance = wrapped_cls.__original_new__(wrapped_cls, *args, **kwargs)

        if "on_new_instance" in master_script_hooks:
            try:
                master_script_hooks["on_new_instance"](instance, class_path)
            except Exception as e:
                log.error(f"Error in 'on_new_instance' master script hook: {e}")

        notification = {
            "jsonrpc": "2.0",
            "method": "pyforge/new_instance",
            "params": {
                "class_path": class_path,
                "instance": serialize_result(instance),
            },
        }
        send_message(conn, notification)
        return instance

    try:
        cls.__new__ = new_wrapper
        watched_classes[class_path] = {"conn": conn}
        return True
    except (TypeError, AttributeError):
        cls.__new__ = cls.__original_new__
        delattr(cls, "__original_new__")
        return False


class SocketLogHandler(logging.Handler):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def emit(self, record):
        log_entry = self.format(record)
        log_notification = {
            "jsonrpc": "2.0",
            "method": "pyforge/log",
            "params": {"message": log_entry},
        }
        send_message(self.conn, log_notification)


log = logging.getLogger("PyForgeAgent")
log.setLevel(logging.INFO)
log.propagate = False

HOST = "127.0.0.1"
PORT = 65432

subscriptions = {}
last_known_state = {}
heartbeat_thread = None
heartbeat_running = False
watched_classes = {}
trash = {}
custom_metrics = {}
process_handle = None


master_script_hooks = {
    "on_tick": lambda: None,
    "on_event": lambda name, value: None,
    "on_new_instance": lambda instance, class_name: None,
    "on_agent_connect": lambda: None,
    "on_agent_disconnect": lambda: None,
    "on_script_start": lambda: None,
    "on_script_end": lambda: None,
    "on_exception": lambda exc, tb_dict: None,
    "metric_functions": [],
    "override_functions": [],
}
original_functions = {}

IS_PYTHON_312_OR_NEWER = sys.version_info >= (3, 12)


def track_metric(name: str, value):
    """Stores a custom metric from the user's application."""
    custom_metrics[name] = value


def run_script(script_path: str, context: dict = None):
    """Executes a PyForge script file."""
    full_path = Path(os.getcwd()) / script_path
    if not full_path.exists():
        log.error(f"pf.run_script: Script not found at '{full_path}'")
        return

    try:
        script_content = full_path.read_text(encoding="utf-8")
        scope = {"context": context or {}}
        exec(script_content, scope)
    except Exception:
        log.error(f"Error executing script '{script_path}':\n{traceback.format_exc()}")


def _validate_master_script(content: str):
    """Compiles and validates the structure of a master script."""
    checks = []
    try:
        checks.append(
            {
                "name": "File Readability",
                "description": "Ensures the script content is valid text.",
                "status": "success",
            }
        )

        compile(content, "master.pfscript", "exec")
        checks.append(
            {
                "name": "Valid Python Syntax",
                "description": "Checks if the script is a valid Python file.",
                "status": "success",
            }
        )
    except SyntaxError as e:
        checks.append(
            {
                "name": "Valid Python Syntax",
                "description": "Checks if the script is a valid Python file.",
                "status": "error",
                "error": f"Line {e.lineno}: {e.msg}",
            }
        )
        return {"status": "error", "error": "Syntax error in script.", "checks": checks}

    temp_scope = {}
    exec(content, temp_scope)

    hook_signatures = {
        "on_tick": 0,
        "on_event": 2,
        "on_new_instance": 2,
        "on_agent_connect": 0,
        "on_agent_disconnect": 0,
        "on_script_start": 0,
        "on_script_end": 0,
        "on_exception": 2,
    }
    for name, expected_args in hook_signatures.items():
        if name in temp_scope and inspect.isfunction(temp_scope[name]):
            sig = inspect.signature(temp_scope[name])
            if len(sig.parameters) != expected_args:
                checks.append(
                    {
                        "name": f"Hook '{name}' Signature",
                        "status": "error",
                        "error": f"Expected {expected_args} args, found {len(sig.parameters)}.",
                    }
                )

    metric_names = set()
    for item in temp_scope.values():
        if hasattr(item, "_is_pf_metric"):
            name = item._pf_metric_name
            if name in metric_names:
                checks.append(
                    {
                        "name": f"Metric '{name}' Name",
                        "status": "error",
                        "error": "Duplicate metric name.",
                    }
                )
            else:
                metric_names.add(name)

    if all(c["status"] != "error" for c in checks):
        return {"status": "success", "checks": checks}
    else:
        return {
            "status": "error",
            "error": "One or more validation checks failed.",
            "checks": checks,
        }


def _reload_master_script(content: str):
    """Hot-reloads the master script hooks, metrics, and overrides."""
    global master_script_hooks, original_functions

    for target_str, original_func in original_functions.items():
        try:
            module_name, func_name = target_str.rsplit(".", 1)
            if module_name == "agent":
                setattr(sys.modules[__name__], func_name, original_func)
        except Exception as e:
            log.error(f"Error restoring override for '{target_str}': {e}")
    original_functions.clear()

    validation = _validate_master_script(content)
    if validation["status"] == "error":
        log.error(f"Failed to reload master script: {validation['error']}")
        return validation

    try:
        temp_scope = {}
        exec(content, temp_scope)

        for hook_name in master_script_hooks:
            if hook_name not in ["metric_functions", "override_functions"]:
                master_script_hooks[hook_name] = temp_scope.get(
                    hook_name, lambda *args, **kwargs: None
                )

        master_script_hooks["metric_functions"] = [
            f for f in temp_scope.values() if hasattr(f, "_is_pf_metric")
        ]

        override_functions = [
            f for f in temp_scope.values() if hasattr(f, "_is_pf_override")
        ]
        for func in override_functions:
            target_str = func._pf_override_target
            try:
                module_name, func_name = target_str.rsplit(".", 1)
                if module_name == "agent":
                    module = sys.modules[__name__]
                    original_func = getattr(module, func_name)
                    original_functions[target_str] = original_func

                    @wraps(func)
                    def override_wrapper(*args, **kwargs):
                        return func(original_func, *args, **kwargs)

                    setattr(module, func_name, override_wrapper)
                    log.info(f"Successfully applied override for '{target_str}'.")
            except Exception as e:
                log.error(f"Failed to apply override for '{target_str}': {e}")

        log.info("Master script reloaded successfully.")

        metric_definitions = []
        for func in master_script_hooks["metric_functions"]:
            metric_definitions.append(
                {
                    "name": func._pf_metric_name,
                    "type": func._pf_metric_type,
                    "unit": func._pf_metric_unit,
                }
            )
        return {
            "status": "success",
            "payload": {"metric_definitions": metric_definitions},
        }

    except Exception:
        return {"status": "error", "payload": _format_traceback()}


def _resolve_path(path, scope):
    try:
        path_type, _, path_data = path.partition(":")

        if path_type in ["global", "builtin"]:
            return eval(path_data, scope)

        if path_type in ["class", "function", "module"]:
            if not path_data:
                raise ValueError("Empty module name")
            module_name, _, object_name = path_data.rpartition(".")
            if not object_name:
                return importlib.import_module(path_data)

            module = importlib.import_module(module_name)
            return getattr(module, object_name)
        elif path_type == "instance":
            return get_scope().get(path_data)
        elif path_type == "attribute":
            obj_id_str, _, attr_name = path_data.partition(".")
            instance = get_scope().get(obj_id_str)
            if instance is None:
                raise NameError(f"Instance with ID {obj_id_str} not found.")
            return getattr(instance, attr_name)
        else:
            return eval(path_data, scope)
    except (ModuleNotFoundError, AttributeError, NameError, ValueError) as e:
        log.error(f"Could not resolve path '{path}': {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error resolving path '{path}': {e}")
        raise


def _format_traceback():
    exc_type, exc_value, exc_tb = sys.exc_info()
    if exc_type is None:
        return {
            "type": "traceback",
            "error_type": "InternalError",
            "error_message": "No exception info available to format.",
            "frames": [],
        }
    frames = []
    for frame in traceback.extract_tb(exc_tb):
        frames.append(
            {"file": frame.filename, "line": frame.lineno, "function": frame.name}
        )
    return {
        "type": "traceback",
        "error_type": exc_type.__name__,
        "error_message": str(exc_value),
        "frames": frames,
    }


def _serialize_for_console(result):
    if result is None:
        return {"type": "none"}

    result_type = type(result)

    if isinstance(result, (int, float, bool, str)):
        return {
            "type": "primitive",
            "kind": result_type.__name__.lower(),
            "value": repr(result),
        }

    if isinstance(result, (list, tuple, set, dict)):
        preview = pprint.pformat(result, indent=2, width=80, depth=2)
        if len(preview) > 200:
            preview = preview[:200] + "..."
        obj_id = id(result)
        register(str(obj_id), result)
        return {"type": "collection", "preview": preview, "path": f"instance:{obj_id}"}

    obj_id = id(result)
    register(str(obj_id), result)
    return {"type": "instance", "repr": repr(result), "path": f"instance:{obj_id}"}


def _find_and_register_object_by_name(name: str):
    """
    Finds an object by its variable name in various scopes.
    If found, registers it by its ID and returns the object.
    Returns None if not found.
    """

    def do_register(obj):
        register(str(id(obj)), obj)
        return obj

    if hasattr(builtins, name):
        return do_register(getattr(builtins, name))

    main_module = sys.modules.get("__main__")
    if main_module and hasattr(main_module, name):
        return do_register(getattr(main_module, name))

    for module_name, module in sys.modules.items():
        if hasattr(module, name):
            return do_register(getattr(module, name))

    for thread_id, frame in sys._current_frames().items():
        current_frame = frame
        while current_frame:
            if name in current_frame.f_locals:
                return do_register(current_frame.f_locals[name])
            if name in current_frame.f_globals:
                return do_register(current_frame.f_globals[name])
            current_frame = current_frame.f_back

    return None


def _discover_roots(workspace_path_str: str):
    roots = []
    roots.append(
        {
            "name": "[Globals & Builtins]",
            "type": "special_group",
            "path": "special:globals",
            "expandable": True,
        }
    )
    roots.append(
        {
            "name": "[All Live Instances]",
            "type": "special_group",
            "path": "special:instances",
            "expandable": True,
        }
    )

    workspace_path = Path(workspace_path_str) if workspace_path_str else None
    user_modules = {}

    for name, mod in sys.modules.items():
        if name == "__main__":
            user_modules[name] = mod
            continue

        file_path_str = getattr(mod, "__file__", None)
        if not file_path_str:
            continue

        if "pyforge" in file_path_str.replace("\\", "/"):
            continue

        if workspace_path:
            try:
                if workspace_path in Path(file_path_str).parents:
                    user_modules[name] = mod
            except (TypeError, ValueError):
                continue

    for name, mod in sorted(user_modules.items()):
        file_path = getattr(mod, "__file__", name)
        roots.append(
            {
                "name": os.path.basename(file_path),
                "type": "module",
                "path": f"module:{name}",
                "expandable": True,
                "file_path": file_path,
            }
        )
    return roots


def _get_details(path: str):
    children = []
    path_type, _, path_data = path.partition(":")
    scope = get_scope()

    if path_type == "attribute":
        try:
            obj_to_inspect = _resolve_path(path, scope)
            if isinstance(obj_to_inspect, (list, tuple)):
                for i, item in enumerate(obj_to_inspect):
                    item_repr = repr(item)
                    if len(item_repr) > 100:
                        item_repr = item_repr[:100] + "..."
                    obj_type = get_object_type(item)
                    item_id = id(item)
                    register(str(item_id), item)
                    children.append(
                        {
                            "name": f"[{i}]",
                            "type": obj_type,
                            "path": f"instance:{item_id}",
                            "value": item_repr,
                            "expandable": obj_type
                            not in ["attribute_simple", "attribute_collection"],
                        }
                    )
            elif isinstance(obj_to_inspect, dict):
                for key, value in obj_to_inspect.items():
                    value_repr = repr(value)
                    if len(value_repr) > 100:
                        value_repr = value_repr[:100] + "..."
                    obj_type = get_object_type(value)
                    item_id = id(value)
                    register(str(item_id), value)
                    children.append(
                        {
                            "name": f"{repr(key)}",
                            "type": obj_type,
                            "path": f"instance:{item_id}",
                            "value": value_repr,
                            "expandable": obj_type
                            not in ["attribute_simple", "attribute_collection"],
                        }
                    )
        except Exception:
            pass
    elif path_type == "special" and path_data == "globals":
        children.append(
            {
                "name": "[Globals]",
                "type": "globals_group",
                "path": "special:globals_list",
                "expandable": True,
            }
        )
        children.append(
            {
                "name": "[Builtins]",
                "type": "builtins_group",
                "path": "special:builtins_list",
                "expandable": True,
            }
        )
    elif path_type == "special" and path_data == "globals_list":
        main_mod = sys.modules.get("__main__")
        if main_mod:
            categorized = {
                "Modules": [],
                "Classes": [],
                "Functions": [],
                "Variables": [],
            }
            for name, value in main_mod.__dict__.items():
                if not name.startswith("__"):
                    obj_type = get_object_type(value)
                    item_data = {
                        "name": name,
                        "type": obj_type,
                        "path": f"global:{name}",
                        "value": repr(value),
                        "expandable": obj_type != "attribute_simple",
                    }
                    if obj_type == "module":
                        categorized["Modules"].append(item_data)
                    elif obj_type == "class":
                        categorized["Classes"].append(item_data)
                    elif obj_type == "function":
                        categorized["Functions"].append(item_data)
                    else:
                        categorized["Variables"].append(item_data)
            for category, items in categorized.items():
                if items:
                    children.append(
                        {
                            "name": f"[{category}]",
                            "type": "globals_group",
                            "path": f"category:{category}",
                            "expandable": True,
                            "children": items,
                        }
                    )
    elif path_type == "special" and path_data == "builtins_list":
        for name, value in builtins.__dict__.items():
            if not name.startswith("_") and not name[0].isupper():
                obj_type = get_object_type(value)
                children.append(
                    {
                        "name": name,
                        "type": obj_type,
                        "path": f"builtin:{name}",
                        "value": repr(value),
                        "expandable": False,
                    }
                )
    elif path_type == "category":
        return path_data
    elif path_type == "special" and path_data == "instances":
        instances_by_type = {}
        for obj in gc.get_objects():
            if hasattr(obj, "__class__"):
                module_name = obj.__class__.__module__
                if module_name == "builtins" or "site-packages" in getattr(
                    sys.modules.get(module_name, {}), "__file__", ""
                ):
                    continue
                type_name = f"{module_name}.{obj.__class__.__name__}"
                if type_name not in instances_by_type:
                    instances_by_type[type_name] = []
                instances_by_type[type_name].append(obj)
        for type_name, instances in sorted(instances_by_type.items()):
            children.append(
                {
                    "name": f"{type_name} ({len(instances)})",
                    "type": "instance_group",
                    "path": f"instance_group:{type_name}",
                    "expandable": True,
                }
            )
    elif path_type == "module":
        mod = sys.modules.get(path_data)
        if mod:
            children.append(
                {
                    "name": "[Imports]",
                    "type": "imports_group",
                    "path": f"imports_group:{path_data}",
                    "expandable": True,
                }
            )
            children.append(
                {
                    "name": "[Globals]",
                    "type": "globals_group",
                    "path": f"globals_group:{path_data}",
                    "expandable": True,
                }
            )
            children.append(
                {
                    "name": "[Classes]",
                    "type": "class_group",
                    "path": f"class_group:{path_data}",
                    "expandable": True,
                }
            )
            children.append(
                {
                    "name": "[Functions]",
                    "type": "function_group",
                    "path": f"function_group:{path_data}",
                    "expandable": True,
                }
            )
    elif path_type == "imports_group" or path_type == "globals_group":
        mod = sys.modules.get(path_data)
        if mod:
            for name, value in mod.__dict__.items():
                if name.startswith("__"):
                    continue
                is_import = inspect.ismodule(value)
                obj_type = get_object_type(value)
                is_global_var = obj_type not in ["module", "class", "function"]
                if path_type == "imports_group" and is_import:
                    children.append(
                        {
                            "name": name,
                            "type": "module",
                            "path": f"global:{name}",
                            "value": repr(value),
                            "expandable": True,
                        }
                    )
                elif path_type == "globals_group" and is_global_var:
                    children.append(
                        {
                            "name": name,
                            "type": obj_type,
                            "path": f"global:{name}",
                            "value": repr(value),
                            "expandable": obj_type != "attribute_simple",
                        }
                    )
    elif path_type == "class_group":
        mod = sys.modules.get(path_data)
        if mod:
            for name, obj in sorted(inspect.getmembers(mod, inspect.isclass)):
                if obj.__module__ == mod.__name__:
                    children.append(
                        {
                            "name": name,
                            "type": "class",
                            "path": f"class:{path_data}.{name}",
                            "expandable": True,
                        }
                    )
    elif path_type == "function_group":
        mod = sys.modules.get(path_data)
        if mod:
            for name, obj in sorted(inspect.getmembers(mod, inspect.isfunction)):
                if obj.__module__ == mod.__name__:
                    sig = str(inspect.signature(obj))
                    display_name = f"{name}{sig}" if len(sig) < 50 else f"{name}(...)"
                    children.append(
                        {
                            "name": display_name,
                            "type": "function",
                            "path": f"function:{path_data}.{name}",
                            "expandable": True,
                            "params": get_params(obj),
                            "doc": inspect.getdoc(obj) or "",
                        }
                    )
    elif path_type == "class":
        cls = _resolve_path(f"class:{path_data}", scope)
        doc = inspect.getdoc(cls) or ""
        children.append(
            {
                "name": "[Class Attributes]",
                "type": "class_attribute_group",
                "path": f"class_attribute_group:{path_data}",
                "expandable": True,
                "doc": doc,
            }
        )
        children.append(
            {
                "name": "[Live Instances]",
                "type": "instance_group_for_class",
                "path": f"instance_group_for_class:{path_data}",
                "expandable": True,
            }
        )
        children.append(
            {
                "name": "[Methods]",
                "type": "method_group",
                "path": f"method_group:{path_data}",
                "expandable": True,
            }
        )
    elif path_type == "class_attribute_group":
        module_name, class_name = path_data.rsplit(".", 1)
        mod = sys.modules.get(module_name)
        if mod:
            cls = getattr(mod, class_name, None)
            if cls:
                for name, value in cls.__dict__.items():
                    if not name.startswith("__") and not isinstance(
                        value,
                        (
                            types.FunctionType,
                            types.MethodType,
                            classmethod,
                            staticmethod,
                        ),
                    ):
                        obj_type = get_object_type(value)
                        children.append(
                            {
                                "name": name,
                                "type": obj_type,
                                "path": f"class_attribute:{path_data}.{name}",
                                "value": repr(value),
                                "expandable": obj_type != "attribute_simple",
                            }
                        )
    elif path_type == "instance_group_for_class" or path_type == "instance_group":
        full_type_name = path_data
        module_name, _, class_name = full_type_name.rpartition(".")
        main_mod = sys.modules.get("__main__")

        for obj in gc.get_objects():
            if (
                obj.__class__.__name__ == class_name
                and obj.__class__.__module__ == module_name
            ):
                obj_id = id(obj)
                var_name = next(
                    (
                        name
                        for name, val in (main_mod.__dict__ if main_mod else {}).items()
                        if val is obj
                    ),
                    None,
                )
                display_name = (
                    f"{var_name} ({class_name} @ {hex(obj_id)})"
                    if var_name
                    else f"{class_name} @ {hex(obj_id)}"
                )
                children.append(
                    {
                        "name": display_name,
                        "type": "instance",
                        "path": f"instance:{obj_id}",
                        "expandable": True,
                    }
                )
                register(str(obj_id), obj)
    elif path_type == "instance":
        obj_id = int(path_data)
        if str(obj_id) in get_scope():
            children.append(
                {
                    "name": "[Attributes]",
                    "type": "attribute_group",
                    "path": f"attribute_group:{obj_id}",
                    "expandable": True,
                }
            )
            children.append(
                {
                    "name": "[Methods]",
                    "type": "method_group_for_instance",
                    "path": f"method_group_for_instance:{obj_id}",
                    "expandable": True,
                }
            )
    elif path_type == "attribute_group":
        obj_id = int(path_data)
        obj = get_scope().get(str(obj_id))
        if obj:
            for name in dir(obj):
                if not name.startswith("__"):
                    try:
                        value = getattr(obj, name)
                        if not inspect.ismethod(value) and not inspect.isfunction(
                            value
                        ):
                            value_repr = repr(value)
                            if len(value_repr) > 100:
                                value_repr = value_repr[:100] + "..."
                            obj_type = get_object_type(value)

                            is_expandable = obj_type not in [
                                "attribute_simple",
                                "attribute_collection",
                            ]
                            path = f"attribute:{obj_id}.{name}"
                            if obj_type == "instance":
                                register(str(id(value)), value)
                                path = f"instance:{id(value)}"

                            children.append(
                                {
                                    "name": name,
                                    "type": obj_type,
                                    "path": path,
                                    "value": value_repr,
                                    "expandable": is_expandable,
                                }
                            )
                    except:
                        pass
    elif path_type == "method_group" or path_type == "method_group_for_instance":
        target = None
        if path_type == "method_group":
            target = _resolve_path(f"class:{path_data}", scope)
        else:
            obj_id = int(path_data)
            target = get_scope().get(str(obj_id))

        if target:
            predicate = (
                inspect.ismethod
                if path_type == "method_group_for_instance"
                else inspect.isfunction
            )
            for name, func in sorted(inspect.getmembers(target, predicate)):
                if (
                    name.startswith("__") and name.endswith("__")
                ) and name != "__init__":
                    continue
                try:
                    sig = str(inspect.signature(func))
                    display_name = f"{name}{sig}" if len(sig) < 50 else f"{name}(...)"
                    children.append(
                        {
                            "name": display_name,
                            "type": "function",
                            "path": f"method:{path_data}.{name}",
                            "expandable": False,
                            "params": get_params(func),
                            "doc": inspect.getdoc(func) or "",
                        }
                    )
                except (ValueError, TypeError):
                    children.append(
                        {
                            "name": f"{name}()",
                            "type": "function",
                            "path": f"method:{path_data}.{name}",
                            "expandable": False,
                            "params": [],
                            "doc": inspect.getdoc(func) or "",
                        }
                    )
    return children


def deep_inspect(path: str):
    scope = get_scope()
    try:
        obj = _resolve_path(path, scope)
    except Exception as e:
        return {"error": f"Could not resolve path '{path}': {e}"}

    root = {"name": "Inspection Root", "expandable": True, "children": []}

    basic_info = {"name": "[Basic Info]", "expandable": True, "children": []}
    basic_info["children"].append({"name": "Repr", "value": repr(obj)})
    try:
        basic_info["children"].append(
            {
                "name": "Type",
                "value": f"{obj.__class__.__module__}.{obj.__class__.__name__}",
            }
        )
    except:
        basic_info["children"].append({"name": "Type", "value": str(type(obj))})
    basic_info["children"].append({"name": "ID (hex)", "value": hex(id(obj))})
    try:
        basic_info["children"].append(
            {
                "name": "Source File",
                "value": inspect.getsourcefile(obj) or "Not available",
            }
        )
    except TypeError:
        basic_info["children"].append({"name": "Source File", "value": "Not available"})
    root["children"].append(basic_info)

    doc = inspect.getdoc(obj)
    if doc:
        root["children"].append(
            {"name": "[Docstring]", "expandable": True, "children": [{"name": doc}]}
        )

    if hasattr(obj, "__class__"):
        mro_info = {"name": "[Class Hierarchy]", "expandable": True, "children": []}
        try:
            for cls in inspect.getmro(obj.__class__):
                mro_info["children"].append(
                    {"name": f"{cls.__module__}.{cls.__name__}"}
                )
            root["children"].append(mro_info)
        except:
            pass

    attr_info = {"name": "[Attributes]", "expandable": True, "children": []}
    if hasattr(obj, "__dict__"):
        for name, value in obj.__dict__.items():
            attr_info["children"].append({"name": name, "value": repr(value)})
    elif hasattr(obj, "__slots__"):
        for name in obj.__slots__:
            try:
                value = getattr(obj, name)
                attr_info["children"].append({"name": name, "value": repr(value)})
            except:
                attr_info["children"].append(
                    {"name": name, "value": "<error reading slot>"}
                )

    for name in dir(obj):
        if name.startswith("__") or hasattr(obj.__dict__ or {}, name):
            continue
        try:
            value = getattr(obj, name)
            if not inspect.ismethod(value) and not inspect.isfunction(value):
                attr_info["children"].append({"name": name, "value": repr(value)})
        except:
            pass
    if attr_info["children"]:
        root["children"].append(attr_info)

    method_info = {"name": "[Methods]", "expandable": True, "children": []}
    for name, value in inspect.getmembers(
        obj, lambda m: inspect.ismethod(m) or inspect.isfunction(m)
    ):
        if name.startswith("__") and name != "__init__":
            continue
        try:
            sig = str(inspect.signature(value))
        except (ValueError, TypeError):
            sig = "()"
        method_info["children"].append({"name": f"{name}{sig}"})
    if method_info["children"]:
        root["children"].append(method_info)

    return root


def _get_all_known_objects():
    objects_by_type = {}

    for obj in gc.get_objects():
        if hasattr(obj, "__class__"):
            module_name = obj.__class__.__module__
            if module_name == "builtins" or "site-packages" in getattr(
                sys.modules.get(module_name, {}), "__file__", ""
            ):
                continue

            type_name = f"{module_name}.{obj.__class__.__name__}"
            if type_name not in objects_by_type:
                objects_by_type[type_name] = []

            obj_id = str(id(obj))
            register(obj_id, obj)

            obj_name = next(
                (
                    name
                    for name, val in sys.modules["__main__"].__dict__.items()
                    if val is obj
                ),
                f"{obj.__class__.__name__}_at_{hex(id(obj))}",
            )

            objects_by_type[type_name].append(
                {"name": obj_name, "type": "instance", "path": f"pf:instance:{obj_id}"}
            )

    for type_name in objects_by_type:
        objects_by_type[type_name].sort(key=lambda x: x["name"])

    return objects_by_type


def _heartbeat_loop(conn):
    global heartbeat_running

    while heartbeat_running:
        try:
            if master_script_hooks["on_tick"]:
                master_script_hooks["on_tick"]()
        except Exception as e:
            log.error(f"Error in 'on_tick' master script hook: {e}")

        temp_custom_metrics = custom_metrics.copy()
        for func in master_script_hooks.get("metric_functions", []):
            try:
                metric_name = func._pf_metric_name
                value = func()
                temp_custom_metrics[metric_name] = value
            except Exception as e:
                log.error(f"Error executing metric function '{func.__name__}': {e}")

        metrics = {
            "custom_metrics": temp_custom_metrics,
            "gc_stats": {
                "counts": gc.get_count(),
                "objects": len(gc.get_objects()),
                "garbage": len(gc.garbage),
            },
            "last_known_state": last_known_state,
        }

        status_update_notification = {
            "jsonrpc": "2.0",
            "method": "pyforge/statusUpdate",
            "params": metrics,
        }
        send_message(conn, status_update_notification)

        if subscriptions:
            try:
                for path, sub_data in list(subscriptions.items()):
                    obj_id_str = path.split(":")[-1]
                    obj = get_scope().get(obj_id_str)
                    if obj is None or not gc.is_tracked(obj):
                        update = {"type": "delete", "path": path}
                        send_message(
                            conn,
                            {
                                "jsonrpc": "2.0",
                                "method": "pyforge/subscription_update",
                                "params": update,
                            },
                        )
                        last_known_state.pop(path, None)
                        if not sub_data["pinned"]:
                            subscriptions.pop(path, None)
                        continue
                    current_attrs = {}
                    for name in dir(obj):
                        if not name.startswith("__"):
                            try:
                                value = getattr(obj, name)
                                if not inspect.ismethod(
                                    value
                                ) and not inspect.isfunction(value):
                                    current_attrs[name] = repr(value)
                            except:
                                pass
                    if last_known_state.get(path) != current_attrs:
                        for name, value_repr in current_attrs.items():
                            if last_known_state.get(path, {}).get(name) != value_repr:
                                attr_path = f"attribute:{obj_id_str}.{name}"
                                update = {
                                    "type": "update",
                                    "path": attr_path,
                                    "new_value": value_repr,
                                }
                                send_message(
                                    conn,
                                    {
                                        "jsonrpc": "2.0",
                                        "method": "pyforge/subscription_update",
                                        "params": update,
                                    },
                                )
                        last_known_state[path] = current_attrs
            except Exception as e:
                log.error(f"Error in heartbeat subscriptions: {e}")

        time.sleep(2)
    heartbeat_running = False


def _handle_client(conn, connection_event: threading.Event):
    global heartbeat_thread, heartbeat_running, watched_classes
    socket_handler = SocketLogHandler(conn)
    log.addHandler(socket_handler)

    try:
        agent_instance = types.SimpleNamespace()
        agent_instance.scope = {}
        agent_instance.scope.update(builtins.__dict__)
        agent_instance.conn = conn
        agent_instance.trash = trash
        agent_instance.find_and_register = _find_and_register_object_by_name

        completer = rlcompleter.Completer(agent_instance.scope)

        def watch_closure(cls):
            return watch_class_legacy(cls, conn, watched_classes)

        pf_object = create_pf_object(agent_instance, serialize_result, watch_closure)

        pf_object.track = track_metric
        pf_object.run_script = run_script

        def fire_event(name: str, value: any = None):
            if "on_event" in master_script_hooks:
                try:
                    master_script_hooks["on_event"](name, value)
                except Exception as e:
                    log.error(f"Error in 'on_event' master script hook: {e}")

        pf_object.fire_event = fire_event

        def metric_decorator_factory(name: str, type: str = "value", unit: str = ""):
            def decorator(func):
                func._is_pf_metric = True
                func._pf_metric_name = name
                func._pf_metric_type = type
                func._pf_metric_unit = unit
                return func

            return decorator

        pf_object.metric = metric_decorator_factory

        def override_decorator_factory(target: str):
            def decorator(func):
                func._is_pf_override = True
                func._pf_override_target = target
                return func

            return decorator

        pf_object.override = override_decorator_factory

        pf_object._reload_master_script = _reload_master_script
        pf_object._validate_master_script = _validate_master_script

        builtins.pf = pf_object
        sys.modules["pf"] = pf_object
        agent_instance.scope["pf"] = pf_object

        log.info("UI Client connected.")
        if "on_agent_connect" in master_script_hooks:
            master_script_hooks["on_agent_connect"]()

        session_info = {
            "jsonrpc": "2.0",
            "method": "pyforge/sessionInfo",
            "params": {"pid": os.getpid()},
        }
        send_message(conn, session_info)

        connection_event.set()

        buffer = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break

            buffer += data
            while b"\r\n\r\n" in buffer:
                header_part, _, body_part = buffer.partition(b"\r\n\r\n")
                headers = dict(line.split(b": ") for line in header_part.split(b"\r\n"))
                content_length = int(headers[b"Content-Length"])

                if len(body_part) < content_length:
                    break

                body_json = body_part[:content_length].decode("utf-8")
                buffer = body_part[content_length:]

                request = json.loads(body_json)
                req_id, method, params = (
                    request.get("id"),
                    request.get("method"),
                    request.get("params", {}),
                )

                response_payload = {}
                if method == "pyforge/execute" or method == "pyforge/execute_script":
                    is_script = method == "pyforge/execute_script"
                    code = params.get("script" if is_script else "command", "")
                    response_payload = pf_object.execute_code(
                        code, is_script=is_script, serializer=_serialize_for_console
                    )
                elif method == "pyforge/set_attribute":
                    try:
                        path = params.get("path")
                        value_str = params.get("value")
                        path_type, _, path_data = path.partition(":")
                        obj_id_str, _, attr_name = path_data.partition(".")

                        try:
                            evaluated_value = eval(value_str, {}, {})
                            final_value_repr = repr(evaluated_value)
                        except (NameError, SyntaxError):
                            final_value_repr = repr(value_str)

                        code = f"setattr(pf.get('{obj_id_str}'), '{attr_name}', {final_value_repr})"
                        exec(code, agent_instance.scope)

                        new_value = _resolve_path(path, agent_instance.scope)
                        response_payload = {
                            "status": "success",
                            "new_value": repr(new_value),
                        }
                    except Exception as e:
                        response_payload = {
                            "status": "error",
                            "payload": _format_traceback(),
                        }
                elif method == "pyforge/reload_master_script":
                    response_payload = _reload_master_script(params.get("content", ""))
                elif method == "pyforge/validate_master_script":
                    response_payload = _validate_master_script(
                        params.get("content", "")
                    )
                elif method == "pyforge/get_completions":
                    text = params.get("text", "")
                    completions = []
                    i = 0
                    while True:
                        comp = completer.complete(text, i)
                        if comp is None:
                            break
                        completions.append(comp)
                        i += 1
                    response_payload = completions
                elif method == "pyforge/hot_reload_module":
                    response_payload = pf_object._hot_reload(
                        params.get("module_name"), params.get("new_source")
                    )
                elif method == "pyforge/discover":
                    response_payload = _discover_roots(params.get("workspace_path"))
                elif method == "pyforge/get_details":
                    response_payload = _get_details(params.get("path"))
                elif method == "pyforge/deep_inspect":
                    response_payload = deep_inspect(params.get("path"))
                elif method == "pyforge/get_all_known_objects":
                    response_payload = _get_all_known_objects()
                elif method == "pyforge/create_instance":
                    try:
                        class_path_full = params.get("class_path")
                        variable_name = params.get("variable_name")
                        args = params.get("args", [])
                        kwargs = params.get("kwargs", {})

                        class_obj = _resolve_path(class_path_full, agent_instance.scope)

                        evaluated_args = []
                        for arg in args:
                            if isinstance(arg, str) and arg.startswith("pf:instance:"):
                                obj_id = arg.split(":")[-1]
                                evaluated_args.append(get_scope().get(obj_id))
                            else:
                                evaluated_args.append(eval(arg, agent_instance.scope))

                        evaluated_kwargs = {}
                        for k, v in kwargs.items():
                            if isinstance(v, str) and v.startswith("pf:instance:"):
                                obj_id = v.split(":")[-1]
                                evaluated_kwargs[k] = get_scope().get(obj_id)
                            else:
                                evaluated_kwargs[k] = eval(v, agent_instance.scope)

                        new_instance = class_obj(*evaluated_args, **evaluated_kwargs)

                        if variable_name:
                            main_mod = sys.modules.get("__main__")
                            if main_mod:
                                setattr(main_mod, variable_name, new_instance)

                        response_payload = {
                            "status": "success",
                            "payload": serialize_result(new_instance),
                        }
                    except Exception:
                        response_payload = {
                            "status": "error",
                            "payload": traceback.format_exc(),
                        }
                elif method == "pyforge/subscribe":
                    path = params.get("path")
                    subscriptions[path] = {"pinned": params.get("pinned", False)}
                    if not heartbeat_running:
                        heartbeat_running = True
                        heartbeat_thread = threading.Thread(
                            target=_heartbeat_loop, args=(conn,), daemon=True
                        )
                        heartbeat_thread.start()
                    response_payload = {"status": "success"}
                elif method == "pyforge/unsubscribe":
                    path = params.get("path")
                    if path in subscriptions and not subscriptions[path]["pinned"]:
                        subscriptions.pop(path, None)
                        last_known_state.pop(path, None)
                    response_payload = {"status": "success"}
                elif method == "pyforge/watch_class":
                    class_path = params.get("class_path")
                    try:
                        cls = _resolve_path(f"class:{class_path}", agent_instance.scope)
                        success = watch_class_legacy(cls, conn, watched_classes)
                        if success:
                            response_payload = {"status": "success"}
                        else:
                            response_payload = {
                                "status": "error",
                                "payload": "Failed to watch class (may be a built-in or native type).",
                            }
                    except Exception:
                        response_payload = {
                            "status": "error",
                            "payload": traceback.format_exc(),
                        }
                elif method == "pyforge/unwatch_class":
                    class_path = params.get("class_path")
                    if class_path in watched_classes:
                        del watched_classes[class_path]
                    response_payload = {"status": "success"}
                else:
                    response_payload = {
                        "status": "error",
                        "type": "protocol_error",
                        "payload": f"Unknown method: {method}",
                    }

                response = {"jsonrpc": "2.0", "id": req_id, "result": response_payload}
                send_message(conn, response)
    except Exception as e:
        log.error(f"An error occurred in handle_client: {e}", exc_info=True)
        connection_event.set()
    finally:
        log.info("Client disconnected.")
        if "on_agent_disconnect" in master_script_hooks:
            master_script_hooks["on_agent_disconnect"]()
        heartbeat_running = False
        log.removeHandler(socket_handler)
        connection_event.set()


def listen(connection_event: threading.Event):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        def server_loop():
            try:
                conn, _ = server_socket.accept()
                _handle_client(conn, connection_event)
            finally:
                server_socket.close()

        threading.Thread(
            target=server_loop, name="Thread-1 (server_loop)", daemon=True
        ).start()
    except Exception as e:
        print(f"[PyForge Agent] FATAL: Could not start listener: {e}", file=sys.stderr)
        connection_event.set()
