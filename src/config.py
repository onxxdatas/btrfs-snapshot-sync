import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "source_subvolume": "/",
    "snapshot_dir": "/mnt/snapshots",
    "snapshot_prefix": "backup",
    "retention": {
        "keep_hourly": 24,
        "keep_daily": 7,
        "keep_weekly": 4,
        "keep_monthly": 3
    },
    "transfer": {
        "compress": True,
        "enabled": True
    },
    "remote": {
        "host": "",
        "user": "backup",
        "port": 22,
        "backup_dir": "/mnt/remote-backups",
        "ssh_key": "/root/.ssh/backup_id_ed25519"
    },
    "logging": {
        "level": "INFO",
        "file": "/var/log/btrfs-snapshot-sync.log"
    }
}


def load_config(path=None):
    if path is None:
        candidates = [
            "/etc/btrfs-snapshot-sync/config.json",
            os.path.expanduser("~/.config/btrfs-snapshot-sync/config.json"),
            "config/config.json"
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                path = candidate
                break

    config = dict(DEFAULT_CONFIG)

    if path and os.path.exists(path):
        with open(path) as f:
            user_config = json.load(f)
        config = _deep_merge(config, user_config)

    return config


def _deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def validate_config(config):
    errors = []

    if not config.get("source_subvolume"):
        errors.append("source_subvolume is required")

    if not config.get("snapshot_dir"):
        errors.append("snapshot_dir is required")

    if config.get("transfer", {}).get("enabled"):
        remote = config.get("remote", {})
        if not remote.get("host"):
            errors.append("remote.host is required when transfer is enabled")
        if not remote.get("user"):
            errors.append("remote.user is required when transfer is enabled")

    if errors:
        raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    return True
