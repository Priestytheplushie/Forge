import os
import time
import json
import difflib
from pathlib import Path
from PySide6.QtCore import QObject

LOCAL_HISTORY_CAP = 10


class HistoryManager(QObject):
    """Manages the local file history saved to the .forge directory."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace_path = None

    def set_workspace_path(self, path: str):
        self.workspace_path = Path(path)

    def _get_history_path(self, file_path: Path) -> Path | None:
        if not self.workspace_path:
            return None
        try:
            relative_path = file_path.relative_to(self.workspace_path)
            return self.workspace_path / ".forge" / "history" / relative_path
        except ValueError:
            return None

    def record_save(self, file_path_str: str, content: str):
        file_path = Path(file_path_str)
        history_dir = self._get_history_path(file_path)
        if not history_dir:
            return

        try:
            history_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)

            history_file = history_dir / f"{timestamp}{file_path.suffix}"
            meta_file = history_dir / f"{timestamp}{file_path.suffix}.meta.json"

            additions, deletions = 0, 0
            previous_snapshots = self.get_history_for_file(file_path_str)
            if previous_snapshots:
                last_snapshot_path, _ = previous_snapshots[0]
                last_content = self.get_history_content(str(last_snapshot_path))
                if last_content is not None:
                    diff = difflib.unified_diff(
                        last_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                    )
                    for line in diff:
                        if line.startswith("+") and not line.startswith("+++"):
                            additions += 1
                        elif line.startswith("-") and not line.startswith("---"):
                            deletions += 1

            with open(history_file, "w", encoding="utf-8") as f:
                f.write(content)

            metadata = {
                "timestamp": timestamp,
                "additions": additions,
                "deletions": deletions,
                "pinned": False,
                "name": None,
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f)

            print(f"[HistoryManager] Recorded snapshot: {history_file}")
            self._prune_history(history_dir)
        except Exception as e:
            print(f"[HistoryManager] Error recording history: {e}")

    def _prune_history(self, history_dir: Path):
        try:
            snapshots_with_meta = self.get_history_for_file(str(history_dir))

            unpinned = [
                (p, m) for p, m in snapshots_with_meta if not m.get("pinned", False)
            ]

            if len(unpinned) > LOCAL_HISTORY_CAP:
                to_delete = sorted(unpinned, key=lambda item: item[1]["timestamp"])
                for old_path, _ in to_delete[: len(unpinned) - LOCAL_HISTORY_CAP]:
                    self.delete_snapshot(str(old_path))
        except Exception as e:
            print(f"[HistoryManager] Error pruning history: {e}")

    def get_history_for_file(self, file_path_str: str) -> list[tuple[Path, dict]]:
        file_path = Path(file_path_str)
        history_dir = self._get_history_path(file_path)
        if not history_dir or not history_dir.exists():
            return []

        try:
            entries = []
            for item in history_dir.iterdir():
                if item.name.endswith(".meta.json"):
                    continue
                meta_path = item.with_suffix(f"{item.suffix}.meta.json")
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        entries.append((item, metadata))

            return sorted(entries, key=lambda x: x[1]["timestamp"], reverse=True)
        except Exception as e:
            print(f"[HistoryManager] Error retrieving history: {e}")
            return []

    def get_history_content(self, history_file_path: str) -> str | None:
        try:
            with open(history_file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"[HistoryManager] Error reading history content: {e}")
            return None

    def update_snapshot_meta(self, history_file_path: str, new_data: dict):
        meta_path = Path(history_file_path).with_suffix(
            f"{Path(history_file_path).suffix}.meta.json"
        )
        if not meta_path.exists():
            return

        try:
            with open(meta_path, "r+", encoding="utf-8") as f:
                metadata = json.load(f)
                metadata.update(new_data)
                f.seek(0)
                json.dump(metadata, f)
                f.truncate()
        except Exception as e:
            print(
                f"[HistoryManager] Error updating metadata for {history_file_path}: {e}"
            )

    def delete_snapshot(self, history_file_path: str):
        snapshot_path = Path(history_file_path)
        meta_path = snapshot_path.with_suffix(f"{snapshot_path.suffix}.meta.json")
        try:
            if snapshot_path.exists():
                snapshot_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
            print(f"[HistoryManager] Deleted snapshot {snapshot_path}")
        except Exception as e:
            print(f"[HistoryManager] Error deleting snapshot {history_file_path}: {e}")
