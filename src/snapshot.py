import subprocess
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotManager:
    def __init__(self, config):
        self.source_subvolume = config["source_subvolume"]
        self.snapshot_dir = Path(config["snapshot_dir"])
        self.snapshot_prefix = config.get("snapshot_prefix", "backup")

    def _run(self, cmd, check=True):
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
        return result

    def create_snapshot(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{self.snapshot_prefix}_{timestamp}"
        dest = self.snapshot_dir / name

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._run([
            "btrfs", "subvolume", "snapshot", "-r",
            self.source_subvolume,
            str(dest)
        ])

        logger.info("Created snapshot: %s", dest)
        return dest

    def list_snapshots(self):
        if not self.snapshot_dir.exists():
            return []

        result = self._run(["btrfs", "subvolume", "list", "-o", str(self.snapshot_dir)])
        snapshots = []

        for line in result.stdout.strip().splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            path = parts[-1]
            name = os.path.basename(path)
            if name.startswith(self.snapshot_prefix):
                full_path = self.snapshot_dir / name
                snapshots.append(full_path)

        snapshots.sort(key=lambda p: p.name)
        return snapshots

    def delete_snapshot(self, path):
        self._run(["btrfs", "subvolume", "delete", str(path)])
        logger.info("Deleted snapshot: %s", path)

    def get_latest_snapshot(self):
        snapshots = self.list_snapshots()
        return snapshots[-1] if snapshots else None
