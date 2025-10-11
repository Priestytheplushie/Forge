import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtWidgets import QInputDialog
from ..components.editor.editor_widget import EditorWidget
from ..components.pyforge.script_editor import PyForgeScriptEditor
from ..utils import uri_to_path


class LSPClient(QObject):
    rename_response_received = Signal(dict)

    def __init__(self, main_window, file_manager):
        super().__init__(main_window)
        self.main_window = main_window
        self.file_manager = file_manager
        self.lsp_manager = None
        self.document_versions = {}
        self.diagnostics_by_uri = {}
        self.pending_semantic_token_requests = {}
        self.pending_completion_requests = {}
        self.pending_hover_requests = {}
        self.pending_symbol_requests = {}
        self.pending_rename_requests = {}
        self.pending_code_action_requests = {}
        self.pending_codelens_requests = {}
        self._pending_token_request_queue = []
        self.outline_editor = None
        self.is_lsp_ready = False
        self._connect_signals()

    def _connect_signals(self):
        self.main_window.problems_panel.problem_clicked.connect(self.on_problem_clicked)
        self.main_window.outline_panel.symbol_clicked.connect(self.on_symbol_clicked)

    def set_lsp_manager(self, lsp_manager):
        self.lsp_manager = lsp_manager
        if not self.lsp_manager:
            return
        self.lsp_manager.lsp_notification_received.connect(self.handle_lsp_notification)
        self.lsp_manager.lsp_response_received.connect(self.handle_lsp_response)
        self.lsp_manager.lsp_ready.connect(self._on_lsp_ready)

        pf_stub_path = (
            Path(self.main_window.app_root) / "src" / "pyforge" / "agent" / "pf.pyi"
        )
        if pf_stub_path.exists():
            self.lsp_manager.add_extra_file_for_analysis(str(pf_stub_path))

    def clear_lsp_manager(self):
        self.lsp_manager = None
        self.is_lsp_ready = False
        self.diagnostics_by_uri.clear()
        self.update_problems_panel()
        self.main_window.outline_panel.clear_symbols()

    @Slot()
    def _on_lsp_ready(self):
        print("[LSPClient] LSP is now ready.")
        self.is_lsp_ready = True
        self.main_window.lsp_status_label.setText("LSP: Ready")
        for uri in self._pending_token_request_queue:
            self.request_semantic_tokens(uri)
        self._pending_token_request_queue.clear()

    def update_problems_panel(self):
        self.main_window.problems_panel.update_diagnostics(self.diagnostics_by_uri)
        count = sum(len(diags) for diags in self.diagnostics_by_uri.values())
        title = f"Problems ({count})" if count > 0 else "Problems"
        self.main_window.problems_dock.setWindowTitle(title)
        errors = 0
        warnings = 0
        hints = 0
        for diags in self.diagnostics_by_uri.values():
            for diag in diags:
                severity = diag.get("severity", 4)
                if severity == 1:
                    errors += 1
                elif severity == 2:
                    warnings += 1
                else:
                    hints += 1
        self.main_window.error_label.setText(f"{errors}")
        self.main_window.warning_label.setText(f"{warnings}")
        self.main_window.hint_label.setText(f"{hints}")

    @Slot(str, str, str, EditorWidget)
    def on_file_opened(self, uri, lang_id, content, editor):
        editor.text_changed.connect(
            lambda editor=editor, uri=uri: self.on_editor_text_changed(editor, uri)
        )
        editor.completion_requested.connect(self.on_completion_requested)
        editor.hover_requested.connect(self.on_hover_requested)
        editor.cursor_position_changed.connect(self.on_cursor_position_changed)
        editor.code_action_requested.connect(self.on_code_action_requested)
        editor.rename_requested.connect(self.on_rename_requested)
        editor.codelens_requested.connect(self.on_codelens_requested)

        is_pyforge_script = isinstance(editor, PyForgeScriptEditor)
        if self.lsp_manager and (lang_id == "python" or is_pyforge_script):
            effective_lang_id = "python"
            self.document_versions[uri] = 1
            self.lsp_manager.send_notification(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": effective_lang_id,
                        "version": 1,
                        "text": content,
                    }
                },
            )
            self.request_semantic_tokens(uri)
            self.request_document_symbols(uri)

    @Slot(str)
    def on_file_closed(self, uri):
        if self.outline_editor and self.outline_editor.current_uri == uri:
            self.outline_editor = None
            self.main_window.outline_panel.clear_symbols()

        self.document_versions.pop(uri, None)
        if self.lsp_manager:
            self.lsp_manager.send_notification(
                "textDocument/didClose", {"textDocument": {"uri": uri}}
            )
        if uri in self.diagnostics_by_uri:
            del self.diagnostics_by_uri[uri]
            self.update_problems_panel()

    def on_editor_text_changed(self, editor, uri: str):
        if self.lsp_manager:
            editor.get_text(
                lambda content: self._on_get_text_for_didChange(content, uri)
            )

    def _on_get_text_for_didChange(self, content: str, uri: str):
        if content is None or uri not in self.document_versions:
            return
        self.document_versions[uri] += 1
        self.lsp_manager.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": self.document_versions[uri]},
                "contentChanges": [{"text": content}],
            },
        )
        self.request_semantic_tokens(uri)
        self.request_document_symbols(uri)

    @Slot(QObject, str, str, int, int)
    def on_completion_requested(self, editor, callback_id, uri, line, char):
        if (
            not (uri.startswith("file://") or uri.startswith("untitled:"))
            or not self.lsp_manager
            or not self.is_lsp_ready
        ):
            editor.resolve_completions(callback_id, [])
            return
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": char - 1},
        }
        request_id = self.lsp_manager.send_request("textDocument/completion", params)
        self.pending_completion_requests[request_id] = (editor, callback_id)

    @Slot(QObject, str, str, int, int)
    def on_hover_requested(self, editor, callback_id, uri, line, char):
        if (
            not (uri.startswith("file://") or uri.startswith("untitled:"))
            or not self.lsp_manager
            or not self.is_lsp_ready
        ):
            editor.resolve_hover(callback_id, None)
            return
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": char - 1},
        }
        request_id = self.lsp_manager.send_request("textDocument/hover", params)
        self.pending_hover_requests[request_id] = (editor, callback_id)

    @Slot(QObject, str, str, dict, list)
    def on_code_action_requested(
        self, editor, callback_id, uri, range_data, diagnostics
    ):
        if not self.lsp_manager or not self.is_lsp_ready:
            editor.resolve_code_actions(callback_id, [])
            return
        params = {
            "textDocument": {"uri": uri},
            "range": range_data,
            "context": {"diagnostics": diagnostics},
        }
        request_id = self.lsp_manager.send_request("textDocument/codeAction", params)
        self.pending_code_action_requests[request_id] = (editor, callback_id)

    @Slot(QObject, str, str)
    def on_codelens_requested(self, editor, callback_id, uri: str):
        if not self.lsp_manager or not self.is_lsp_ready:
            editor.resolve_codelens(callback_id, [])
            return
        request_id = self.lsp_manager.send_request(
            "textDocument/codeLens", {"textDocument": {"uri": uri}}
        )
        self.pending_codelens_requests[request_id] = (editor, callback_id)

    @Slot(str, int, int)
    def on_rename_requested(self, uri, line, char):
        if not self.lsp_manager or not self.is_lsp_ready:
            return
        new_name, ok = QInputDialog.getText(
            self.main_window, "Rename Symbol", "Enter new name:"
        )
        if ok and new_name:
            params = {
                "textDocument": {"uri": uri},
                "position": {"line": line - 1, "character": char - 1},
                "newName": new_name,
            }
            request_id = self.lsp_manager.send_request("textDocument/rename", params)
            self.pending_rename_requests[request_id] = True

    def request_semantic_tokens(self, uri: str):
        if self.lsp_manager and self.is_lsp_ready:
            request_id = self.lsp_manager.send_request(
                "textDocument/semanticTokens/full", {"textDocument": {"uri": uri}}
            )
            self.pending_semantic_token_requests[request_id] = uri
        elif uri not in self._pending_token_request_queue:
            self._pending_token_request_queue.append(uri)

    def request_document_symbols(self, uri: str):
        if self.lsp_manager and self.is_lsp_ready:
            params = {"textDocument": {"uri": uri}}
            request_id = self.lsp_manager.send_request(
                "textDocument/documentSymbol", params
            )
            self.pending_symbol_requests[request_id] = uri

    @Slot(dict)
    def handle_lsp_response(self, response: dict):
        request_id = response.get("id")
        result = response.get("result")
        if request_id in self.pending_completion_requests:
            editor, cb_id = self.pending_completion_requests.pop(request_id)
            items = result.get("items", []) if result else []
            editor.resolve_completions(cb_id, items)
        elif request_id in self.pending_hover_requests:
            editor, cb_id = self.pending_hover_requests.pop(request_id)
            editor.resolve_hover(cb_id, result)
        elif request_id in self.pending_semantic_token_requests:
            uri = self.pending_semantic_token_requests.pop(request_id)
            editor_found = None
            if uri.startswith("untitled:"):
                for editor in self.file_manager.editors_by_path.values():
                    if editor.current_uri == uri:
                        editor_found = editor
                        break
            else:
                try:
                    path = str(uri_to_path(uri))
                    editor_found = self.file_manager.editors_by_path.get(path)
                except (ValueError, OSError):
                    pass
            if editor_found:
                tokens = result.get("data", []) if result else []
                editor_found.show_semantic_tokens(tokens)

        elif request_id in self.pending_symbol_requests:
            uri = self.pending_symbol_requests.pop(request_id)
            symbols = result if result else []
            active_uri = (
                self.outline_editor.current_uri if self.outline_editor else None
            )
            if uri == active_uri:
                self.main_window.outline_panel.update_symbols(symbols)
        elif request_id in self.pending_rename_requests:
            self.pending_rename_requests.pop(request_id)
            self.rename_response_received.emit(result or {})
        elif request_id in self.pending_code_action_requests:
            editor, cb_id = self.pending_code_action_requests.pop(request_id)
            editor.resolve_code_actions(
                cb_id, self.add_custom_code_actions(result or [])
            )
        elif request_id in self.pending_codelens_requests:
            editor, cb_id = self.pending_codelens_requests.pop(request_id)
            editor.get_text(
                lambda content: self._resolve_codelens(cb_id, editor, content, result)
            )

    def _resolve_codelens(self, cb_id, editor, content, result):
        if content is None:
            editor.resolve_codelens(cb_id, [])
            return
        lenses = self.add_custom_codelens(content)
        editor.resolve_codelens(cb_id, lenses)

    def add_custom_codelens(self, content: str) -> list:
        lenses = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            line_num = i + 1
            stripped_line = line.strip()
            if stripped_line.startswith("def on_"):
                hook_name = stripped_line.split("(", 1)[0].replace("def ", "")

                doc = self.main_window.pyforge_controller.all_hook_definitions.get(
                    hook_name, {}
                ).get("docstring", "This function runs on a specific agent event.")
                lenses.append(
                    {
                        "range": {
                            "startLineNumber": line_num,
                            "startColumn": 1,
                            "endLineNumber": line_num,
                            "endColumn": 1,
                        },
                        "command": {"title": "(PyForge Hook)", "tooltip": doc},
                    }
                )
            elif "@pf.metric" in stripped_line:
                lenses.append(
                    {
                        "range": {
                            "startLineNumber": line_num,
                            "startColumn": 1,
                            "endLineNumber": line_num,
                            "endColumn": 1,
                        },
                        "command": {
                            "title": "(PyForge Custom Metric)",
                            "tooltip": "This function defines a value that appears in the Metrics panel.",
                        },
                    }
                )
            elif "@pf.override" in stripped_line:
                lenses.append(
                    {
                        "range": {
                            "startLineNumber": line_num,
                            "startColumn": 1,
                            "endLineNumber": line_num,
                            "endColumn": 1,
                        },
                        "command": {
                            "title": "⚠ (PyForge Override)",
                            "tooltip": "Warning: This function modifies core agent behavior and can cause instability.",
                        },
                    }
                )
        return lenses

    def add_custom_code_actions(self, actions: list) -> list:
        actions.append(
            {
                "title": "Discover in PyForge",
                "kind": "refactor",
                "command": {"title": "Discover", "command": "pyforge.discoverSymbol"},
            }
        )
        return actions

    @Slot(dict)
    def handle_lsp_notification(self, notification: dict):
        method = notification.get("method")
        if method == "textDocument/publishDiagnostics":
            params = notification.get("params", {})
            uri = params.get("uri")
            if not uri:
                return

            diagnostics = params.get("diagnostics", [])
            editor_found = None
            if uri.startswith("untitled:"):
                for editor in self.file_manager.editors_by_path.values():
                    if editor.current_uri == uri:
                        editor_found = editor
                        break
            else:
                try:
                    path = str(uri_to_path(uri))
                    editor_found = self.file_manager.editors_by_path.get(path)
                except (ValueError, OSError):
                    pass
            if editor_found:
                editor_found.show_diagnostics(diagnostics)

            if diagnostics:
                self.diagnostics_by_uri[uri] = diagnostics
            elif uri in self.diagnostics_by_uri:
                del self.diagnostics_by_uri[uri]

            self.update_problems_panel()

    @Slot(str, int, int)
    def on_problem_clicked(self, uri: str, line: int, char: int):
        try:
            target_path = uri_to_path(uri)
        except Exception as e:
            print(f"[LSPClient] Error converting URI to path: {e}")
            return
        self.file_manager.open_file_from_path(str(target_path))
        if str(target_path) in self.file_manager.editors_by_path:
            editor = self.file_manager.editors_by_path[str(target_path)]
            self.main_window.tab_widget.setCurrentWidget(editor)
            editor.setFocus()
            editor.jump_and_highlight(line, char)
        else:
            print(f"[LSPClient] ERROR: Could not find editor for path {target_path}")

    @Slot(int, int)
    def on_symbol_clicked(self, line: int, char: int):
        if self.outline_editor:
            self.main_window.tab_widget.setCurrentWidget(self.outline_editor)
            self.outline_editor.setFocus()
            self.outline_editor.jump_and_highlight(line, char)

    @Slot(int, int)
    def on_cursor_position_changed(self, line: int, column: int):
        self.main_window.cursor_pos_label.setText(f"Ln {line}, Col {column}")

    def update_outline_panel(self, editor: EditorWidget | None):
        self.outline_editor = editor
        if editor and editor.current_uri:
            self.request_document_symbols(editor.current_uri)
        else:
            self.main_window.outline_panel.clear_symbols()

    def update_outline_panel_from_uri(self, uri: str | None):
        if uri:
            path = str(uri_to_path(uri))
            self.outline_editor = self.file_manager.editors_by_path.get(path)
            self.request_document_symbols(uri)
        else:
            self.outline_editor = None
            self.main_window.outline_panel.clear_symbols()
