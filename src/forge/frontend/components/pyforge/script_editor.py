from ..editor.editor_widget import EditorWidget
from ...utils import uri_to_path
from pathlib import Path
import json


class PyForgeScriptEditor(EditorWidget):
    """
    A specialized editor for PyForge scripts that communicates its
    disconnected state to the underlying Monaco editor for custom highlighting.
    """

    def __init__(self, theme_data: dict, main_window, parent=None):
        super().__init__(theme_data, parent)
        self.is_session_active = True
        self.is_global_script = False
        self.main_window = main_window
        self.is_master_script = False

    def set_session_active(self, active: bool):
        """Tells the editor whether a PyForge session is active."""
        if self.is_session_active != active:
            self.is_session_active = active
            if self.is_ready:
                self.web_view.page().runJavaScript(
                    f"set_pyforge_session_active({str(active).lower()});"
                )

    def set_content(self, content: str, lang_id: str, uri: str, callback):

        try:
            path = uri_to_path(uri)
            if path.name == "master.pfscript":
                self.is_master_script = True
        except Exception:
            self.is_master_script = False

        def post_load_callback():
            self.set_session_active(self.is_session_active)
            self._inject_pf_library()
            if callback:
                callback()

        super().set_content(content, lang_id, uri, post_load_callback)

    def _inject_pf_library(self):
        """Loads the pf.pyi stub file and injects it as an extra library."""
        if not self.is_ready or not self.main_window:
            return

        try:
            app_root = self.main_window.app_root
            pf_stub_path = Path(app_root) / "src" / "pyforge" / "agent" / "pf.pyi"
            if pf_stub_path.exists():
                stub_content = pf_stub_path.read_text(encoding="utf-8")
                lib_uri = "ts:filename/pyforge.d.ts"
                self.web_view.page().runJavaScript(
                    f"add_extra_lib({json.dumps(stub_content)}, '{lib_uri}');"
                )
        except Exception as e:
            print(f"[ScriptEditor] Failed to inject pf.pyi library: {e}")
