# src/pyforge/agent/pf.pyi

"""
The PyForge Live Introspection API (`pf`)

This module is dynamically injected into your application at runtime by the
PyForge agent. It provides a powerful set of functions to inspect, manipulate,
and script your live application state without needing to restart it.

All functions operate directly on the running process.
"""

from typing import Any, Type, List, Dict, Callable
import gc

def log(*args: Any) -> None:
    """
    Logs a message back to the PyForge console in the IDE.

    This is the primary way to send information from a PyForge script
    back to the Forge user interface. It accepts multiple arguments,
    similar to the built-in `print()` function.

    Example:
        ```python
        import pf
        player_health = 100
        pf.log("Player health is:", player_health)
        ```
    """
    ...

def find(class_name: str) -> List[Any]:
    """
    Finds all live instances of a given class name in memory.

    This function scans the garbage collector's object list to find all
    active objects that are instances of the specified class.

    Example:
        ```python
        import pf
        # Find all active "Enemy" objects in a game
        all_enemies = pf.find("Enemy")
        pf.log(f"Found {len(all_enemies)} enemies.")
        ```

    :param class_name: The string name of the class to find (e.g., "Player").
    :return: A list of all found instances.
    """
    ...

def get(name: str) -> Any:
    """
    Gets a live object by its variable name from the application's scope.

    PyForge will attempt to find the object in global, local, and module
    scopes. This is useful for getting a handle on well-known objects.

    Example:
        ```python
        import pf
        # Get the main 'game_manager' object
        manager = pf.get("game_manager")
        if manager:
            manager.pause()
        ```

    :param name: The variable name of the object to get.
    :return: The object instance, or raises a NameError if not found.
    """
    ...

def set_attribute(path: str, value: Any) -> None:
    """
    Sets an attribute on a live object using a string path.

    The path is a dot-separated string that navigates from a known object
    to the target attribute. The value can be any live Python object.

    Example:
        ```python
        import pf
        player = pf.get("player")
        # Set the player's health directly
        # NOTE: This example is often better as: pf.set_attribute(player, "health", 100)
        # Assuming the function takes (obj, attr_name, value) or (path_str, value)
        # Based on your signature: def set_attribute(path: str, value: Any)
        # I'm adjusting the example to fit a path string, e.g., "player.health"
        pf.set_attribute("player.health", 100) 
        ```

    :param path: The target object to modify.
    :param value: The new value to set.
    """
    ...

def call(path: str, *args: Any, **kwargs: Any) -> Any:
    """
    Calls a function or method on a live object.

    Arguments can be live objects from your application.

    Example:
        ```python
        import pf
        player = pf.get("player")
        
        # Call a method with no arguments
        pf.call(player.heal_fully)

        # Call a method with an argument
        pf.call(player.take_damage, 25)
        ```

    :param path: A reference to the callable (e.g., `player.heal`).
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    :return: The return value of the called function.
    """
    ...

def delete(obj: Any) -> bool:
    """
    (Advanced) Deletes an object from the live application.

    This is a dangerous operation that can cause instability if other parts
    of the application still hold references to the object. It is recommended
    to use the UI context menu for safer deletion where possible.

    Example:
        ```python
        import pf
        old_enemy = pf.find("Enemy")[0]
        pf.delete(old_enemy)
        ```

    :param obj: The live object instance to delete.
    :return: True on success, False on failure.
    """
    ...

def watch(class_obj: Type[Any]) -> bool:
    """
    Starts watching a class for new instances created at runtime.

    When a new instance of the watched class is created, a notification
    will appear in the Forge UI, and the instance will be shown in the
    Object Browser. This requires passing the actual class type, not its name.

    Example:
        ```python
        import pf
        from my_game import Bullet
        # Start watching for every new Bullet that gets created
        pf.watch(Bullet)
        ```

    :param class_obj: The class type to watch.
    :return: True on success, False on failure.
    """
    ...

def migrate_instance(instance: Any, new_class: Type[Any]) -> bool:
    """
    (Advanced & Risky) Migrates an object instance to a new class definition in-place.

    This directly changes the `__class__` attribute of the instance. It is fast but
    can be dangerous if the new class has a different memory layout (e.g., adds `__slots__`)
    than the old one, potentially leading to memory corruption or crashes.

    This is best used for simple class changes, like modifying a method.

    Example:
        ```python
        import pf
        
        # After hot-reloading the 'player' module
        old_player_instances = pf.find("Player")
        NewPlayerClass = pf.get("Player")

        for p in old_player_instances:
            pf.migrate_instance(p, NewPlayerClass)
        ```

    :param instance: The old object instance to migrate.
    :param new_class: The new (reloaded) class definition to apply.
    :return: True on success, False on failure.
    """
    ...

