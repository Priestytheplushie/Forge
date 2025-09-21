from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThread
from pathlib import Path
import git
import os
import datetime


class CloneWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, url, path, parent=None):
        super().__init__(parent)
        self.url = url
        self.path = path
        self.result = (False, "")

    def run(self):
        try:

            class CloneProgress(git.remote.RemoteProgress):
                def update(self2, op_code, cur_count, max_count=None, message=""):
                    self.progress.emit(f"-> {message}")

            self.progress.emit(f"Cloning '{self.url}' into '{self.path}'...")
            git.Repo.clone_from(self.url, self.path, progress=CloneProgress())
            self.result = (True, self.path)
            self.finished.emit(True, self.path)
        except git.GitCommandError as e:
            self.result = (False, str(e.stderr))
            self.finished.emit(False, str(e.stderr))
        except Exception as e:
            self.result = (False, str(e))
            self.finished.emit(False, str(e))


class GitManager(QObject):
    repo_status_changed = Signal(bool)
    status_changed = Signal(list, list)
    branch_changed = Signal(str)
    remote_status_changed = Signal(int, int)
    git_command_output = Signal(str)
    upstream_branch_not_found = Signal()
    merge_conflict_detected = Signal(list)
    clone_progress = Signal(str)
    clone_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace_path = None
        self.repo = None
        self.current_branch = "main"
        self.clone_worker = None
        self.is_in_merge_conflict = False

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.refresh_status)

    def _log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.git_command_output.emit(f"[{timestamp}] {message}")

    @Slot(str)
    def set_workspace_path(self, path: str):
        self.workspace_path = Path(path)
        self.refresh_timer.stop()
        try:
            self.repo = git.Repo(path, search_parent_directories=True)
            self._log(f"Git repository found at: {self.repo.working_dir}")
            self.repo_status_changed.emit(True)
            self.refresh_status()
            self.refresh_timer.start()
        except git.InvalidGitRepositoryError:
            self.repo = None
            self.repo_status_changed.emit(False)
        except Exception as e:
            self._log(f"Error initializing Git: {e}")
            self.repo = None
            self.repo_status_changed.emit(False)

    @Slot()
    def refresh_status(self):
        if not self.repo or not self.repo.git_dir:
            return

        is_merging_now = (Path(self.repo.git_dir) / "MERGE_HEAD").exists()
        if is_merging_now:
            unresolved_paths = set()
            staged_paths = set()

            status_output = self.repo.git.status("--porcelain")
            for line in status_output.strip().split("\n"):
                if not line:
                    continue

                status, path = line[:2], line[3:]
                if status in ("DD", "AU", "UD", "UA", "DU", "AA", "UU"):
                    unresolved_paths.add(path)

                if status[0] != " " and status not in (
                    "DD",
                    "AU",
                    "UD",
                    "UA",
                    "DU",
                    "AA",
                    "UU",
                ):
                    staged_paths.add(path)

            unresolved_paths = {
                p for p in unresolved_paths if not p.startswith(".forge/")
            }
            staged_paths = {p for p in staged_paths if not p.startswith(".forge/")}

            if not self.is_in_merge_conflict:
                self._log("Merge conflict state detected.")
                self.is_in_merge_conflict = True
                self.merge_conflict_detected.emit(sorted(list(unresolved_paths)))

            self.status_changed.emit(
                sorted(list(staged_paths)), sorted(list(unresolved_paths))
            )
            return
        elif self.is_in_merge_conflict:
            self.is_in_merge_conflict = False

        try:
            self.current_branch = self.repo.active_branch.name
            self.branch_changed.emit(self.current_branch)
            tracking_branch = self.repo.active_branch.tracking_branch()
            if tracking_branch:
                ahead = sum(
                    1
                    for _ in self.repo.iter_commits(
                        f"{tracking_branch.name}..{self.current_branch}"
                    )
                )
                behind = sum(
                    1
                    for _ in self.repo.iter_commits(
                        f"{self.current_branch}..{tracking_branch.name}"
                    )
                )
                self.remote_status_changed.emit(ahead, behind)
            else:
                self.remote_status_changed.emit(0, 0)
        except TypeError:
            self.current_branch = self.repo.head.object.hexsha[:7]
            self.branch_changed.emit(self.current_branch)
            self.remote_status_changed.emit(0, 0)
            return
        except Exception:
            self.remote_status_changed.emit(0, 0)

        staged_changes = [
            {"path": diff.a_path or diff.b_path, "status": diff.change_type}
            for diff in self.repo.index.diff("HEAD", R=True)
        ]
        unstaged_changes = [
            {"path": diff.a_path or diff.b_path, "status": diff.change_type}
            for diff in self.repo.index.diff(None)
        ]
        for path in self.repo.untracked_files:
            if not self.repo.ignored(path):
                unstaged_changes.append({"path": path, "status": "A"})
        self.status_changed.emit(staged_changes, unstaged_changes)

    def initialize_repo(self):
        if self.workspace_path and not self.repo:
            try:
                self.repo = git.Repo.init(self.workspace_path)
                self._log(f"Initialized empty repository at: {self.workspace_path}")
                self.set_workspace_path(self.workspace_path)
            except Exception as e:
                self._log(f"Error initializing repository: {e}")

    def clone_repo(self, url: str, path: str):
        if self.clone_worker and self.clone_worker.isRunning():
            self._log("A clone operation is already in progress.")
            return
        self.clone_worker = CloneWorker(url, path)
        self.clone_worker.progress.connect(self.clone_progress)
        self.clone_worker.finished.connect(self.clone_finished)
        self.clone_worker.start()

    def fetch(self):
        if not self.repo or not self.repo.remotes:
            self._log("Error: No remote repository configured.")
            return
        try:
            self._log(f"Fetching from '{self.repo.remotes.origin.name}'...")
            self.repo.remotes.origin.fetch()
            self._log("Fetch successful.")
            self.refresh_status()
        except Exception as e:
            self._log(f"Error fetching: {e}")

    def pull(self):
        if not self.repo or not self.repo.remotes:
            self._log("Error: No remote repository configured.")
            return
        try:
            self._log(f"Pulling from '{self.repo.remotes.origin.name}'...")
            self.repo.remotes.origin.pull()
            self._log("Pull successful.")
            self.refresh_status()
        except git.GitCommandError as e:
            if "merge conflict" in e.stderr.lower():
                self._log("Pull resulted in merge conflicts. Please resolve them.")
                self.refresh_status()
            else:
                self._log(f"Error pulling: {e.stderr.strip()}")
        except Exception as e:
            self._log(f"An unexpected error occurred during pull: {e}")

    def push(self):
        if not self.repo or not self.repo.remotes:
            self._log("Error: No remote repository configured.")
            return
        try:
            self._log(f"Pushing to '{self.repo.remotes.origin.name}'...")
            self.repo.remotes.origin.push()
            self._log("Push successful.")
            self.refresh_status()
        except git.GitCommandError as e:
            if "no upstream branch" in e.stderr:
                self.upstream_branch_not_found.emit()
            else:
                self._log(f"Error pushing: {e.stderr.strip()}")
        except Exception as e:
            self._log(f"An unexpected error occurred during push: {e}")

    def push_and_set_upstream(self):
        if not self.repo or not self.repo.remotes:
            self._log("Error: No remote repository configured.")
            return
        try:
            self._log(
                f"Pushing and setting upstream for branch '{self.current_branch}'..."
            )
            self.repo.git.push(
                "--set-upstream", self.repo.remotes.origin.name, self.current_branch
            )
            self._log("Push successful.")
            self.refresh_status()
        except git.GitCommandError as e:
            self._log(f"Error pushing: {e.stderr.strip()}")
        except Exception as e:
            self._log(f"An unexpected error occurred during push: {e}")

    def abort_merge(self):
        if not self.repo:
            return
        try:
            if (Path(self.repo.git_dir) / "MERGE_HEAD").exists():
                self.repo.git.merge("--abort")
                self._log("Merge aborted.")
                self.is_in_merge_conflict = False
                self.refresh_status()
            else:
                self._log("No active merge to abort.")
        except Exception as e:
            self._log(f"Error aborting merge: {e}")

    def stage_files(self, file_paths: list[str]):
        if not self.repo:
            return
        try:
            self.repo.index.add(file_paths)
            self.refresh_status()
        except Exception as e:
            self._log(f"Error staging files: {e}")

    def stage_all_files(self):
        if not self.repo:
            return
        try:
            self.repo.git.add(A=True)
            self.refresh_status()
        except Exception as e:
            self._log(f"Error staging all files: {e}")

    def unstage_files(self, file_paths: list[str]):
        if not self.repo:
            return
        try:
            self.repo.index.reset(paths=file_paths)
            self.refresh_status()
        except Exception as e:
            self._log(f"Error unstaging files: {e}")

    def unstage_all_files(self):
        if not self.repo:
            return
        try:
            self.repo.index.reset()
            self.refresh_status()
        except Exception as e:
            self._log(f"Error unstaging all files: {e}")

    def commit(self, message: str, stage_all: bool = False):
        if not self.repo:
            return
        try:
            if self.is_in_merge_conflict:
                unmerged = self.repo.index.unmerged_blobs()
                if unmerged:
                    self._log(
                        f"Error: Cannot commit. You still have {len(unmerged)} unresolved conflicts."
                    )
                    return
            if stage_all:
                self.repo.git.add(A=True)
            self.repo.index.commit(message)
            self._log(f'Committed changes with message: "{message}"')
            self.is_in_merge_conflict = False
            self.refresh_status()
        except Exception as e:
            self._log(f"Error committing: {e}")

    def stash_changes(self, message: str):
        if not self.repo:
            return
        try:
            self.repo.git.stash("push", "-m", message)
            self._log("Stashed changes.")
            self.refresh_status()
        except Exception as e:
            self._log(f"Error stashing changes: {e}")

    def discard_changes(self, file_path_str: str):
        if not self.repo:
            return
        try:
            full_path = Path(self.repo.working_dir) / file_path_str
            if file_path_str in self.repo.untracked_files:
                if full_path.is_file():
                    os.remove(full_path)
            else:
                self.repo.git.checkout("--", file_path_str)
            self.refresh_status()
        except Exception as e:
            self._log(f"Error discarding changes for {file_path_str}: {e}")

    def get_head_content(self, file_path_str: str) -> str | None:
        if not self.repo:
            return None
        try:
            return self.repo.git.show(f"HEAD:{file_path_str}")
        except git.GitCommandError:
            return ""
        except Exception as e:
            print(f"[GitManager] Error getting HEAD content for {file_path_str}: {e}")
            return None
