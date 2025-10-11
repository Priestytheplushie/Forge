import logging


def log(*args):
    """
    Logs a message back to the PyForge console in the IDE.
    Accepts multiple arguments, similar to the built-in print().
    """
    agent_log = logging.getLogger("PyForgeAgent")
    message = " ".join(str(arg) for arg in args)
    agent_log.info(message)
