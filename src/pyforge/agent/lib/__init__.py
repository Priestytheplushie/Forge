from types import SimpleNamespace
import traceback
import sys
from ..registry import get_scope
from . import comms, discovery, state, modules, metrics, scripts


def create_pf_object(agent_instance, serializer_func, watch_function):
    """
    Creates and returns the `pf` object that will be injected into the user's application.
    This object serves as the public API for live scripting.
    """
    pf_object = SimpleNamespace()

    pf_object.log = comms.log
    pf_object.find = discovery.find
    pf_object.source_of = discovery.source_of
    pf_object.doc_of = discovery.doc_of
    pf_object.get_referrers = discovery.get_referrers
    pf_object.inspect_object = discovery.inspect_object
    pf_object.get_modules = discovery.get_modules

    pf_object.set_attribute = state.set_attribute
    pf_object.call = state.call_callable
    pf_object.delete = state.delete_object
    pf_object.migrate_instance = state.migrate_instance
    pf_object.copy_state = state.copy_state
    pf_object.replace_instance = state.replace_instance

    pf_object.watch = watch_function
    pf_object.track = metrics.track
    pf_object.metric = metrics.metric
    pf_object.override = metrics.override
    pf_object.run_script = scripts.run_script

    def pf_get(name: str):
        """Gets an object, triggering JIT discovery if needed."""

        if name.isdigit():
            return get_scope().get(name)
        try:
            return eval(name, agent_instance.scope)
        except NameError:
            found_obj = agent_instance.find_and_register(name)
            if found_obj is not None:
                agent_instance.scope[name] = found_obj
                return found_obj
            else:
                raise

    pf_object.get = pf_get

    pf_object._hot_reload = modules.hot_reload_module

    def _format_traceback():
        """Creates a structured traceback dictionary from the current exception."""
        exc_type, exc_value, exc_tb = sys.exc_info()
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

    def execute_code(code, is_script=False, serializer=None):
        """
        Executes a string of Python code within the agent's scope,
        which includes globals, builtins, and the `pf` object itself.
        """
        serialize_func = serializer or serializer_func

        if is_script:
            try:
                exec(code, agent_instance.scope)
                return {"status": "success", "type": "script_success", "payload": None}
            except Exception:
                return {"status": "error", "payload": _format_traceback()}

        try:
            if code.strip().startswith("print("):
                inner_expr = code.strip()[6:-1]
                code = f"pf.log({inner_expr})"

            result = eval(code, agent_instance.scope)
            return {
                "status": "success",
                "type": "expression_result",
                "payload": serialize_func(result),
            }
        except NameError:
            found_obj = agent_instance.find_and_register(code)
            if found_obj is not None:
                try:
                    agent_instance.scope[code] = found_obj
                    result = eval(code, agent_instance.scope)
                    return {
                        "status": "success",
                        "type": "expression_result",
                        "payload": serialize_func(result),
                    }
                except Exception:
                    return {"status": "error", "payload": _format_traceback()}
            else:
                return {"status": "error", "payload": _format_traceback()}
        except SyntaxError:
            try:
                exec(code, agent_instance.scope)
                return {
                    "status": "success",
                    "type": "statement_success",
                    "payload": None,
                }
            except Exception:
                return {"status": "error", "payload": _format_traceback()}
        except Exception:
            return {"status": "error", "payload": _format_traceback()}

    pf_object.execute_code = execute_code

    return pf_object
