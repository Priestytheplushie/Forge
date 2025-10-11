from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThread
from pathlib import Path
import git
import os
import datetime
import time


class CloneWorker(QThread):
    """Worker thread to run git clone in the background."""

    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, url, path, parent=None):
        super().__init__(parent)
        self.url, self.path = url, path

    def run(self):
        try:

            class CloneProgress(git.remote.RemoteProgress):
                def update(self, op_code, cur_count, max_count=None, message=""):
                    self.progress.emit(f"-> {message}")

            self.progress.emit(f"Cloning '{self.url}' into '{self.path}'...")
            git.Repo.clone_from(self.url, self.path, progress=CloneProgress())
            self.finished.emit(True, self.path)
        except git.GitCommandError as e:
            self.finished.emit(False, str(e.stderr))
        except Exception as e:
            self.finished.emit(False, str(e))


class GitStatusWorker(QThread):
    """Worker thread to run git status checks in the background."""

    status_updated = Signal(dict)

    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.is_running = True

    def run(self):
        while self.is_running:
            if not self.repo or not self.repo.git_dir:
                time.sleep(2)
                continue

            status_data = {}
            try:

                all_branches = {"local": [], "remote": []}
                current_branch_name = self.repo.active_branch.name
                for head in self.repo.heads:
                    all_branches["local"].append((head.name, "up-to-date"))
                for remote in self.repo.remotes:
                    for ref in remote.refs:
                        if ref.name != f"{remote.name}/HEAD":
                            all_branches["remote"].append((ref.name, "up-to-date"))
                status_data["branches"] = all_branches
                status_data["current_branch"] = current_branch_name

                tracking_branch = self.repo.active_branch.tracking_branch()
                if tracking_branch:
                    ahead = sum(
                        1
                        for _ in self.repo.iter_commits(
                            f"{tracking_branch.name}..{current_branch_name}"
                        )
                    )
                    behind = sum(
                        1
                        for _ in self.repo.iter_commits(
                            f"{current_branch_name}..{tracking_branch.name}"
                        )
                    )
                    status_data["remote_status"] = (ahead, behind)
                else:
                    status_data["remote_status"] = (0, 0)

                try:
                    head_commit = self.repo.head.commit
                    status_data["head_commit"] = (
                        head_commit.author.name,
                        head_commit.committed_date,
                        head_commit.hexsha[:7],
                    )
                except ValueError:
                    status_data["head_commit"] = ("", 0, "")

                staged = [
                    {"path": d.a_path or d.b_path, "status": d.change_type}
                    for d in self.repo.index.diff("HEAD", R=True)
                ]
                unstaged = [
                    {"path": d.a_path or d.b_path, "status": d.change_type}
                    for d in self.repo.index.diff(None)
                ]
                untracked = [
                    p for p in self.repo.untracked_files if not self.repo.ignored(p)
                ]
                for path in untracked:
                    unstaged.append({"path": path, "status": "A"})

                status_data["staged"] = staged
                status_data["unstaged"] = unstaged
                status_data["is_merge_conflict"] = (
                    Path(self.repo.git_dir) / "MERGE_HEAD"
                ).exists()

            except TypeError:
                status_data["current_branch"] = (
                    self.repo.head.object.hexsha[:7] if self.repo.head else "Detached"
                )
                status_data["remote_status"] = (0, 0)
            except Exception as e:
                print(f"[GitStatusWorker] Error: {e}")
                status_data["error"] = str(e)

            self.status_updated.emit(status_data)
            time.sleep(2)

    def stop(self):
        self.is_running = False


