from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextBrowser,
    QLineEdit,
    QLabel,
    QCompleter,
    QPlainTextEdit,
    QToolButton,
    QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt, QStringListModel, QEvent
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QKeyEvent, QTextCursor


class PyForgeConsole(QWidget):
    """A dedicated console for interacting with a PyForge agent."""

    command_entered = Signal(str)
    completion_requested = Signal(str)
    object_link_clicked = Signal(str)
    file_link_clicked = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.history = []
        self.history_index = -1

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.output_view = QTextBrowser()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(QFont("Consolas", 10))
        self.output_view.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        self.output_view.setOpenLinks(False)
        self.output_view.anchorClicked.connect(self.on_anchor_clicked)

        self.input_container = QWidget()
        input_container_layout = QHBoxLayout(self.input_container)
        input_container_layout.setContentsMargins(5, 5, 5, 5)
        input_container_layout.setSpacing(5)

        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Consolas", 10))
        self.input_line.setPlaceholderText("Enter a Python expression or /command...")
        self.input_line.setAcceptDrops(True)
        self.input_line.installEventFilter(self)

        self.multiline_input = QPlainTextEdit()
        self.multiline_input.setFont(QFont("Consolas", 10))
        self.multiline_input.setPlaceholderText(
            "Enter a Python script... (Ctrl+Enter to execute)"
        )
        self.multiline_input.setVisible(False)
        self.multiline_input.installEventFilter(self)
        self.multiline_input.setAcceptDrops(True)

        self.multiline_toggle_button = QToolButton()
        self.multiline_toggle_button.setText("⤓")
        self.multiline_toggle_button.setToolTip("Toggle Multi-line Mode")
        self.multiline_toggle_button.setCheckable(True)

        input_container_layout.addWidget(self.multiline_toggle_button)
        input_container_layout.addWidget(self.input_line)
        input_container_layout.addWidget(self.multiline_input)

        main_layout.addWidget(self.output_view)
        main_layout.addWidget(self.input_container)

        self.completer = QCompleter(self)
        self.completer_model = QStringListModel(self)
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.input_line.setCompleter(self.completer)

        self.prompt_format = self._create_format(QColor("#808080"))
        self.error_format = self._create_format(QColor("#ff6b68"))
        self.system_format = self._create_format(QColor("#78c379"))
        self.response_format = self._create_format(QColor("#c792ea"))
        self.primitive_formats = {
            "int": self._create_format(QColor("#B5CEA8")),
            "float": self._create_format(QColor("#B5CEA8")),
            "bool": self._create_format(QColor("#569CD6")),
            "str": self._create_format(QColor("#CE9178")),
        }
        self.link_format = self._create_format(QColor("#4E94D7"), underline=True)

        self.input_line.returnPressed.connect(self._on_single_line_command)
        self.multiline_toggle_button.toggled.connect(self.toggle_multiline_mode)
        self.set_input_enabled(False)

    def eventFilter(self, source, event):
        if source is self.input_line:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Up:
                    self.navigate_history(1)
                    return True
                elif event.key() == Qt.Key.Key_Down:
                    self.navigate_history(-1)
                    return True
                elif event.key() == Qt.Key.Key_Tab:
                    self.completion_requested.emit(self.input_line.text())
                    return True
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasText():
                    self.input_line.insert(event.mimeData().text())
                    return True
        elif source is self.multiline_input:
            if (
                event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Return
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier
            ):
                self._on_multi_line_command()
                return True
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasText():
                    self.multiline_input.insertPlainText(event.mimeData().text())
                    return True
        return super().eventFilter(source, event)

    def on_anchor_clicked(self, url):
        url_str = url.toString()
        if url_str.startswith("pyforge://inspect/"):
            path = url_str.replace("pyforge://inspect/", "")
            self.object_link_clicked.emit(path)
        elif url_str.startswith("file://"):
            parts = url_str.replace("file:///", "").replace("file://", "").split(":")
            if len(parts) >= 2:
                line_num_str = parts[-1]
                file_path = ":".join(parts[:-1])
                try:
                    self.file_link_clicked.emit(file_path, int(line_num_str))
                except (ValueError, IndexError):
                    print(f"[Console] Could not parse file link: {url_str}")

    def navigate_history(self, direction: int):
        if not self.history:
            return
        self.history_index += direction
        if self.history_index >= len(self.history):
            self.history_index = len(self.history) - 1
        elif self.history_index < 0:
            self.history_index = -1
            self.input_line.clear()
            return
        if 0 <= self.history_index < len(self.history):
            self.input_line.setText(self.history[self.history_index])

    def _create_format(self, color: QColor, underline=False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if underline:
            fmt.setFontUnderline(True)
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
        return fmt

    def _insert_text(self, text: str, fmt: QTextCharFormat, newline=False):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        if newline:
            cursor.insertBlock()
        self.output_view.ensureCursorVisible()

    def _insert_html(self, html: str):
        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self.output_view.ensureCursorVisible()

    def clear_log(self):
        self.output_view.clear()

    def log_prompt(self, text: str):
        self._insert_text(text, self.prompt_format, newline=True)

    def log_system(self, text: str):
        self._insert_text(text, self.system_format, newline=True)

    def log_error(self, text: str):
        self._insert_text(text, self.error_format, newline=True)

    def log_response(self, result: dict):

        if not isinstance(result, dict):
            self._insert_text(str(result), self.response_format, newline=True)
            return

        res_type = result.get("type")
        if res_type == "none":
            self.log_system("[OK]")
        elif res_type == "primitive":
            self._insert_text(
                result.get("value", ""),
                self.primitive_formats.get(result.get("kind"), self.response_format),
                newline=True,
            )
        elif res_type in ["collection", "instance", "reference"]:
            path = result.get("path", "")
            preview = result.get("preview", result.get("repr", "[Object]"))
            html = f'<a href="pyforge://inspect/{path}" style="color: #4E94D7; text-decoration: none;">{preview}</a>'
            self._insert_html(html)
            self._insert_text("", self.prompt_format)
        elif res_type == "traceback":
            self.log_traceback(result)
        else:
            self._insert_text(str(result), self.response_format, newline=True)

    def log_traceback(self, tb_data: dict):
        self._insert_text(
            f"{tb_data.get('error_type', 'Error')}: {tb_data.get('error_message', 'Unknown')}\n",
            self.error_format,
        )
        for frame in reversed(tb_data.get("frames", [])):
            file, line, func = (
                frame.get("file"),
                frame.get("line"),
                frame.get("function"),
            )
            if file and line and func:
                if file == "<pyforge_console>":
                    html = f'  File "<font color="#808080">{file}</font>", line {line}, in {func}<br>'
                else:
                    html = f'  File "<a href="file://{file}:{line}" style="color: #4E94D7; text-decoration: none;">{file}</a>", line {line}, in {func}<br>'
                self._insert_html(html)

    def _on_single_line_command(self):
        command = self.input_line.text().strip()
        if command:
            self._process_command(command)
            self.input_line.clear()

    def _on_multi_line_command(self):
        command = self.multiline_input.toPlainText().strip()
        if command:
            self._process_command(command)
            self.multiline_input.clear()

    def _process_command(self, command: str):
        self.log_prompt(f">>> {command}")
        if not self.history or self.history[-1] != command:
            self.history.append(command)
        self.history_index = len(self.history)
        self.command_entered.emit(command)

    def set_input_enabled(self, enabled: bool):
        self.input_line.setEnabled(enabled)
        self.multiline_input.setEnabled(enabled)
        placeholder = (
            "Enter a Python expression or /command..."
            if enabled
            else "No active PyForge session."
        )
        self.input_line.setPlaceholderText(placeholder)
        self.multiline_input.setPlaceholderText(
            placeholder.replace("...", " script... (Ctrl+Enter to execute)")
        )

    def toggle_multiline_mode(self, checked: bool):
        self.input_line.setVisible(not checked)
        self.multiline_input.setVisible(checked)
        self.multiline_toggle_button.setText("⤒" if checked else "⤓")
        if checked:
            self.multiline_input.setFocus()
        else:
            self.input_line.setFocus()

    def update_completions(self, completions: list):
        self.completer_model.setStringList(completions)
        self.completer.complete()
