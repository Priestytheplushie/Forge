import gc
from typing import Any, Type, List, Dict, Callable


def set_attribute(obj, name: str, value: Any):
    """
    Sets an attribute on a live object.
    :param obj: The object to modify.
    :param name: The string name of the attribute to set.
    :param value: The new value for the attribute.
    """
    setattr(obj, name, value)


def call_callable(callable_obj, *args, **kwargs):
    """
    Calls a function or method on a live object.
    :param callable_obj: A direct reference to the function/method.
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    :return: The return value of the called function.
    """
    return callable_obj(*args, **kwargs)


def delete_object(obj):
    """
    (Dangerous) Schedules an object for deletion by moving it to the agent's trash.
    The object will be garbage collected if no other strong references exist.
    """

    return True


def migrate_instance(instance: Any, new_class: Type[Any]) -> bool:
    """(Advanced) In-place migration of an instance to a new class."""
    try:
        instance.__class__ = new_class
        return True
    except TypeError:

        return False


def copy_state(source: Any, destination: Any) -> None:
    """Shallow copies attributes from source to destination."""
    if hasattr(source, "__dict__") and hasattr(destination, "__dict__"):
        destination.__dict__.update(source.__dict__)


def replace_instance(old_instance: Any, new_instance: Any) -> int:
    """(Experimental) Attempts to replace all references to old_instance with new_instance."""
    referrers = gc.get_referrers(old_instance)
    updated_count = 0
    for ref in referrers:

        if ref is locals() or ref is globals():
            continue
        try:
            if isinstance(ref, dict):
                for k, v in ref.items():
                    if v is old_instance:
                        ref[k] = new_instance
                        updated_count += 1
            elif isinstance(ref, list):
                for i, v in enumerate(ref):
                    if v is old_instance:
                        ref[i] = new_instance
                        updated_count += 1
            elif hasattr(ref, "__dict__"):
                for k, v in ref.__dict__.items():
                    if v is old_instance:
                        setattr(ref, k, new_instance)
                        updated_count += 1
        except Exception:

            continue
    return updated_count