class GitManager(QObject):
    repo_status_changed = Signal(bool)
    status_changed = Signal(list, list)
    branch_changed = Signal(str)
    branches_updated = Signal(dict, str)
    remote_status_changed = Signal(int, int)
    git_command_output = Signal(str)
    upstream_branch_not_found = Signal()
    merge_conflict_detected = Signal(list)
    clone_progress = Signal(str)
    clone_finished = Signal(bool, str)
    head_commit_changed = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace_path = None
        self.repo = None
        self.clone_worker = None
        self.status_worker = None
        self.is_in_merge_conflict = False

    def _log(self, message: str):
        self.git_command_output.emit(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}"
        )

    def _get_relative_time(self, commit_time):
        diff = time.time() - commit_time
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{int(diff / 60)}m ago"
        if diff < 86400:
            return f"{int(diff / 3600)}h ago"
        return f"{int(diff / 86400)}d ago"

    @Slot(str)
    def set_workspace_path(self, path: str):
        self.workspace_path = Path(path)
        if self.status_worker:
            self.status_worker.stop()
            self.status_worker.wait()
            self.status_worker = None

        try:
            self.repo = git.Repo(path, search_parent_directories=True)
            self.repo_status_changed.emit(True)
            self.status_worker = GitStatusWorker(self.repo, self)
            self.status_worker.status_updated.connect(self.on_status_updated)
            self.status_worker.start()
        except git.InvalidGitRepositoryError:
            self.repo = None
            self.repo_status_changed.emit(False)
            self.branches_updated.emit({}, "")
        except Exception as e:
            self._log(f"Error initializing Git: {e}")
            self.repo = None
            self.repo_status_changed.emit(False)
            self.branches_updated.emit({}, "")

    @Slot(dict)
    def on_status_updated(self, status_data: dict):
        if "error" in status_data:
            return

        self.branch_changed.emit(status_data.get("current_branch", ""))
        self.branches_updated.emit(
            status_data.get("branches", {}), status_data.get("current_branch", "")
        )

        ahead, behind = status_data.get("remote_status", (0, 0))
        self.remote_status_changed.emit(ahead, behind)

        author, cdate, sha = status_data.get("head_commit", ("", 0, ""))
        if author:
            self.head_commit_changed.emit(author, self._get_relative_time(cdate), sha)
        else:
            self.head_commit_changed.emit("", "", "")

        staged = status_data.get("staged", [])
        unstaged = status_data.get("unstaged", [])
        self.status_changed.emit(staged, unstaged)

    @Slot()
    def refresh_status(self):

        if not self.repo or not self.repo.git_dir:
            return

        if (Path(self.repo.git_dir) / "MERGE_HEAD").exists():
            unresolved, staged_merge = set(), set()
            for line in self.repo.git.status("--porcelain").strip().split("\n"):
                if not line:
                    continue
                status, path = line[:2], line[3:].strip().replace('"', "")
                if status in ("DD", "AU", "UD", "UA", "DU", "AA", "UU"):
                    unresolved.add(path)
                if status[0] != " " and status not in (
                    "DD",
                    "AU",
                    "UD",
                    "UA",
                    "DU",
                    "AA",
                    "UU",
                ):
                    staged_merge.add(path)

            unresolved = {p for p in unresolved if not p.startswith(".forge/")}
            staged_merge = {p for p in staged_merge if not p.startswith(".forge/")}

            if not self.is_in_merge_conflict:
                self.is_in_merge_conflict = True
                self.merge_conflict_detected.emit(sorted(list(unresolved)))

            self.status_changed.emit(
                sorted(list(staged_merge)), sorted(list(unresolved))
            )
        elif self.is_in_merge_conflict:
            self.is_in_merge_conflict = False

    def get_file_commit_history(self, file_path_str: str) -> list:
        if not self.repo or not file_path_str:
            return []
        try:
            relative_path = Path(file_path_str).relative_to(self.repo.working_dir)
            commits = list(self.repo.iter_commits(paths=str(relative_path)))
            return [
                {
                    "sha": c.hexsha,
                    "author": c.author.name,
                    "timestamp": c.committed_date * 1000,
                    "message": c.summary,
                }
                for c in commits
            ]
        except Exception:
            return []

    def get_commit_diff(self, file_path_str: str, sha: str) -> tuple[str, str]:
        if not self.repo:
            return ("", "")
        try:
            commit = self.repo.commit(sha)
            relative_path = str(Path(file_path_str).relative_to(self.repo.working_dir))
            modified_content = self.repo.git.show(f"{sha}:{relative_path}")
            original_content = ""
            if commit.parents:
                parent_sha = commit.parents[0].hexsha
                try:
                    original_content = self.repo.git.show(
                        f"{parent_sha}:{relative_path}"
                    )
                except git.GitCommandError:
                    original_content = ""
            return (original_content, modified_content)
        except Exception as e:
            self._log(f"Error getting commit diff: {e}")
            return ("", "")

    @Slot(str)
    def checkout_branch(self, branch_name: str):
        if not self.repo:
            return
        try:
            self.repo.git.checkout(branch_name)
            self.refresh_status()
        except git.GitCommandError as e:
            self._log(f"Error checking out branch: {e.stderr.strip()}")

    @Slot(str, str)
    def create_branch(self, name: str, base: str):
        if not self.repo:
            return
        try:
            self.repo.create_head(name, base).checkout()
            self.refresh_status()
        except git.GitCommandError as e:
            self._log(f"Error creating branch: {e.stderr.strip()}")

    @Slot(str, bool, str)
    def merge_branch(self, target_branch: str, squash: bool = False, message: str = ""):
        if not self.repo:
            return
        try:
            args = ["--no-ff"]
            if squash:
                args.append("--squash")
            self.repo.git.merge(target_branch, *args)
            if squash:
                self.repo.index.commit(message)
            elif message:
                self.repo.index.commit(message)
            self.refresh_status()
        except git.GitCommandError as e:
            if "merge conflict" in e.stderr.lower():
                self.refresh_status()
            else:
                self._log(f"Error merging: {e.stderr.strip()}")

    @Slot(str)
    def rebase_branch(self, target_branch: str):
        if not self.repo:
            return
        try:
            self.repo.git.rebase(target_branch)
            self.refresh_status()
        except git.GitCommandError as e:
            if (
                "merge conflict" in e.stderr.lower()
                or "could not apply" in e.stderr.lower()
            ):
                self.refresh_status()
            else:
                self._log(f"Error rebasing: {e.stderr.strip()}")

    @Slot(str, str)
    def rename_branch(self, old_name: str, new_name: str):
        if not self.repo:
            return
        try:
            self.repo.git.branch("-m", old_name, new_name)
            self.refresh_status()
        except git.GitCommandError as e:
            self._log(f"Error renaming branch: {e.stderr.strip()}")

    @Slot(str, bool)
    def delete_branch(self, branch_name: str, is_remote: bool):
        if not self.repo:
            return
        try:
            if is_remote:
                remote_name, remote_branch_name = branch_name.split("/", 1)
                self.repo.git.push(remote_name, "--delete", remote_branch_name)
            else:
                self.repo.git.branch("-d", branch_name)
            self.refresh_status()
        except git.GitCommandError as e:
            self._log(f"Error deleting branch: {e.stderr.strip()}")

    def initialize_repo(self):
        if self.workspace_path and not self.repo:
            try:
                self.repo = git.Repo.init(self.workspace_path)
                self.set_workspace_path(str(self.workspace_path))
            except Exception as e:
                self._log(f"Error initializing repository: {e}")

    def clone_repo(self, url: str, path: str):
        if self.clone_worker and self.clone_worker.isRunning():
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
                f"Pushing and setting upstream for branch '{self.repo.active_branch.name}'..."
            )
            self.repo.git.push(
                "--set-upstream",
                self.repo.remotes.origin.name,
                self.repo.active_branch.name,
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
            unmerged_blobs = self.repo.index.unmerged_blobs()
            if self.is_in_merge_conflict and unmerged_blobs:
                self._log(
                    f"Error: Cannot commit. You still have {len(unmerged_blobs)} unresolved conflicts."
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

    def discard_changes(self, file_paths: list[str]):
        if not self.repo:
            return
        try:
            untracked = [p for p in file_paths if p in self.repo.untracked_files]
            tracked = [p for p in file_paths if p not in untracked]
            for p in untracked:
                os.remove(Path(self.repo.working_dir) / p)
            if tracked:
                self.repo.git.checkout("--", *tracked)
            self.refresh_status()
        except Exception as e:
            self._log(f"Error discarding changes: {e}")

    def get_head_content(self, file_path_str: str) -> str | None:
        if not self.repo:
            return None
        try:
            relative_path = str(Path(file_path_str).relative_to(self.repo.working_dir))
            return self.repo.git.show(f"HEAD:{relative_path}")
        except git.GitCommandError:
            return ""
        except Exception as e:
            self._log(f"Error getting HEAD content for {file_path_str}: {e}")
            return None
