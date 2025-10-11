import sys
import os
import shutil
import ast
from pathlib import Path
from PySide6.QtCore import QObject, Slot, QTimer, QDir, QStringListModel, QModelIndex
from PySide6.QtWidgets import (
    QMessageBox,
    QApplication,
    QFileDialog,
    QCompleter,
    QInputDialog,
    QTreeView,
)
from PySide6.QtGui import QColor, QPixmap
import pprint
import importlib
import inspect

from ..windows.function_runner_dialog import FunctionRunnerDialog
from ..windows.object_browser_legend_dialog import ObjectBrowserLegendDialog
from ..windows.inspector_dialog import InspectorDialog
from ..windows.metric_creator_dialog import MetricCreatorDialog
from ..windows.snippet_editor_dialog import SnippetEditorDialog
from ..windows.add_hook_dialog import AddHookDialog
from ..components.pyforge.toast_notification import ToastNotification
from ..components.pyforge.script_editor import PyForgeScriptEditor
from ..windows.action_confirmation_dialog import ActionConfirmationDialog
from ...backend.pyforge.audit_logger import AuditLogger
from ..assets.icon_map import get_pyforge_icon
from ..utils import uri_to_path


class PyForgeController(QObject):
    def __init__(self, main_window, pyforge_manager):
        super().__init__(main_window)
        self.main_window = main_window
        self.pyforge_manager = pyforge_manager
        self.audit_logger = AuditLogger(self)
        self.workspace_path = None
        self.pending_requests = {}
        self.tray_icon = None
        self.injection_worker = None
        self.pending_refresh_expansion_state = None

        self.pyforge_manager.set_main_window(self.main_window)
        self.toast = ToastNotification(
            self.main_window.pyforge_active_panel.object_browser.tree_view
        )

        self.script_storage_path = Path(main_window.app_root) / ".forge" / "scripts"
        self.script_storage_path.mkdir(parents=True, exist_ok=True)
        self.workspace_script_path = None

        self.watched_classes = set()
        self.latest_system_metrics = {}
        self.latest_agent_metrics = {}

        self.all_hook_definitions = {
            "on_tick": {
                "template": 'def on_tick():\n    """Runs on every agent heartbeat (approx. every 2 seconds)."""\n    pass',
                "docstring": "Runs on every agent heartbeat (approx. every 2 seconds).",
            },
            "on_new_instance": {
                "template": 'def on_new_instance(instance, class_name):\n    """Runs when a new instance of a watched class is created."""\n    pass',
                "docstring": "Runs when a new instance of a watched class is created.",
            },
            "on_agent_connect": {
                "template": 'def on_agent_connect():\n    """Runs when the UI connects to the agent."""\n    pass',
                "docstring": "Runs when the UI connects to the agent.",
            },
            "on_agent_disconnect": {
                "template": 'def on_agent_disconnect():\n    """Runs when the UI disconnects from the agent."""\n    pass',
                "docstring": "Runs when the UI disconnects from the agent.",
            },
            "on_script_start": {
                "template": 'def on_script_start():\n    """Runs when the user\'s main Python script begins execution."""\n    pass',
                "docstring": "Runs when the user's main Python script begins execution.",
            },
            "on_script_end": {
                "template": 'def on_script_end():\n    """Runs when the user\'s script finishes or terminates."""\n    pass',
                "docstring": "Runs when the user's script finishes or terminates.",
            },
            "on_exception": {
                "template": 'def on_exception(exc, tb_dict):\n    """Runs when an unhandled exception occurs in the target script."""\n    pass',
                "docstring": "Runs when an unhandled exception occurs in the target script.",
            },
            "on_event": {
                "template": 'def on_event(name, value):\n    """Runs when a custom event is fired via pf.fire_event()."""\n    pass',
                "docstring": "Runs when a custom event is fired via pf.fire_event().",
            },
            "on_metric_update": {
                "template": 'def on_metric_update(metric_path, new_value, old_value):\n    """Runs when any metric\'s value changes."""\n    pass',
                "docstring": "Runs when any metric's value changes.",
            },
        }

    def set_tray_icon(self, tray_icon):
        self.tray_icon = tray_icon

    def set_workspace_path(self, path: str):
        self.workspace_path = path
        self.workspace_script_path = None

    def init_connections(self):

        self.pyforge_manager.status_changed.connect(self.on_status_changed)
        self.pyforge_manager.system_metrics_updated.connect(
            self.on_system_metrics_update
        )
        self.pyforge_manager.client.response_received.connect(self.on_response_received)
        self.pyforge_manager.session_started.connect(self.on_session_started)
        self.pyforge_manager.session_stopped.connect(self.on_session_stopped)
        self.pyforge_manager.client.log_received.connect(self.on_agent_log)
        self.pyforge_manager.client.subscription_update_received.connect(
            self.on_subscription_update
        )
        self.pyforge_manager.client.new_instance_received.connect(self.on_new_instance)
        self.pyforge_manager.client.status_update_received.connect(
            self.on_agent_status_update
        )
        self.pyforge_manager.client.disconnected.connect(
            self.audit_logger.finalize_pending_as_crashed
        )

        self.audit_logger.log_entry_added.connect(
            self.main_window.pyforge_active_panel.audit_log_panel.add_log_entry
        )

        self.main_window.debug_view.pyforge_launch_view.launch_requested.connect(
            self.on_launch_requested
        )
        self.main_window.pyforge_console.command_entered.connect(
            self.on_command_entered
        )
        self.main_window.pyforge_console.completion_requested.connect(
            self.on_completion_requested
        )
        self.main_window.pyforge_console.object_link_clicked.connect(
            self.on_object_link_clicked
        )
        self.main_window.pyforge_console.file_link_clicked.connect(
            self.on_file_link_clicked
        )

        active_panel = self.main_window.pyforge_active_panel
        active_panel.stop_requested.connect(self.pyforge_manager.stop_session)
        active_panel.audit_log_panel.revert_requested.connect(self.on_revert_requested)
        active_panel.audit_log_panel.goto_requested.connect(self.on_goto_requested)

        session_panel = active_panel.session_panel
        session_panel.create_master_script_requested.connect(
            self.on_create_master_script_from_prompt
        )
        session_panel.refresh_master_script_requested.connect(
            self.on_refresh_master_script_view
        )
        manager_tree = session_panel.master_script_manager
        manager_tree.edit_in_text_requested.connect(self.on_edit_in_text_requested)
        manager_tree.add_hook_requested.connect(self.on_add_hook)
        manager_tree.add_override_requested.connect(self.on_add_override)
        manager_tree.add_snippet_requested.connect(self.on_add_snippet)
        manager_tree.attach_new_script_requested.connect(self.on_attach_new_script)
        manager_tree.attach_existing_script_requested.connect(
            self.on_attach_existing_script
        )
        manager_tree.remove_script_requested.connect(self.on_remove_script)
        manager_tree.inline_script_requested.connect(self.on_inline_script)

        browser = active_panel.object_browser
        browser.refresh_requested.connect(self.on_discover_requested)
        browser.discover_requested.connect(self.on_get_details_requested)
        browser.collapse_requested.connect(browser.tree_view.collapseAll)
        browser.model.attribute_changed.connect(self.on_attribute_changed)
        browser.run_requested.connect(self.on_run_requested)
        browser.create_instance_requested.connect(self.on_create_instance_requested)
        browser.subscribe_requested.connect(self.on_subscribe_requested)
        browser.unsubscribe_requested.connect(self.on_unsubscribe_requested)
        browser.copy_reference_requested.connect(self.on_copy_reference)
        browser.inspect_requested.connect(self.on_inspect_requested)
        browser.delete_requested.connect(self.on_delete_requested)
        browser.watch_requested.connect(self.on_watch_requested)
        browser.show_legend_requested.connect(self.on_show_legend)

        active_panel.metrics_panel.create_event_script_requested.connect(
            self.on_create_metric_event_script
        )

        self.main_window.file_explorer.new_script_requested.connect(self.on_new_script)
        self.main_window.file_explorer.script_double_clicked.connect(
            self.on_open_script
        )
        self.main_window.file_explorer.rename_script_requested.connect(
            self.on_rename_script
        )
        self.main_window.file_explorer.delete_script_requested.connect(
            self.on_delete_script
        )
        self.main_window.file_explorer.duplicate_script_requested.connect(
            self.on_duplicate_script
        )
        self.main_window.file_explorer.move_script_requested.connect(
            self.on_move_script
        )

        self.main_window.pyforge_active_panel.tab_widget.currentChanged.connect(
            self.on_tab_changed
        )
        self.main_window.hot_reload_button.clicked.connect(self.on_hot_reload_requested)
        self.main_window.validate_reload_button.clicked.connect(
            self.on_validate_reload_clicked
        )

        self.main_window.file_manager.file_saved.connect(self.on_file_saved)

    def shutdown(self):
        self.pyforge_manager.stop_session()

    @Slot(dict)
    def on_revert_requested(self, log_data: dict):
        action_type = log_data.get("type")
        if action_type == "AttributeChange":
            path = log_data.get("target", {}).get("path")
            old_value = log_data.get("outcome", {}).get("old_value", "None")
            if path:
                message = f"This will execute a command to revert the attribute change:\n\n`setattr(..., {old_value})`\n\nAre you sure?"
                dialog = ActionConfirmationDialog(
                    "Confirm Revert", message, "Revert", self.main_window
                )
                if dialog.exec():
                    self.on_attribute_changed(path, old_value, None)
        elif action_type == "DeleteObject":
            object_id = log_data.get("outcome", {}).get("id")
            if object_id:
                message = f"This will attempt to restore the deleted object (ID: {object_id}) from the agent's trash.\n\nThis may fail if all references have been garbage collected. Continue?"
                dialog = ActionConfirmationDialog(
                    "Confirm Restore", message, "Restore", self.main_window
                )
                if dialog.exec():
                    self.on_restore_requested(object_id)

    @Slot(dict)
    def on_goto_requested(self, log_data: dict):
        action_type = log_data.get("type")
        if action_type == "ConsoleCommand":
            command = log_data.get("source", {}).get("command")
            if command:
                self.main_window.pyforge_console.input_line.setText(command)
                self.main_window.pyforge_console.input_line.setFocus()

    @Slot()
    def on_show_legend(self):
        dialog = ObjectBrowserLegendDialog(self.main_window)
        dialog.exec()

    @Slot(bool)
    def on_new_script(self, is_global: bool):
        start_dir = self.script_storage_path if is_global else self.workspace_path
        if not start_dir:
            QMessageBox.warning(
                self.main_window,
                "No Workspace",
                "Please open a workspace to create a workspace script.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Create New PyForge Script",
            str(Path(start_dir) / "new_script.pfscript"),
            "PyForge Scripts (*.pfscript)",
        )

        if not file_path:
            return

        content = "import pf\n\npf.log('Hello from script!')\n"

        try:
            Path(file_path).write_text(content, encoding="utf-8")
            self.main_window.file_manager.open_file_from_path(file_path)
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not create new script file: {e}"
            )

    def on_open_script(self, file_path: str):
        self.main_window.file_manager.open_file_from_path(file_path)

    def on_run_script_button_pressed(self, action=None):
        editor = self.main_window.get_current_editor()
        if isinstance(editor, PyForgeScriptEditor):
            editor.get_text(self.on_get_text_for_run_script)

    def on_get_text_for_run_script(self, script_content: str):
        if script_content:
            log_entry = self.audit_logger.begin_action(
                action_type="ScriptExecution",
                source={"component": "Editor Toolbar"},
                details={
                    "script_content": (
                        script_content[:500] + "..."
                        if len(script_content) > 500
                        else script_content
                    )
                },
            )
            req_id = self.pyforge_manager.client.execute_script(script_content)
            if req_id != -1:
                self.pending_requests[req_id] = (
                    self._handle_script_response,
                    log_entry,
                )
                self.audit_logger.associate_action(req_id, log_entry)

    @Slot()
    def on_launch_requested(self):
        if not self.workspace_path:
            return
        editor = self.main_window.get_current_editor()
        if not editor or not editor.property("file_path"):
            return
        file_path = editor.property("file_path")
        if not file_path.endswith(".py"):
            return

        self.main_window.view_manager.set_view("Debug")
        self.main_window.debug_view.tab_widget.setCurrentIndex(1)
        self.main_window.pyforge_console.clear_log()
        self.main_window.pyforge_console_dock.raise_()

        pyforge_terminal = self.main_window.terminal.create_new_terminal(
            "PyForge Session"
        )
        if not pyforge_terminal:
            return

        self.main_window.terminal_dock.raise_()
        self.pyforge_manager.launch(sys.executable, file_path, pyforge_terminal)

    @Slot(str)
    def on_command_entered(self, command: str):
        log_entry = self.audit_logger.begin_action(
            action_type="ConsoleCommand",
            source={"component": "PyForge Console", "command": command},
        )
        if command.startswith("/"):
            self.parse_and_execute_slash_command(command)
            self.audit_logger.finalize_action(
                log_entry, {"status": "success", "payload": "Local command executed."}
            )
        else:
            req_id = self.pyforge_manager.client.send_command(command)
            if req_id != -1:
                self.pending_requests[req_id] = (
                    self._handle_console_response,
                    log_entry,
                )
                self.audit_logger.associate_action(req_id, log_entry)

    def parse_and_execute_slash_command(self, command: str):
        parts = command.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            self.main_window.pyforge_console.log_system(
                "Available Commands:\n"
                "/run <script_name>   - Run a .pfscript from your workspace or global scripts.\n"
                "/watch <class_name>  - Start watching for new instances of a class.\n"
                "/clear               - Clear the console output.\n"
                "/history             - Show command history.\n"
                "/help                - Show this help message."
            )
        elif cmd == "/clear":
            self.main_window.pyforge_console.clear_log()
        elif cmd == "/history":
            history_text = "\n".join(self.main_window.pyforge_console.history)
            self.main_window.pyforge_console.log_system(
                f"Command History:\n{history_text}"
            )
        elif cmd == "/watch" and args:
            class_name = args[0]
            log_entry = self.audit_logger.begin_action(
                action_type="WatchClass",
                source={"component": "Console Command"},
                target={"class_name": class_name},
            )
            req_id = self.pyforge_manager.client.send_command(
                f"pf.watch(pf.get('{class_name}'))"
            )
            if req_id != -1:
                self.pending_requests[req_id] = (
                    self._handle_console_response,
                    log_entry,
                )
                self.audit_logger.associate_action(req_id, log_entry)
        elif cmd == "/run" and args:
            script_name = args[0]
            if not script_name.endswith(".pfscript"):
                script_name += ".pfscript"

            script_path = None
            if self.workspace_path:
                found_scripts = list(
                    Path(self.workspace_path).rglob(f"**/{script_name}")
                )
                if found_scripts:
                    script_path = found_scripts[0]

            if not script_path:
                script_path = self.script_storage_path / script_name

            if script_path and script_path.exists():
                try:
                    content = script_path.read_text(encoding="utf-8")
                    self.on_get_text_for_run_script(content)
                except Exception as e:
                    self.main_window.pyforge_console.log_response(
                        {
                            "type": "traceback",
                            "error_type": "ScriptError",
                            "error_message": f"Could not read script '{script_name}': {e}",
                            "frames": [],
                        }
                    )
            else:
                self.main_window.pyforge_console.log_response(
                    {
                        "type": "traceback",
                        "error_type": "ScriptError",
                        "error_message": f"Script '{script_name}' not found in workspace or global scripts.",
                        "frames": [],
                    }
                )

        else:
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "CommandError",
                    "error_message": f"Unknown or invalid slash command: {command}",
                    "frames": [],
                }
            )

    @Slot(str)
    def on_completion_requested(self, text: str):
        if text.startswith("/run "):
            prefix = text.split(" ", 1)[1]
            completions = []
            if self.workspace_path:
                for p in Path(self.workspace_path).rglob(f"**/{prefix}*.pfscript"):
                    completions.append(f"/run {p.name}")
            for p in self.script_storage_path.glob(f"{prefix}*.pfscript"):
                completions.append(f"/run {p.name}")
            self.main_window.pyforge_console.update_completions(list(set(completions)))
        elif not text.startswith("/"):
            req_id = self.pyforge_manager.client.get_completions(text)
            self.pending_requests[req_id] = (self._handle_completions_response, None)

    @Slot(int)
    def on_tab_changed(self, index):
        if self.main_window.pyforge_active_panel.tab_widget.tabText(index) == "Objects":
            browser = self.main_window.pyforge_active_panel.object_browser
            if browser.model.rowCount(QModelIndex()) == 0:
                self.on_discover_requested()

    @Slot()
    def on_hot_reload_requested(self):
        editor = self.main_window.get_current_editor()
        if not editor:
            return

        file_path_str = self.main_window.file_manager.open_file_paths.get(editor)
        if not file_path_str:
            return

        file_path = Path(file_path_str)

        if self.pyforge_manager.active_script_path and os.path.samefile(
            file_path_str, self.pyforge_manager.active_script_path
        ):
            module_name = "__main__"
        else:
            module_name = None
            if self.workspace_path:
                workspace = Path(self.workspace_path)
                try:
                    rel_path = file_path.relative_to(workspace)
                    module_name = ".".join(rel_path.parts).replace(".py", "")
                except ValueError:
                    pass
            if not module_name:
                module_name = file_path.stem

        reply = QMessageBox.question(
            self.main_window,
            "Confirm Hot Reload",
            f"Are you sure you want to reload the module '{module_name}' in the live application?\n\n"
            "Warning: This updates class and function definitions, but existing object instances will NOT be automatically updated. "
            "You may need to use `pf.migrate_instance()` or `pf.copy_state()` in a script to update them.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            editor.get_text(
                lambda source: self._send_hot_reload_request(module_name, source)
            )

    def _send_hot_reload_request(self, module_name: str, new_source: str):
        if new_source is None:
            return
        log_entry = self.audit_logger.begin_action(
            action_type="HotReload",
            source={"component": "Editor Toolbar"},
            target={"module_name": module_name},
        )
        req_id = self.pyforge_manager.client.hot_reload_module(module_name, new_source)
        if req_id != -1:
            self.pending_requests[req_id] = (
                self._handle_hot_reload_response,
                log_entry,
            )
            self.audit_logger.associate_action(req_id, log_entry)

    @Slot()
    def on_discover_requested(self):
        if not self.workspace_path:
            return
        browser = self.main_window.pyforge_active_panel.object_browser
        self.pending_refresh_expansion_state = browser.get_expansion_state()
        req_id = self.pyforge_manager.client.discover_roots(self.workspace_path)
        if req_id != -1:
            self.pending_requests[req_id] = (self._handle_discover_response, None)

    @Slot(str, object)
    def on_get_details_requested(self, path: str, parent_item):
        req_id = self.pyforge_manager.client.get_details(path)
        if req_id != -1:
            QTimer.singleShot(
                2000, lambda: self._handle_details_timeout(req_id, parent_item)
            )
            self.pending_requests[req_id] = (
                lambda data: self._handle_get_details_response(data, parent_item),
                None,
            )

    def _handle_details_timeout(self, req_id, parent_item):
        if req_id in self.pending_requests:
            self.pending_requests.pop(req_id, None)
            self.main_window.pyforge_active_panel.object_browser.model.update_children(
                parent_item, []
            )

    @Slot(str, str, object)
    def on_attribute_changed(self, path: str, new_value_str: str, item):
        log_entry = self.audit_logger.begin_action(
            action_type="AttributeChange",
            source={"component": "Object Browser", "input": new_value_str},
            target={"path": path},
        )
        req_id = self.pyforge_manager.client.set_attribute(path, new_value_str)
        if req_id != -1:
            self.pending_requests[req_id] = (
                lambda data: self._handle_set_attribute_response(data, item),
                log_entry,
            )
            self.audit_logger.associate_action(req_id, log_entry)

    @Slot(object)
    def on_run_requested(self, item):
        req_id = self.pyforge_manager.client.get_all_known_objects()
        if req_id != -1:
            self.pending_requests[req_id] = (
                lambda objects: self._show_function_runner(item, objects),
                None,
            )

    def _show_function_runner(self, item, all_objects):
        params = item.full_data.get("params", [])
        docstring = item.full_data.get("doc", "")

        dialog = FunctionRunnerDialog(
            item.full_data["name"], params, docstring, all_objects, self.main_window
        )
        dialog.run_requested.connect(
            lambda args, kwargs, var_name: self.on_run_confirmed(
                item.node_path, args, kwargs
            )
        )
        dialog.exec()

    @Slot(object)
    def on_create_instance_requested(self, item):
        class_path_data = item.node_path.split(":", 1)[1]
        method_group_path = f"method_group:{class_path_data}"
        req_id = self.pyforge_manager.client.get_details(method_group_path)
        if req_id != -1:
            self.pending_requests[req_id] = (
                lambda method_details: self._show_create_instance_dialog(
                    item, method_details
                ),
                None,
            )

    def _show_create_instance_dialog(self, class_item, method_details):
        init_method = None
        for detail in method_details:
            if detail.get("name", "").startswith("__init__"):
                init_method = detail
                break

        params = init_method.get("params", []) if init_method else []
        class_doc = class_item.full_data.get("doc", "")
        init_doc = init_method.get("doc", "") if init_method else ""
        if init_doc and "Initialize self" in init_doc:
            init_doc = ""
        docstring = init_doc or class_doc or "Create a new instance of this class."
        req_id = self.pyforge_manager.client.get_all_known_objects()
        if req_id != -1:
            self.pending_requests[req_id] = (
                lambda objects: self._show_constructor_runner(
                    class_item, params, docstring, objects
                ),
                None,
            )

    def _show_constructor_runner(self, class_item, params, docstring, all_objects):
        class_name = class_item.full_data["name"]
        dialog = FunctionRunnerDialog(
            f"new {class_name}", params, docstring, all_objects, self.main_window
        )
        dialog.run_requested.connect(
            lambda args, kwargs, var_name: self.on_create_instance_confirmed(
                class_item.node_path, var_name, args, kwargs
            )
        )
        dialog.exec()

    def on_create_instance_confirmed(
        self, class_path, variable_name: str, args: list, kwargs: dict
    ):
        log_entry = self.audit_logger.begin_action(
            action_type="InstanceCreation",
            source={"component": "Object Browser"},
            target={"class_path": class_path},
            details={"variable_name": variable_name, "args": args, "kwargs": kwargs},
        )
        req_id = self.pyforge_manager.client.create_instance(
            class_path, variable_name, args, kwargs
        )
        if req_id != -1:
            self.pending_requests[req_id] = (
                self._handle_create_instance_response,
                log_entry,
            )
            self.audit_logger.associate_action(req_id, log_entry)

    def on_run_confirmed(self, path: str, args: list, kwargs: dict):
        log_entry = self.audit_logger.begin_action(
            action_type="FunctionCall",
            source={"component": "Object Browser"},
            target={"path": path},
            details={"args": args, "kwargs": kwargs},
        )
        resolved_args, resolved_kwargs = [], {}
        for arg in args:
            resolved_args.append(
                f"pf.get('{arg.split(':')[-1]}')"
                if isinstance(arg, str) and arg.startswith("pf:instance:")
                else arg
            )
        for k, v in kwargs.items():
            resolved_kwargs[k] = (
                f"pf.get('{v.split(':')[-1]}')"
                if isinstance(v, str) and v.startswith("pf:instance:")
                else v
            )
        req_id = self.pyforge_manager.client.execute_callable(
            path, resolved_args, resolved_kwargs
        )
        if req_id != -1:
            self.pending_requests[req_id] = (self._handle_console_response, log_entry)
            self.audit_logger.associate_action(req_id, log_entry)

    @Slot(str, bool)
    def on_subscribe_requested(self, path: str, is_pinned: bool):
        self.pyforge_manager.client.subscribe(path, is_pinned)
        item = self.main_window.pyforge_active_panel.object_browser.model.item_map.get(
            path
        )
        if item:
            item.is_pinned = is_pinned

    @Slot(str)
    def on_unsubscribe_requested(self, path: str):
        self.pyforge_manager.client.unsubscribe(path)

    @Slot(str)
    def on_copy_reference(self, path: str):
        QApplication.clipboard().setText(path)
        self.main_window.pyforge_console.log_system(f"Copied '{path}' to clipboard.\n")

    @Slot(object)
    def on_inspect_requested(self, item):
        req_id = self.pyforge_manager.client.deep_inspect(item.node_path)
        if req_id != -1:
            self.pending_requests[req_id] = (self._handle_inspect_response, None)

    @Slot(object)
    def on_delete_requested(self, item):
        path = item.node_path
        reply = QMessageBox.warning(
            self.main_window,
            "Delete Object",
            f"Are you sure you want to delete this object?\n\n{item.text()}\n\nThis may cause the application to crash if other objects still reference it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            log_entry = self.audit_logger.begin_action(
                action_type="DeleteObject",
                source={"component": "Object Browser"},
                target={"path": path},
            )
            req_id = self.pyforge_manager.client.delete_object(path)
            if req_id != -1:
                self.pending_requests[req_id] = (
                    lambda data: self._handle_delete_response(data, item),
                    log_entry,
                )
                self.audit_logger.associate_action(req_id, log_entry)

    @Slot(str, bool, bool)
    def on_watch_requested(
        self, class_path_with_prefix: str, watching: bool, from_user: bool
    ):
        class_path = class_path_with_prefix.partition(":")[-1]
        action = "unwatch" if watching else "watch"
        if not from_user and action == "watch" and class_path in self.watched_classes:
            return

        log_entry = self.audit_logger.begin_action(
            action_type="WatchClass" if action == "watch" else "UnwatchClass",
            source={"component": "Object Browser"},
            target={"class_path": class_path},
        )

        if watching:
            req_id = self.pyforge_manager.client.unwatch_class(class_path)
        else:
            req_id = self.pyforge_manager.client.watch_class(class_path)

        if req_id == -1:
            self.audit_logger.finalize_action(
                log_entry, {"status": "error", "payload": "Failed to send request."}
            )
            if from_user:
                self.main_window.pyforge_console.log_error(
                    f"Failed to send {action} request for '{class_path}'. Not connected or error."
                )
            return

        self.pending_requests[req_id] = (
            lambda res, p=class_path, a=action, u=from_user: self._handle_watch_response(
                res, p, a, u
            ),
            log_entry,
        )
        self.audit_logger.associate_action(req_id, log_entry)

    def on_restore_requested(self, object_id: str):
        log_entry = self.audit_logger.begin_action(
            action_type="RestoreObject",
            source={"component": "Audit Log"},
            target={"object_id": object_id},
        )
        req_id = self.pyforge_manager.client.restore_object(object_id)
        if req_id != -1:
            self.pending_requests[req_id] = (self._handle_console_response, log_entry)
            self.audit_logger.associate_action(req_id, log_entry)

    @Slot(dict)
    def on_subscription_update(self, update_data: dict):
        self.main_window.pyforge_active_panel.object_browser.model.handle_subscription_update(
            update_data
        )

    @Slot(dict)
    def on_new_instance(self, new_instance_data: dict):
        self.main_window.pyforge_active_panel.object_browser.model.handle_new_instance(
            new_instance_data
        )
        if self.tray_icon:
            class_path = new_instance_data.get("class_path", "Object")
            self.tray_icon.showMessage(
                "PyForge Watcher",
                f"New instance of '{class_path}' created.",
                self.main_window.windowIcon(),
            )

    @Slot(int, object)
    def on_response_received(self, req_id, result):
        handler, log_entry = self.pending_requests.pop(req_id, (None, None))
        if log_entry:
            if log_entry["type"] == "AttributeChange":
                try:
                    path = log_entry["target"]["path"]
                    obj_id = path.split(":")[1].split(".")[0]
                    attr_name = path.split(".")[-1]
                    instance_path = f"instance:{obj_id}"
                    if (
                        instance_path
                        in self.main_window.pyforge_manager.client.last_known_state
                    ):
                        result["old_value"] = (
                            self.main_window.pyforge_manager.client.last_known_state[
                                instance_path
                            ].get(attr_name, "unknown")
                        )
                except Exception:
                    pass
            self.audit_logger.finalize_action(log_entry, result)
        if handler:
            handler(result)

    def _handle_console_response(self, result):
        status = result.get("status")
        payload = result.get("payload", "")
        if status == "error":
            self.main_window.pyforge_console.log_response(payload)
        else:
            self.main_window.pyforge_console.log_response(payload)

    def _handle_completions_response(self, result):
        self.main_window.pyforge_console.update_completions(result or [])

    def _handle_create_instance_response(self, result):
        if result.get("status") == "success":
            self.main_window.pyforge_console.log_system(
                "New instance created successfully."
            )
            self.on_discover_requested()
        else:
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "InstanceCreationError",
                    "error_message": result.get("payload", "Unknown error"),
                    "frames": [],
                }
            )

    def _handle_script_response(self, result):
        payload = result.get("payload")
        if result.get("status") == "error":
            self.main_window.log_to_output("PyForge", "", clear=True)
            self.main_window.pyforge_console.log_response(payload)
        else:
            log_msg = "--- Script executed successfully ---"
            self.main_window.log_to_output(
                "PyForge", log_msg, clear=True, raise_panel=True
            )
            if payload:
                self.main_window.pyforge_console.log_response(payload)

    def _handle_discover_response(self, result):
        browser = self.main_window.pyforge_active_panel.object_browser
        browser.model.update_toplevel(result)
        if self.pending_refresh_expansion_state:
            browser.restore_expansion_state(self.pending_refresh_expansion_state)

    def _handle_get_details_response(self, result, parent_item):
        browser = self.main_window.pyforge_active_panel.object_browser
        browser.model.update_children(parent_item, result)
        if self.pending_refresh_expansion_state:
            browser.restore_expansion_state(self.pending_refresh_expansion_state)

    def _handle_inspect_response(self, result):
        dialog = InspectorDialog(result, self.main_window)
        dialog.exec()

    def _handle_hot_reload_response(self, result):
        status = result.get("status")
        payload = result.get("payload", "")
        if status == "success":
            QMessageBox.information(self.main_window, "Hot Reload Successful", payload)
        else:
            QMessageBox.critical(
                self.main_window,
                "Hot Reload Failed",
                f"Could not reload module:\n\n{payload}",
            )

    def _handle_set_attribute_response(self, result, item):
        if result.get("status") == "success":
            if item:
                self.main_window.pyforge_active_panel.object_browser.model.update_item_value(
                    item, result.get("new_value")
                )
            self.main_window.pyforge_console.log_system(f"[OK] Attribute set.")
        else:
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "AttributeError",
                    "error_message": result.get("payload", "Unknown error"),
                    "frames": [],
                }
            )

    def _handle_delete_response(self, result, item):
        if result.get("status") == "success":
            self.main_window.pyforge_active_panel.object_browser.model.remove_item(item)
            object_id = result.get("id")
            self.toast.show_message(
                f"Deleted {item.text()}",
                "Undo",
                lambda: self.on_restore_requested(object_id),
            )
        else:
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "DeleteError",
                    "error_message": result.get("payload", "Unknown error"),
                    "frames": [],
                }
            )

    def _handle_watch_response(
        self, result, class_path: str, action: str, from_user: bool
    ):
        status = result.get("status")
        payload = result.get("payload", "")
        model = self.main_window.pyforge_active_panel.object_browser.model
        if status == "success":
            if action == "watch":
                self.watched_classes.add(class_path)
            else:
                self.watched_classes.discard(class_path)
            if from_user:
                self.main_window.pyforge_console.log_system(
                    f"{'Watching' if action == 'watch' else 'Stopped watching'} new instances of '{class_path}'."
                )
            item_path = f"class:{class_path}"
            proxy_index = model.find_item_by_path(item_path)
            if proxy_index.isValid():
                source_index = model.mapToSource(proxy_index)
                item = model.sourceModel().itemFromIndex(source_index)
                if item:
                    item.full_data["watched"] = action == "watch"
                    model.sourceModel().dataChanged.emit(source_index, source_index)
        elif from_user:
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "WatchError",
                    "error_message": payload,
                    "frames": [],
                }
            )

    @Slot(str, str)
    def on_status_changed(self, status: str, message: str):
        is_connected = status in ["connected", "connecting"]
        if is_connected:
            self.main_window.pyforge_status_label.setPixmap(
                get_pyforge_icon().pixmap(16, 16)
            )
            self.main_window.pyforge_status_label.setText(
                f"PyForge: {status.capitalize()}"
            )
        else:
            self.main_window.pyforge_status_label.setPixmap(QPixmap())
            self.main_window.pyforge_status_label.setText("PyForge: Idle")
        log_message = f"[STATUS] {message}"
        if status == "error":
            self.main_window.pyforge_console.log_response(
                {
                    "type": "traceback",
                    "error_type": "ConnectionError",
                    "error_message": log_message,
                    "frames": [],
                }
            )
        else:
            self.main_window.pyforge_console.log_system(log_message)
        self.main_window.pyforge_console.set_input_enabled(status == "connected")
        for editor in self.main_window.file_manager.open_file_paths:
            if isinstance(editor, PyForgeScriptEditor):
                editor.set_session_active(status == "connected")

    @Slot(str, int)
    def on_session_started(self, script_path: str, pid: int):
        self.main_window.debug_stack.setCurrentWidget(
            self.main_window.pyforge_active_panel
        )
        script_name = "Injected Process" if not script_path else Path(script_path).name
        self.main_window.pyforge_active_panel.set_session_info(script_name, pid)
        self.toast.setParent(
            self.main_window.pyforge_active_panel.object_browser.tree_view
        )

        self.audit_logger.start_session(self.workspace_path)
        QTimer.singleShot(1000, self.on_discover_requested)
        QTimer.singleShot(
            100,
            lambda: self.on_tab_changed(
                self.main_window.pyforge_active_panel.tab_widget.currentIndex()
            ),
        )

        self.toggle_live_mode(True)
        self.main_window.controller._update_ui_for_editor(
            self.main_window.get_current_editor()
        )
        self.update_master_script_view()

    @Slot()
    def on_session_stopped(self):
        self.audit_logger.stop_session()
        self.main_window.debug_stack.setCurrentWidget(self.main_window.debug_view)
        self.main_window.pyforge_active_panel.object_browser.model.clear()
        self.main_window.pyforge_active_panel.clear_session_info()
        self.watched_classes.clear()
        self.pending_refresh_expansion_state = None
        self.latest_system_metrics.clear()
        self.latest_agent_metrics.clear()
        for editor in self.main_window.file_manager.open_file_paths:
            if isinstance(editor, PyForgeScriptEditor):
                editor.set_session_active(False)

        self.toggle_live_mode(False)
        self.main_window.controller._update_ui_for_editor(
            self.main_window.get_current_editor()
        )
        self.update_master_script_view()

    def toggle_live_mode(self, is_active: bool):
        purple = QColor("#B69CFD") if is_active else None
        self.main_window.activity_bar.set_action_icon_color("Explorer", purple)
        self.main_window.activity_bar.set_action_icon_color("Debug", purple)
        self.main_window.activity_bar.set_action_icon_color("Review", purple)

        self.main_window.run_manager.update_run_actions_state(
            self.main_window.get_current_editor()
        )

    @Slot(str)
    def on_agent_log(self, message: str):
        self.main_window.log_to_output("PyForge", message.strip(), raise_panel=False)

    @Slot(str)
    def on_rename_script(self, old_path_str: str):
        old_path = Path(old_path_str)
        old_name = old_path.name
        new_name, ok = QInputDialog.getText(
            self.main_window,
            "Rename Script",
            f"Enter new name for '{old_name}':",
            text=old_name,
        )
        if ok and new_name and new_name != old_name:
            if not new_name.endswith(".pfscript"):
                new_name += ".pfscript"
            new_path = old_path.with_name(new_name)
            if new_path.exists():
                QMessageBox.warning(
                    self.main_window, "Error", "A script with that name already exists."
                )
                return
            try:
                self.main_window.file_manager.close_tab_by_path(str(old_path.resolve()))
                old_path.rename(new_path)
                self.main_window.file_manager.open_file_from_path(str(new_path))
            except OSError as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not rename script: {e}"
                )

    @Slot(str)
    def on_delete_script(self, path_str: str):
        path = Path(path_str)
        reply = QMessageBox.question(
            self.main_window,
            "Delete Script",
            f"Are you sure you want to permanently delete '{path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.main_window.file_manager.close_tab_by_path(str(path.resolve()))
                path.unlink()
            except OSError as e:
                QMessageBox.critical(
                    self.main_window, "Error", f"Could not delete script: {e}"
                )

    @Slot(str)
    def on_duplicate_script(self, path_str: str):
        original_path = Path(path_str)
        i = 1
        while True:
            new_name = f"{original_path.stem}_copy{i}{original_path.suffix}"
            new_path = original_path.with_name(new_name)
            if not new_path.exists():
                break
            i += 1
        try:
            shutil.copy2(original_path, new_path)
        except OSError as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not duplicate script: {e}"
            )

    @Slot(str, bool)
    def on_move_script(self, path_str: str, to_global: bool):
        path = Path(path_str)
        if to_global:
            target_dir, action_name = self.script_storage_path, "move to Global"
        else:
            if not self.workspace_path:
                QMessageBox.warning(
                    self.main_window,
                    "No Workspace",
                    "Cannot move to a workspace that is not open.",
                )
                return
            target_dir, action_name = Path(self.workspace_path), "move to Workspace"
        target_path = target_dir / path.name
        if target_path.exists():
            QMessageBox.warning(
                self.main_window,
                "Error",
                f"A script named '{path.name}' already exists in the target location.",
            )
            return
        try:
            self.main_window.file_manager.close_tab_by_path(str(path.resolve()))
            shutil.move(str(path), str(target_path))
        except (OSError, shutil.Error) as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not {action_name} script: {e}"
            )

    @Slot(str)
    def on_object_link_clicked(self, path: str):
        browser = self.main_window.pyforge_active_panel.object_browser
        index = browser.model.find_item_by_path(path)
        if index.isValid():
            browser.tree_view.setCurrentIndex(index)
            browser.tree_view.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
            self.main_window.pyforge_active_panel.tab_widget.setCurrentIndex(2)
            self.main_window.view_manager.set_view("Debug")

    @Slot(str, int)
    def on_file_link_clicked(self, file_path: str, line: int):
        self.main_window.file_manager.open_file_from_path(file_path)
        editor = self.main_window.file_manager.editors_by_path.get(
            str(Path(file_path).resolve())
        )
        if editor:
            editor.jump_and_highlight(line, 0)

    @Slot(dict)
    def on_system_metrics_update(self, system_metrics: dict):
        self.latest_system_metrics = system_metrics
        self._update_full_metrics_display()

    @Slot(dict)
    def on_agent_status_update(self, agent_metrics: dict):
        self.latest_agent_metrics = agent_metrics
        self._update_full_metrics_display()

    def _update_full_metrics_display(self):
        full_metrics = {**self.latest_system_metrics, **self.latest_agent_metrics}
        if (
            self.main_window.debug_stack.currentWidget()
            is self.main_window.pyforge_active_panel
        ):
            self.main_window.pyforge_active_panel.metrics_panel.update_metrics(
                full_metrics
            )

    @Slot(str, str)
    def on_file_saved(self, file_path: str, content: str):
        if (
            self.workspace_path
            and Path(file_path).resolve()
            == (Path(self.workspace_path) / "master.pfscript").resolve()
        ):
            self.update_master_script_view()

    @Slot()
    def on_validate_reload_clicked(self):
        editor = self.main_window.get_current_editor()
        if not isinstance(editor, PyForgeScriptEditor) or not editor.is_master_script:
            return

        def _proceed_with_request(content):
            if content is None:
                return
            if self.pyforge_manager.is_session_active():
                self._send_reload_request(content)
            else:
                self._send_validation_request(content)

        editor.get_text(_proceed_with_request)

    def _send_validation_request(self, content: str):
        if content is None:
            return
        log_entry = self.audit_logger.begin_action(
            action_type="ValidateMasterScript", source={"component": "Editor Toolbar"}
        )
        self.main_window.pyforge_console.log_system(
            "[Compiler] Validating master script..."
        )
        req_id = self.pyforge_manager.client.validate_master_script(content)
        if req_id != -1:
            self.pending_requests[req_id] = (
                self._handle_validation_response,
                log_entry,
            )
            self.audit_logger.associate_action(req_id, log_entry)

    def _handle_validation_response(self, result: dict):
        if result.get("status") == "success":
            self.main_window.pyforge_console.log_system(
                "[Compiler] Validation successful."
            )
        else:
            error_msg = result.get("error", "Unknown validation error.")
            checks = result.get("checks", [])
            full_report = f"[Compiler] Validation Failed: {error_msg}\n"
            for check in checks:
                if check["status"] == "error":
                    full_report += (
                        f"- {check['name']}: {check.get('error', 'Failed')}\n"
                    )
            self.main_window.pyforge_console.log_error(full_report)

    def _send_reload_request(self, content: str):
        if content is None:
            return
        log_entry = self.audit_logger.begin_action(
            action_type="ReloadMasterScript", source={"component": "Editor Toolbar"}
        )
        self.main_window.pyforge_console.log_system(
            "[Compiler] Validating and reloading master script..."
        )
        req_id = self.pyforge_manager.client.reload_master_script(content)
        if req_id != -1:
            self.pending_requests[req_id] = (self._handle_reload_response, log_entry)
            self.audit_logger.associate_action(req_id, log_entry)

    def _handle_reload_response(self, result: dict):
        if result.get("status") == "success":
            self.main_window.pyforge_console.log_system(
                "[Compiler] Master script reloaded successfully."
            )
            payload = result.get("payload", {})
            definitions = payload.get("metric_definitions", [])
            self.main_window.pyforge_active_panel.metrics_panel.update_definitions(
                definitions
            )
        else:
            error_msg = result.get("error", "Unknown validation error.")
            checks = result.get("checks", [])
            full_report = f"[Compiler] Failed to reload Master Script: {error_msg}\n"
            for check in checks:
                if check["status"] == "error":
                    full_report += (
                        f"- {check['name']}: {check.get('error', 'Failed')}\n"
                    )
            self.main_window.pyforge_console.log_error(full_report)

    def update_master_script_view(self):
        if not self.workspace_path:
            return
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        session_panel = self.main_window.pyforge_active_panel.session_panel
        if master_script_path.exists():
            session_panel.show_manager(True)
            try:
                content = master_script_path.read_text(encoding="utf-8")
                ast_data = self._parse_master_script_ast(content)
                session_panel.master_script_manager.update_from_ast(ast_data)
            except Exception as e:
                print(f"Error parsing master script AST: {e}")
        else:
            session_panel.show_manager(False)

    def _parse_master_script_ast(self, content: str) -> dict:
        tree = ast.parse(content)
        data = {"hooks": [], "metrics": [], "global_scope": [], "overrides": []}
        defined_hooks = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in self.all_hook_definitions:
                    defined_hooks.add(node.name)
                    hook_data = {
                        "name": node.name,
                        "lineno": node.lineno,
                        "scripts": [],
                    }
                    for sub_node in node.body:
                        if (
                            isinstance(sub_node, ast.Expr)
                            and isinstance(sub_node.value, ast.Call)
                            and isinstance(sub_node.value.func, ast.Attribute)
                            and sub_node.value.func.attr == "run_script"
                            and sub_node.value.args
                            and isinstance(sub_node.value.args[0], ast.Constant)
                        ):
                            script_path_str = sub_node.value.args[0].value
                            full_path = str(
                                (Path(self.workspace_path) / script_path_str).resolve()
                            )
                            hook_data["scripts"].append(
                                {
                                    "path": script_path_str,
                                    "full_path": full_path,
                                    "lineno": sub_node.lineno,
                                }
                            )
                    data["hooks"].append(hook_data)
                elif node.decorator_list:
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call) and isinstance(
                            decorator.func, ast.Attribute
                        ):
                            if decorator.func.attr == "metric":
                                metric_name = "Unknown Metric"
                                for kw in decorator.keywords:
                                    if kw.arg == "name" and isinstance(
                                        kw.value, ast.Constant
                                    ):
                                        metric_name = kw.value.value
                                data["metrics"].append(
                                    {
                                        "name": metric_name,
                                        "func_name": node.name,
                                        "lineno": node.lineno,
                                    }
                                )
                            elif decorator.func.attr == "override" and decorator.args:
                                target = decorator.args[0].value
                                data["overrides"].append(
                                    {
                                        "target": target,
                                        "func_name": node.name,
                                        "lineno": node.lineno,
                                    }
                                )
            elif not isinstance(node, (ast.Import, ast.ImportFrom)):
                summary = ast.get_source_segment(content, node)
                if summary and summary.strip():
                    if len(summary) > 50:
                        summary = summary[:50].strip() + "..."
                    data["global_scope"].append(
                        {"summary": summary, "lineno": node.lineno}
                    )
        data["defined_hooks"] = defined_hooks
        data["hooks"].sort(key=lambda x: x["name"])
        return data

    @Slot()
    def on_create_master_script_from_prompt(self):
        if not self.workspace_path:
            return
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        if master_script_path.exists():
            QMessageBox.information(
                self.main_window,
                "File Exists",
                "A `master.pfscript` file already exists in your workspace.",
            )
            return
        try:
            template_path = (
                Path(self.main_window.app_root)
                / "src"
                / "forge"
                / "frontend"
                / "components"
                / "pyforge"
                / "templates"
                / "master.pfscript.template"
            )
            if template_path.exists():
                content = template_path.read_text(encoding="utf-8")
                master_script_path.write_text(content, encoding="utf-8")
            else:
                master_script_path.write_text(
                    "import pf\n\n# Master script created, but template not found.\n",
                    encoding="utf-8",
                )
            self.main_window.file_manager.open_file_from_path(str(master_script_path))
            self.update_master_script_view()
        except OSError as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not create master script: {e}"
            )

    @Slot(int)
    def on_edit_in_text_requested(self, line_number):
        master_script_path = str(Path(self.workspace_path) / "master.pfscript")
        self.main_window.file_manager.open_file_from_path(master_script_path)
        if line_number > 0:
            QTimer.singleShot(
                200,
                lambda: self._jump_to_line_in_editor(master_script_path, line_number),
            )

    def _jump_to_line_in_editor(self, path, line):
        editor = self.main_window.file_manager.editors_by_path.get(path)
        if editor:
            editor.jump_and_highlight(line - 1, 0)

    @Slot()
    def on_add_hook(self):
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        try:
            content = master_script_path.read_text(encoding="utf-8")
            ast_data = self._parse_master_script_ast(content)
            existing_hooks = ast_data["defined_hooks"]
            available_hooks = {
                k: v
                for k, v in self.all_hook_definitions.items()
                if k not in existing_hooks
            }
            if not available_hooks:
                QMessageBox.information(
                    self.main_window,
                    "Add Hook",
                    "All available hooks are already defined in the master script.",
                )
                return
            dialog = AddHookDialog(available_hooks, self.main_window)
            dialog.hook_selected.connect(self._add_hook_to_script)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not parse master script to add hook: {e}",
            )

    @Slot(str)
    def _add_hook_to_script(self, hook_name: str):
        hook_info = self.all_hook_definitions.get(hook_name)
        if not hook_info:
            return
        self._append_to_master_script(f"\n\n{hook_info['template']}\n")

    @Slot()
    def on_add_override(self):
        reply = QMessageBox.warning(
            self.main_window,
            "Advanced Feature",
            "Overrides can replace core agent functions and may cause instability or break the connection to the UI if used incorrectly.\n\nAre you sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        template_path = (
            Path(self.main_window.app_root)
            / "src"
            / "forge"
            / "frontend"
            / "components"
            / "pyforge"
            / "templates"
            / "overrides"
            / "example_override.pfscript.template"
        )
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            self._append_to_master_script(f"\n{content}\n")
        else:
            QMessageBox.critical(
                self.main_window, "Error", "Override template not found."
            )

    @Slot()
    def on_add_snippet(self):
        dialog = SnippetEditorDialog(self.main_window)
        dialog.snippet_saved.connect(self._add_snippet_to_script)
        dialog.exec()

    @Slot(str)
    def on_attach_new_script(self, hook_name):
        if not self.workspace_path:
            return
        file_name, ok = QInputDialog.getText(
            self.main_window,
            "Create New Event Script",
            f"Enter filename for new script to attach to '{hook_name}':",
        )
        if ok and file_name:
            if not file_name.endswith(".pfscript"):
                file_name += ".pfscript"
            new_script_path = Path(self.workspace_path) / file_name
            if new_script_path.exists():
                QMessageBox.warning(
                    self.main_window,
                    "File Exists",
                    f"A script named '{file_name}' already exists.",
                )
                return
            try:
                template_content = f"# Event script for hook: {hook_name}\nimport pf\n\npf.log('Event script {file_name} triggered!')\n"
                new_script_path.write_text(template_content, encoding="utf-8")
                relative_path = os.path.relpath(
                    new_script_path, self.workspace_path
                ).replace("\\", "/")
                self._add_line_to_function(
                    hook_name, f"    pf.run_script('{relative_path}')"
                )
                self.main_window.file_manager.open_file_from_path(str(new_script_path))
            except Exception as e:
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    f"Could not create or attach new script: {e}",
                )

    @Slot(str)
    def on_attach_existing_script(self, hook_name):
        script_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            f"Select Event Script for '{hook_name}'",
            self.workspace_path,
            "PyForge Scripts (*.pfscript)",
        )
        if script_path and self.workspace_path:
            relative_path = os.path.relpath(script_path, self.workspace_path).replace(
                "\\", "/"
            )
            self._add_line_to_function(
                hook_name, f"    pf.run_script('{relative_path}')"
            )

    @Slot(str, str)
    def on_remove_script(self, hook_name: str, script_full_path: str):
        if not self.workspace_path:
            return
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        relative_path = os.path.relpath(script_full_path, self.workspace_path).replace(
            "\\", "/"
        )
        try:
            content = master_script_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            new_lines, in_hook, line_removed = [], False, False
            for line in lines:
                if line.strip().startswith(f"def {hook_name}("):
                    in_hook = True
                elif in_hook and (
                    line.strip().startswith("def ") or line.strip().startswith("@")
                ):
                    in_hook = False
                if in_hook and f"pf.run_script('{relative_path}'" in line:
                    line_removed = True
                    continue
                new_lines.append(line)
            if not line_removed:
                QMessageBox.warning(
                    self.main_window,
                    "Error",
                    "Could not find the script reference inside the hook to remove it.",
                )
                return
            new_content = "\n".join(new_lines)
            tree = ast.parse(new_content)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == hook_name:
                    if not node.body or (
                        len(node.body) == 1
                        and isinstance(node.body[0], ast.Expr)
                        and node.body[0].value is None
                    ):
                        def_line = f"def {hook_name}"
                        lines = new_content.splitlines()
                        for i, line in enumerate(lines):
                            if line.strip().startswith(def_line):
                                lines.insert(i + 1, "    pass")
                                new_content = "\n".join(lines)
                                break
                        break
            self._rewrite_master_script(new_content)
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not modify master script to remove event script: {e}",
            )

    @Slot(str, str)
    def on_inline_script(self, hook_name: str, script_full_path: str):
        if not self.workspace_path:
            return
        master_script_path, event_script_path = Path(
            self.workspace_path
        ) / "master.pfscript", Path(script_full_path)
        relative_path = os.path.relpath(script_full_path, self.workspace_path).replace(
            "\\", "/"
        )
        try:
            if not event_script_path.exists():
                QMessageBox.warning(
                    self.main_window,
                    "Error",
                    f"Event script file not found at: {script_full_path}",
                )
                return
            event_content = event_script_path.read_text(encoding="utf-8")
            indented_event_content = "\n".join(
                ["    " + line for line in event_content.splitlines()]
            )
            master_content = master_script_path.read_text(encoding="utf-8")
            lines, new_lines, in_hook, line_replaced = (
                master_content.splitlines(),
                [],
                False,
                False,
            )
            for line in lines:
                if line.strip().startswith(f"def {hook_name}("):
                    in_hook = True
                elif in_hook and (
                    line.strip().startswith("def ") or line.strip().startswith("@")
                ):
                    in_hook = False
                if in_hook and f"pf.run_script('{relative_path}'" in line:
                    line_replaced = True
                    new_lines.append(indented_event_content)
                    continue
                new_lines.append(line)
            if not line_replaced:
                QMessageBox.warning(
                    self.main_window,
                    "Error",
                    "Could not find the script reference to inline it.",
                )
                return
            self._rewrite_master_script("\n".join(new_lines))
            reply = QMessageBox.question(
                self.main_window,
                "Inline Complete",
                f"Successfully inlined '{event_script_path.name}'.\n\nDo you want to delete the original event script file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.main_window.file_manager.handle_delete_item(str(event_script_path))
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not inline script: {e}"
            )

    def _add_snippet_to_script(self, snippet: str):
        self._append_to_master_script(f"\n{snippet}\n")

    def _append_to_master_script(self, text_to_append: str):
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        try:
            with open(master_script_path, "a", encoding="utf-8") as f:
                f.write(text_to_append)
            new_content = master_script_path.read_text(encoding="utf-8")
            editor = self.main_window.file_manager.editors_by_path.get(
                str(master_script_path.resolve())
            )
            if editor:
                editor.set_content(
                    new_content,
                    "python",
                    editor.current_uri,
                    lambda: self.update_master_script_view(),
                )
            else:
                self.update_master_script_view()
        except IOError as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not write to master script: {e}"
            )

    def _rewrite_master_script(self, new_content: str):
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        try:
            master_script_path.write_text(new_content, encoding="utf-8")
            editor = self.main_window.file_manager.editors_by_path.get(
                str(master_script_path.resolve())
            )
            if editor:
                editor.set_content(
                    new_content,
                    "python",
                    editor.current_uri,
                    lambda: self.update_master_script_view(),
                )
            else:
                self.update_master_script_view()
        except IOError as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not write to master script: {e}"
            )

    def _add_line_to_function(self, func_name: str, line_to_add: str):
        master_script_path = Path(self.workspace_path) / "master.pfscript"
        try:
            content = master_script_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            in_func = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f"def {func_name}("):
                    in_func = True
                elif in_func and line.strip() == "pass":
                    lines[i] = line_to_add
                    in_func = False
                    break
                elif (
                    in_func
                    and (line.strip() == "" or line.strip().startswith("#"))
                    and (
                        i + 1 < len(lines)
                        and (
                            lines[i + 1].strip().startswith("def ")
                            or lines[i + 1].strip().startswith("@")
                        )
                    )
                ):
                    lines.insert(i, line_to_add)
                    in_func = False
                    break
            else:
                for i, line in reversed(list(enumerate(lines))):
                    if line.strip().startswith(f"def {func_name}("):
                        lines.insert(i + 1, line_to_add)
                        break
            new_content = "\n".join(lines)
            master_script_path.write_text(new_content, encoding="utf-8")
            editor = self.main_window.file_manager.editors_by_path.get(
                str(master_script_path.resolve())
            )
            if editor:
                editor.set_content(
                    new_content,
                    "python",
                    editor.current_uri,
                    lambda: self.update_master_script_view(),
                )
            else:
                self.update_master_script_view()
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error", f"Could not modify master script: {e}"
            )

    @Slot()
    def on_refresh_master_script_view(self):
        if not self.workspace_path:
            return
        master_script_path = str(
            (Path(self.workspace_path) / "master.pfscript").resolve()
        )
        editor = self.main_window.file_manager.editors_by_path.get(master_script_path)
        if editor and self.main_window.file_manager.is_dirty(editor):
            self.main_window.file_manager.save_file(editor)
        else:
            self.update_master_script_view()

    @Slot(str)
    def on_create_metric_event_script(self, metric_path: str):
        safe_name = metric_path.replace("/", "_").replace(" ", "_")
        script_path, ok = QInputDialog.getText(
            self.main_window,
            "Create Metric Event Script",
            "Enter a filename for the new event script:",
            text=f"on_{safe_name}_changed.pfscript",
        )
        if ok and script_path and self.workspace_path:
            if not script_path.endswith(".pfscript"):
                script_path += ".pfscript"
            full_path = Path(self.workspace_path) / script_path
            template_path = (
                Path(self.main_window.app_root)
                / "src"
                / "forge"
                / "frontend"
                / "components"
                / "pyforge"
                / "templates"
                / "metrics"
                / "metric_event_script.pfscript.template"
            )
            content = template_path.read_text(encoding="utf-8")
            content += f"\n# Example for the '{metric_path}' metric:\nif metric_path == '{metric_path}':\n    # Add your logic here, for example:\n    if isinstance(new_value, (int, float)) and new_value > 100:\n        pf.log(f'ALERT: {metric_path} has exceeded threshold with value: {{new_value}}')\n"
            full_path.write_text(content, encoding="utf-8")
            master_script_path = Path(self.workspace_path) / "master.pfscript"
            script_content = master_script_path.read_text(encoding="utf-8")
            if "def on_metric_update" not in script_content:
                self._add_hook_to_script("on_metric_update")
            relative_path = os.path.relpath(full_path, self.workspace_path).replace(
                "\\", "/"
            )
            self._add_line_to_function(
                "on_metric_update",
                f"    pf.run_script('{relative_path}', context={{'metric_path': metric_path, 'new_value': new_value, 'old_value': old_value}})",
            )
            self.main_window.file_manager.open_file_from_path(str(full_path))
