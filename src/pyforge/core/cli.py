import sys
import os
import runpy
import logging
from pathlib import Path
import threading

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pyforge_root = os.path.dirname(script_dir)
    if pyforge_root not in sys.path:
        sys.path.insert(0, pyforge_root)
except NameError:
    if os.path.abspath("src/pyforge") not in sys.path:
        sys.path.insert(0, os.path.abspath("src/pyforge"))

from agent.agent import listen, master_script_hooks


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "run":

        print("This script is intended to be run by the Forge IDE.", file=sys.stderr)
        return

    script_path = sys.argv[2]
    if not os.path.exists(script_path):
        print(f"Error: File not found at '{script_path}'", file=sys.stderr)
        return

    script_dir = str(Path(script_path).parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    connection_event = threading.Event()
    listen(connection_event)

    connected = connection_event.wait(timeout=5.0)

    if not connected:

        print(
            "[PyForge] WARNING: Client did not connect within timeout. Live agent will not be available.",
            file=sys.stderr,
        )

    sys.argv = sys.argv[2:]

    try:
        if "on_script_start" in master_script_hooks:
            master_script_hooks["on_script_start"]()
        runpy.run_path(script_path, run_name="__main__")
    except Exception as e:
        print(f"\n--- User script terminated with an error ---", file=sys.stderr)
        import traceback

        tb_dict = {
            "type": type(e).__name__,
            "message": str(e),
            "frames": traceback.format_exc(),
        }
        if "on_exception" in master_script_hooks:
            master_script_hooks["on_exception"](e, tb_dict)
        traceback.print_exc()
    finally:
        if "on_script_end" in master_script_hooks:
            master_script_hooks["on_script_end"]()


if __name__ == "__main__":
    main()
