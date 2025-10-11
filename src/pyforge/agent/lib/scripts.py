from typing import Dict


def run_script(script_path: str, context: Dict = None) -> None:
    """
    Executes another PyForge script.

    This is primarily used within the master.pfscript to delegate event handling
    to other, more modular scripts. The path is relative to the workspace root.

    An optional context dictionary can be passed, which will be available
    as a 'context' variable inside the executed script.

    :param script_path: The workspace-relative path to the .pfscript file.
    :param context: An optional dictionary to pass data to the script.
    """

    print(f"pf.run_script is only available in a live PyForge session.")
