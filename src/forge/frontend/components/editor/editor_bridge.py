from PySide6.QtCore import QObject, Signal, Slot


class EditorBridge(QObject):
    _internal_web_channel_ready = Signal()
    js_ready = Signal()
    text_received = Signal(str, str)
    content_changed_signal = Signal()
    js_log_received = Signal(str, str)
    semantic_tokens_applied = Signal(str)
    model_ready = Signal(str)
    cursor_position_changed = Signal(int, int)
    all_conflicts_resolved_in_editor = Signal()

    _completion_requested_from_js = Signal(str, str, int, int)
    _hover_requested_from_js = Signal(str, str, int, int)
    _code_action_requested_from_js = Signal(str, str, list)

    stage_lines_requested = Signal(str)
    apply_staged_changes_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    cut_requested = Signal()
    copy_requested = Signal()
    paste_requested = Signal()

    conflict_check_result = Signal(str, bool)

    @Slot()
    def on_web_channel_ready(self):
        """Called from JS when the web channel is established."""
        self._internal_web_channel_ready.emit()

    @Slot()
    def js_loaded(self):
        self.js_ready.emit()

    @Slot(str, str)
    def receive_text(self, callback_id, content):
        self.text_received.emit(callback_id, content)

    @Slot()
    def on_content_changed(self):
        self.content_changed_signal.emit()

    @Slot(str, str)
    def log_message(self, level: str, message: str):
        self.js_log_received.emit(level, message)

    @Slot(str)
    def on_model_ready(self, callback_id: str):
        self.model_ready.emit(callback_id)

    @Slot(str)
    def on_semantic_tokens_applied(self, callback_id: str):
        self.semantic_tokens_applied.emit(callback_id)

    @Slot(int, int)
    def on_cursor_position_changed(self, line: int, column: int):
        self.cursor_position_changed.emit(line, column)

    @Slot(str)
    def on_stage_lines(self, selected_text: str):
        self.stage_lines_requested.emit(selected_text)

    @Slot()
    def on_apply_staged_changes(self):
        self.apply_staged_changes_requested.emit()

    @Slot(str, str, int, int)
    def request_completions(
        self, callback_id: str, uri: str, line: int, character: int
    ):
        self._completion_requested_from_js.emit(callback_id, uri, line, character)

    @Slot(str, str, int, int)
    def request_hover(self, callback_id: str, uri: str, line: int, character: int):
        self._hover_requested_from_js.emit(callback_id, uri, line, character)

    @Slot(str, str, list)
    def request_code_actions(self, callback_id: str, uri: str, diagnostics: list):
        self._code_action_requested_from_js.emit(callback_id, uri, diagnostics)

    @Slot(str, bool)
    def receive_conflict_check_result(self, callback_id: str, has_conflicts: bool):
        self.conflict_check_result.emit(callback_id, has_conflicts)

    @Slot()
    def on_all_conflicts_resolved(self):
        self.all_conflicts_resolved_in_editor.emit()


class DiffBridge(QObject):
    _internal_web_channel_ready = Signal()
    js_ready = Signal()
    stage_lines_requested = Signal(str)

    @Slot()
    def on_web_channel_ready(self):
        """Called from JS when the web channel is established."""
        self._internal_web_channel_ready.emit()

    @Slot()
    def js_loaded(self):
        self.js_ready.emit()

    @Slot(str)
    def on_stage_lines(self, selected_text: str):
        self.stage_lines_requested.emit(selected_text)
