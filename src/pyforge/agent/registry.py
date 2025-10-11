import logging

log = logging.getLogger("PyForgeAgent")

INSTANCE_REGISTRY = {}


def register(name, instance):
    """Adds an object instance to the global registry."""
    if name not in INSTANCE_REGISTRY:
        INSTANCE_REGISTRY[name] = instance


def get_scope():
    """Returns the current registry scope."""
    return INSTANCE_REGISTRY
