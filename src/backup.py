import logging
import sys
from pathlib import Path

from .config import load_config, validate_config
from .snapshot import SnapshotManager
from .transfer import RemoteTransfer
from .retention import RetentionPolicy

logger = logging.getLogger(__name__)


def setup_logging(config):
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)
    log_file = log_config.get("file")

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            handlers.append(logging.FileHandler(log_file))
        except PermissionError:
            pass

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers
    )


class BackupRunner:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        validate_config(self.config)
        setup_logging(self.config)

        self.snapshots = SnapshotManager(self.config)
        self.retention = RetentionPolicy(self.config)

        transfer_enabled = self.config.get("transfer", {}).get("enabled", True)
        self.transfer = RemoteTransfer(self.config) if transfer_enabled else None

    def run(self):
        logger.info("Starting backup cycle")

        snapshot_path = self._create_snapshot()
        if not snapshot_path:
            return False

        if self.transfer:
            self._send_snapshot(snapshot_path)
            self._cull_remote()

        self._cull_local()
        logger.info("Backup cycle complete")
        return True

    def _create_snapshot(self):
        try:
            path = self.snapshots.create_snapshot()
            return path
        except Exception as e:
            logger.error("Snapshot creation failed: %s", e)
            return None

    def _send_snapshot(self, snapshot_path):
        try:
            self.transfer.ensure_remote_dir()

            prefix = self.config["snapshot_prefix"]
            remote_names = self.transfer.list_remote_snapshots(prefix)

            parent_path = None
            if remote_names:
                latest_remote = remote_names[-1]
                local_parent = Path(self.config["snapshot_dir"]) / latest_remote
                if local_parent.exists():
                    parent_path = local_parent
                    logger.info("Using parent snapshot for incremental send: %s", latest_remote)

            self.transfer.send_snapshot(snapshot_path, parent_path=parent_path)
        except Exception as e:
            logger.error("Remote transfer failed: %s", e)

    def _cull_local(self):
        try:
            snapshots = self.snapshots.list_snapshots()
            prefix = self.config["snapshot_prefix"]
            to_delete = self.retention.select_snapshots_to_delete(snapshots, prefix)
            for path in to_delete:
                self.snapshots.delete_snapshot(path)
        except Exception as e:
            logger.error("Local cleanup failed: %s", e)

    def _cull_remote(self):
        try:
            prefix = self.config["snapshot_prefix"]
            remote_names = self.transfer.list_remote_snapshots(prefix)
            to_delete = self.retention.select_snapshots_to_delete(remote_names, prefix)
            for name in to_delete:
                self.transfer.delete_remote_snapshot(name)
        except Exception as e:
            logger.error("Remote cleanup failed: %s", e)
