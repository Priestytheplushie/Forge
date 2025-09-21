from PySide6.QtCore import QObject, Slot, QPoint
from PySide6.QtWidgets import QMessageBox, QInputDialog

from forge.frontend.windows.clone_dialog import CloneDialog
from forge.frontend.windows.create_branch_dialog import CreateBranchDialog
from forge.frontend.windows.action_confirmation_dialog import ActionConfirmationDialog
from forge.frontend.windows.branch_operations_studio import BranchOperationsStudio
from forge.frontend.components.menus.branch_menu import BranchMenu


class GitController(QObject):
    def __init__(self, main_window, git_manager, workspace_manager):
        super().__init__(main_window)
        self.main_window = main_window
        self.git_manager = git_manager
        self.workspace_manager = workspace_manager

        self.branch_data_cache = {}
        self.current_branch_cache = ""

        self.branch_menu = BranchMenu(self.main_window)

        self._connect_signals()

    def _connect_signals(self):

        sc_panel = self.main_window.source_control_panel
        sc_panel.stage_requested.connect(self.git_manager.stage_files)
        sc_panel.unstage_requested.connect(self.git_manager.unstage_files)
        sc_panel.stage_all_requested.connect(self.git_manager.stage_all_files)
        sc_panel.unstage_all_requested.connect(self.git_manager.unstage_all_files)
        sc_panel.commit_requested.connect(self.on_git_commit)
        sc_panel.commit_merge_requested.connect(self.on_git_commit_merge)
        sc_panel.stash_requested.connect(self.git_manager.stash_changes)
        sc_panel.initialize_repo_requested.connect(self.git_manager.initialize_repo)
        sc_panel.clone_repo_requested.connect(self.on_clone_repo_requested)
        sc_panel.abort_merge_requested.connect(self.on_abort_merge)

        self.main_window.git_refresh_button.clicked.connect(self.git_manager.fetch)
        self.main_window.git_pull_button.clicked.connect(self.git_manager.pull)
        self.main_window.git_push_button.clicked.connect(self.git_manager.push)
        self.main_window.git_branch_widget.clicked.connect(
            self.on_branch_menu_requested
        )

        self.branch_menu.checkout_requested.connect(self.git_manager.checkout_branch)
        self.branch_menu.create_branch_requested.connect(
            self.on_create_branch_requested
        )
        self.branch_menu.manage_branches_requested.connect(
            self.on_manage_branches_requested
        )
        self.branch_menu.merge_requested.connect(self.on_merge_branch_requested)
        self.branch_menu.squash_merge_requested.connect(
            lambda branch: self.on_merge_branch_requested(branch, squash=True)
        )
        self.branch_menu.rebase_requested.connect(self.on_rebase_branch_requested)
        self.branch_menu.rename_requested.connect(self.on_rename_branch_requested)
        self.branch_menu.delete_local_requested.connect(
            lambda branch: self.on_delete_branch_requested(branch, is_remote=False)
        )
        self.branch_menu.delete_remote_requested.connect(
            lambda branch: self.on_delete_branch_requested(branch, is_remote=True)
        )

    @Slot(dict, str)
    def on_branches_updated(self, branch_data: dict, current_branch: str):
        self.branch_data_cache, self.current_branch_cache = branch_data, current_branch

    @Slot()
    def on_branch_menu_requested(self):
        self.branch_menu.populate_branches(
            self.branch_data_cache, self.current_branch_cache
        )
        pos = self.main_window.git_branch_widget.mapToGlobal(QPoint(0, 0))
        pos.setY(pos.y() - self.branch_menu.sizeHint().height())
        self.branch_menu.exec(pos)

    @Slot()
    def on_clone_repo_requested(self):
        dialog = CloneDialog(self.main_window)
        dialog.clone_requested.connect(self.git_manager.clone_repo)
        self.git_manager.clone_progress.connect(dialog.update_progress)
        self.git_manager.clone_finished.connect(dialog.on_clone_finished)
        self.git_manager.clone_finished.connect(self.on_clone_finished)
        dialog.exec()
        try:
            self.git_manager.clone_progress.disconnect(dialog.update_progress)
            self.git_manager.clone_finished.disconnect(dialog.on_clone_finished)
            self.git_manager.clone_finished.disconnect(self.on_clone_finished)
        except RuntimeError:
            pass

    @Slot(bool, str)
    def on_clone_finished(self, success: bool, path_or_error: str):
        if success:
            self.workspace_manager.set_workspace(path_or_error)

    @Slot()
    def on_create_branch_requested(self):
        all_branches = [b[0] for b in self.branch_data_cache.get("local", [])] + [
            b[0] for b in self.branch_data_cache.get("remote", [])
        ]
        dialog = CreateBranchDialog(
            all_branches, self.current_branch_cache, self.main_window
        )
        dialog.create_branch_requested.connect(self.git_manager.create_branch)
        dialog.exec()

    @Slot(str, bool, str)
    def on_merge_branch_requested(
        self, branch_name: str, squash: bool = False, message: str = ""
    ):
        if not message:
            action = "Squash Merge" if squash else "Merge"
            if squash:
                msg = (
                    f"This will combine all commits from '{branch_name}' into a single new commit on your current branch '{self.current_branch_cache}'.\n\n"
                    "A squash merge does not create a merge commit. This is useful for keeping a clean history. Are you sure?"
                )
            else:
                msg = f"This will merge branch '{branch_name}' into your current branch '{self.current_branch_cache}'.\n\nThis may create a merge commit. Are you sure you want to continue?"

            dialog = ActionConfirmationDialog(
                f"Confirm {action}", msg, action, self.main_window
            )
            if dialog.exec():
                self.git_manager.merge_branch(
                    branch_name, squash, f"Merge branch '{branch_name}'"
                )
        else:
            self.git_manager.merge_branch(branch_name, squash, message)

    @Slot(str)
    def on_rebase_branch_requested(self, branch_name: str):
        msg = f"This will rebase your current branch '{self.current_branch_cache}' onto '{branch_name}'.\n\nThis will rewrite the commit history of your current branch. Are you sure you want to continue?"
        dialog = ActionConfirmationDialog(
            "Confirm Rebase", msg, "Rebase", self.main_window
        )
        if dialog.exec():
            self.git_manager.rebase_branch(branch_name)

    @Slot(str, str)
    def on_rename_branch_requested(self, old_name: str, new_name: str):
        self.git_manager.rename_branch(old_name, new_name)

    @Slot(str, bool)
    def on_delete_branch_requested(self, branch_name: str, is_remote: bool):
        branch_type = "remote" if is_remote else "local"
        display_name = (
            branch_name.replace("origin/", "", 1) if is_remote else branch_name
        )
        msg = f"Are you sure you want to permanently delete the {branch_type} branch '{display_name}'?\n\nThis action cannot be undone."
        dialog = ActionConfirmationDialog(
            f"Confirm Delete {branch_type.capitalize()} Branch",
            msg,
            "Delete",
            self.main_window,
        )
        if dialog.exec():
            self.git_manager.delete_branch(branch_name, is_remote)

    @Slot()
    def on_manage_branches_requested(self):
        dialog = BranchOperationsStudio(
            self.branch_data_cache, self.current_branch_cache, self.main_window
        )
        dialog.create_branch_requested.connect(self.on_create_branch_requested)
        dialog.merge_branch_requested.connect(
            lambda branch, squash, msg: self.git_manager.merge_branch(
                branch, squash, msg
            )
        )
        dialog.rebase_branch_requested.connect(self.on_rebase_branch_requested)
        dialog.rename_branch_requested.connect(self.on_rename_branch_requested)
        dialog.delete_branch_requested.connect(self.on_delete_branch_requested)
        dialog.exec()

    @Slot(str, bool)
    def on_git_commit(self, message: str, stage_all: bool):
        self.git_manager.commit(message, stage_all)

    @Slot(str)
    def on_git_commit_merge(self, message: str):
        self.on_git_commit(message, stage_all=False)
        self.main_window.controller.refactor_controller._exit_merge_mode()

    @Slot()
    def on_abort_merge(self):
        self.git_manager.abort_merge()
        self.main_window.controller.refactor_controller._exit_merge_mode()