def copy_state(source: Any, destination: Any) -> None:
    """
    (Safer) Copies all attributes from a source object to a destination object.

    This is the recommended way to migrate state between an old instance and a
    newly created one after a hot reload. It avoids the memory risks of
    `pf.migrate_instance` by creating a separate, healthy object.

    Note: This performs a shallow copy of the instance's `__dict__`.

    Example:
        ```python
        import pf

        old_player = pf.get("player")
        NewPlayerClass = pf.get("Player")
        new_player = NewPlayerClass() # Create a new, clean instance

        pf.copy_state(old_player, new_player)
        
        # Now you must manually replace references to old_player
        # with new_player throughout your application.
        ```

    :param source: The object to copy attributes from.
    :param destination: The object to copy attributes to.
    """
    ...

def replace_instance(old_instance: Any, new_instance: Any) -> int:
    """
    (Experimental) Attempts to find all references to an old instance and
    replace them with a new instance.

    This is a powerful but potentially slow and incomplete operation. It uses the
    garbage collector to find all referrers and tries to update them. It may not
    work for all container types or complex reference scenarios. Use with caution.

    Example:
        ```python
        import pf
        
        old = pf.get("old_thing")
        new = pf.get("NewThing")()

        pf.replace_instance(old, new)
        ```

    :param old_instance: The object to be replaced.
    :param new_instance: The object to substitute in its place.
    :return: The number of referrers that were successfully updated.
    """
    ...

def source_of(obj: Any) -> str:
    """
    Gets the source code of a live function, class, method, or module.

    Example:
        ```python
        import pf
        player_class = pf.get("Player")
        pf.log(pf.source_of(player_class))
        ```

    :param obj: The object to get the source code from.
    :return: A string containing the source code.
    """
    ...

def doc_of(obj: Any) -> str:
    """
    Gets the docstring of a live object.

    Example:
        ```python
        import pf
        player = pf.get("player")
        heal_method = player.heal
        pf.log(pf.doc_of(heal_method))
        ```

    :param obj: The object to get the docstring from.
    :return: A string containing the formatted docstring.
    """
    ...

def get_referrers(obj: Any) -> List[Any]:
    """
    (Advanced) Finds all live objects that hold a reference to the given object.

    This can be a powerful tool for debugging memory leaks or understanding
    object relationships. Note that this can be a slow operation.

    Example:
        ```python
        import pf
        player = pf.get("player")
        referrers = pf.get_referrers(player)
        pf.log(f"Player is referenced by {len(referrers)} objects.")
        ```

    :param obj: The object whose referrers you want to find.
    :return: A list of objects that refer to the input object.
    """
    ...

def inspect_object(obj: Any) -> Dict[str, Any]:
    """
    Returns a dictionary of an object's public attributes and methods.

    This provides a structured view of an object's contents, separating
    data (attributes) from behavior (methods).

    Example:
        ```python
        import pf
        player = pf.get("player")
        details = pf.inspect_object(player)
        pf.log("Player Attributes:", details['attributes'])
        pf.log("Player Methods:", details['methods'])
        ```

    :param obj: The object to inspect.
    :return: A dictionary containing 'attributes' and 'methods'.
    """
    ...

def get_modules() -> List[Dict[str, str]]:
    """
    Gets a list of all loaded, user-defined modules from the target application.

    This function filters out modules from the standard library and installed
    packages (site-packages) to show only the code relevant to the current project.

    Example:
        ```python
        import pf
        modules = pf.get_modules()
        for module in modules:
            pf.log(module['name'])
        ```

    :return: A list of dictionaries, each with 'name' and 'file_path'.
    """
    ...

def track(name: str, value: Any) -> None:
    """
    Tracks a custom metric for display in the PyForge Metrics panel.

    This allows you to monitor any variable or value from your application
    in real-time. The value should be a simple type that can be easily
    represented (like a number, string, or boolean).

    Example:
        ```python
        import pf
        player_count = len(pf.find("Player"))
        pf.track("Active Players", player_count)
        ```

    :param name: The string name of the metric.
    :param value: The value to track.
    """
    ...

def run_script(script_path: str, context: Dict = None) -> None:
    """
    Executes another PyForge script from within a script.

    This is used in the master script to delegate event handling to other,
    more modular scripts. The path is relative to the workspace root.

    Example:
        ```python
        import pf
        # Run a script that performs a weekly cleanup
        pf.run_script("scripts/weekly_cleanup.pfscript")
        ```

    :param script_path: The workspace-relative path to the .pfscript file.
    :param context: An optional dictionary to pass data to the script.
    """
    ...

def metric(name: str, type: str = 'value', unit: str = '') -> Callable:
    """
    A decorator for creating a custom metric from a function.

    The decorated function should take no arguments and return a value that
    can be serialized (number, string, bool). It will be called on every
    agent heartbeat to update the metric in the UI.

    Example:
        ```python
        import pf
        import random

        @pf.metric(name="Random Value", type="graph")
        def my_random_metric():
            return random.randint(0, 100)
        ```

    :param name: The display name for the metric in the UI.
    :param type: (Future) The type of metric, e.g., 'value' or 'graph'.
    :param unit: (Future) The unit for display, e.g., '%', 'ms'.
    :return: A decorator.
    """
    ...