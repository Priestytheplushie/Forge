import time
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QFrame,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QTextBrowser,
    QPushButton,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import Slot, Signal, QModelIndex, Qt

from ...assets.icon_map import get_status_icon, get_audit_log_icon
from .audit_log_model import AuditLogItem
from .audit_log_delegate import AuditLogDelegate
from .audit_log_filter_model import AuditLogFilterProxyModel


class ExceptionWidget(QWidget):
    """A custom widget to display detailed exception info in the tree."""

    goto_requested = Signal()
    fix_requested = Signal()

    def __init__(self, log_data: dict, controller, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(5)

        payload = log_data.get("outcome", {}).get("payload", {})
        error_msg = payload.get("error_message", "An unknown error occurred.")

        msg_label = QLabel(error_msg)
        msg_label.setWordWrap(True)

        tb_browser = QTextBrowser()
        tb_browser.setReadOnly(True)
        tb_browser.setOpenLinks(False)

        if controller:
            tb_browser.anchorClicked.connect(controller.on_file_link_clicked)
        tb_browser.setFixedHeight(100)
        tb_browser.setStyleSheet(
            "background-color: #2E3440; border: 1px solid #434C5E;"
        )

        html = ""
        frames = payload.get("frames", [])
        for frame in reversed(frames):
            file, line, func = (
                frame.get("file"),
                frame.get("line"),
                frame.get("function"),
            )
            if file and line and func:
                if file == "<pyforge_console>":
                    html += f'  File "<font color="#808080">{file}</font>", line {line}, in {func}<br>'
                else:
                    html += f'  File "<a href="file://{file}:{line}" style="color: #4E94D7; text-decoration: none;">{file}</a>", line {line}, in {func}<br>'
        tb_browser.setHtml(
            f"<pre style='color: #D8DEE9; font-family: Consolas, monaco, monospace;'>{html}</pre>"
        )

        button_layout = QHBoxLayout()
        goto_button = QPushButton("Goto")
        goto_button.setToolTip(
            "Recall the original command or go to the source of the error."
        )
        fix_button = QPushButton("Fix")
        fix_button.setToolTip(
            "Attempt to automatically fix this exception (Feature coming soon)."
        )
        fix_button.setEnabled(False)
        button_layout.addWidget(goto_button)
        button_layout.addWidget(fix_button)
        button_layout.addStretch()

        layout.addWidget(msg_label)
        layout.addWidget(tb_browser)
        layout.addLayout(button_layout)

        goto_button.clicked.connect(self.goto_requested)
        fix_button.clicked.connect(self.fix_requested)


class AuditLogPanel(QWidget):
    revert_requested = Signal(dict)
    goto_requested = Signal(dict)

    file_link_clicked = Signal(str, int)

    def __init__(self, pyforge_controller, parent=None):
        super().__init__(parent)
        self.pyforge_controller = pyforge_controller
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("PyForgePanelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.addWidget(QLabel("Audit Log"))
        main_layout.addWidget(header)

        filter_bar = QWidget()
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(5, 2, 5, 2)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter log entries...")
        self.filter_edit.setClearButtonEnabled(True)
        filter_layout.addWidget(self.filter_edit)
        main_layout.addWidget(filter_bar)

        self.log_tree = QTreeView()
        self.log_tree.setHeaderHidden(True)
        self.log_tree.setWordWrap(True)
        self.delegate = AuditLogDelegate(self.log_tree)
        self.log_tree.setItemDelegate(self.delegate)
        self.source_model = QStandardItemModel()
        self.proxy_model = AuditLogFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self.log_tree.setModel(self.proxy_model)

        self.log_tree.doubleClicked.connect(self.on_item_double_clicked)
        self.filter_edit.textChanged.connect(
            self.proxy_model.setFilterRegularExpression
        )

        main_layout.addWidget(self.log_tree)
        self.clear_log()

    @Slot()
    def clear_log(self):
        self.source_model.clear()
        placeholder = QStandardItem("No actions have been logged in this session.")
        placeholder.setEnabled(False)
        self.source_model.appendRow(placeholder)

    def _create_child_node(
        self, parent_item, icon, text, data=None, item_type=None
    ) -> AuditLogItem:
        child_item = AuditLogItem(icon, text) if icon else AuditLogItem(text)
        child_item.setEditable(False)
        child_item.full_data = data or {}
        child_item.item_type = item_type
        parent_item.appendRow(child_item)
        return child_item

    @Slot(dict)
    def add_log_entry(self, log_data: dict):
        if (
            self.source_model.rowCount() == 1
            and not self.source_model.item(0).isEnabled()
        ):
            self.source_model.clear()

        action_type = log_data.get("type", "UnknownAction")
        timestamp = log_data.get("timestamp", 0)
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp / 1000))

        title = self._get_log_title(log_data)
        icon = get_audit_log_icon(action_type)
        root_item = AuditLogItem(icon, f"{time_str} | {title}")
        root_item.setEditable(False)
        root_item.full_data = log_data
        root_item.item_type = "log_root"
        root_item.setToolTip(f"Action: {action_type}\nID: {log_data.get('action_id')}")

        explanation_text = self._get_explanation(log_data)
        if explanation_text:
            explain_node = self._create_child_node(
                root_item,
                get_status_icon("help-circle"),
                "Explain",
                log_data,
                "explain_header",
            )
            explain_node.setToolTip(
                "An explanation of what this action does and its implications."
            )
            self._create_child_node(
                explain_node, None, explanation_text, item_type="explanation_text"
            )

        actions_node = self._create_child_node(
            root_item, get_status_icon("tool"), "Actions", log_data, "actions_header"
        )
        actions_node.setToolTip(
            "Interactive actions you can take based on this log entry."
        )
        actions_added = False

        revert_text = self._get_revert_text(log_data)
        if revert_text:
            revert_node = self._create_child_node(
                actions_node,
                get_status_icon("rotate-ccw"),
                revert_text,
                log_data,
                "revert",
            )
            revert_node.setToolTip(
                "Double-click to revert this action in the live application."
            )
            actions_added = True

        details_node = self._create_child_node(
            root_item, get_status_icon("info"), "Details", log_data, "details_header"
        )
        details_node.setToolTip("Metadata about this log entry.")
        self._create_child_node(details_node, None, f"Timestamp: {timestamp}")
        action_id_node = self._create_child_node(
            details_node, None, "Action ID:", log_data, "action_id_header"
        )
        self._create_child_node(action_id_node, None, log_data.get("action_id"))

        if log_data.get("source"):
            source_node = self._create_child_node(
                root_item,
                get_status_icon("log-out"),
                "Source",
                log_data,
                "source_header",
            )
            source_node.setToolTip("Where the action originated from in the UI.")
            for key, value in log_data["source"].items():
                self._create_child_node(
                    source_node, None, f"{key.replace('_', ' ').capitalize()}: {value}"
                )
        if log_data.get("target"):
            target_node = self._create_child_node(
                root_item,
                get_status_icon("crosshair"),
                "Target",
                log_data,
                "target_header",
            )
            target_node.setToolTip("The object or module this action was performed on.")
            for key, value in log_data["target"].items():
                if value:
                    self._create_child_node(
                        target_node,
                        None,
                        f"{key.replace('_', ' ').capitalize()}: {value}",
                    )

        outcome = log_data.get("outcome")
        if outcome:
            outcome_node = self._create_child_node(
                root_item,
                get_status_icon("log-in"),
                "Outcome",
                log_data,
                "outcome_header",
            )
            outcome_node.setToolTip("The result received from the agent.")
            payload = outcome.get("payload")
            status = outcome.get("status")
            if status == "success":
                self._create_child_node(
                    outcome_node,
                    get_status_icon("check-circle", "#73C991"),
                    f"Success: {str(payload)[:100]}",
                )
            else:
                error_type = payload.get("error_type", "Error")
                exc_node = self._create_child_node(
                    outcome_node,
                    get_status_icon("alert-triangle", "#BF616A"),
                    f"Exception: {error_type}",
                    item_type="exception_header",
                )

                exc_widget = ExceptionWidget(log_data, self.pyforge_controller, self)
                exc_widget.goto_requested.connect(
                    lambda d=log_data: self.goto_requested.emit(d)
                )
                self.log_tree.setIndexWidget(exc_node.index(), exc_widget)
                self._create_child_node(
                    actions_node, get_status_icon("code"), "Goto", log_data, "goto"
                ).setToolTip("Recall the command that caused this error.")
                actions_added = True

        if not actions_added:
            actions_node.setEnabled(False)

        self.source_model.insertRow(0, root_item)

    def _get_log_title(self, data):
        type, source = data.get("type"), data.get("source", {})
        if type == "AttributeChange":
            path = data.get("target", {}).get("path", "?.?")
            attr = path.split(".")[-1]
            val = source.get("input", "?")
            return f"Set '{attr}' = {val}"
        elif type == "ConsoleCommand":
            cmd = source.get("command", "")
            return f"Console: {cmd[:50]}" + ("..." if len(cmd) > 50 else "")
        elif type == "FunctionCall":
            path = data.get("target", {}).get("path", "?")
            name = path.split(".")[-1]
            args = data.get("details", {}).get("args", [])
            kwargs = data.get("details", {}).get("kwargs", {})
            arg_str = ", ".join(map(str, args))
            kwarg_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            if arg_str and kwarg_str:
                full_args = f"{arg_str}, {kwarg_str}"
            else:
                full_args = arg_str or kwarg_str
            return f"Call: {name}({full_args})"
        return type

    def _get_explanation(self, data):
        explanations = {
            "AttributeChange": "This action modified an attribute of a live object. This is a direct memory mutation and will not persist if the application is restarted.",
            "FunctionCall": "This action executed a function or method on a live object.",
            "InstanceCreation": "This action created a new instance of a class in the target application's memory.",
            "DeleteObject": "This action removed a live object from memory. This can cause instability if other parts of the application still hold a reference to it.",
            "HotReload": "This action replaced a live Python module with new source code. Existing instances of classes from this module are not automatically updated.",
            "ReloadMasterScript": "This action reloaded the `master.pfscript` file in the agent, updating hooks and custom metrics.",
        }
        return explanations.get(data.get("type"))

    def _get_revert_text(self, data):
        type = data.get("type")
        if type == "AttributeChange":
            old_val = data.get("outcome", {}).get("old_value", "?")
            attr = data.get("target", {}).get("path", "?.?").split(".")[-1]
            return f"Revert '{attr}' back to {old_val}"
        elif type == "DeleteObject":
            return "Restore Object"
        return None

    @Slot(QModelIndex)
    def on_item_double_clicked(self, index: QModelIndex):
        source_index = self.proxy_model.mapToSource(index)
        item = self.source_model.itemFromIndex(source_index)
        if not isinstance(item, AuditLogItem):
            return

        if item.item_type == "revert":
            self.revert_requested.emit(item.full_data)
        elif item.item_type == "goto":
            self.goto_requested.emit(item.full_data)
