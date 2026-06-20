import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RemoteTransfer:
    def __init__(self, config):
        remote = config["remote"]
        self.host = remote["host"]
        self.user = remote["user"]
        self.port = remote.get("port", 22)
        self.remote_dir = remote["backup_dir"]
        self.ssh_key = remote.get("ssh_key")
        self.compress = config.get("transfer", {}).get("compress", True)

    def _ssh_args(self):
        args = ["ssh", "-p", str(self.port), "-o", "StrictHostKeyChecking=accept-new"]
        if self.ssh_key:
            args += ["-i", self.ssh_key]
        return args

    def _remote_target(self):
        return f"{self.user}@{self.host}"

    def _run_piped(self, send_cmd, recv_cmd):
        logger.debug("Send: %s", " ".join(send_cmd))
        logger.debug("Recv: %s", " ".join(recv_cmd))

        send_proc = subprocess.Popen(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        recv_proc = subprocess.Popen(recv_cmd, stdin=send_proc.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        send_proc.stdout.close()
        recv_out, recv_err = recv_proc.communicate()
        send_proc.wait()

        if send_proc.returncode != 0:
            _, send_err = send_proc.communicate()
            raise RuntimeError(f"btrfs send failed: {send_err.decode()}")

        if recv_proc.returncode != 0:
            raise RuntimeError(f"btrfs receive failed: {recv_err.decode()}")

        return True

    def send_snapshot(self, snapshot_path, parent_path=None):
        snapshot_path = Path(snapshot_path)

        send_cmd = ["btrfs", "send"]
        if parent_path:
            send_cmd += ["-p", str(parent_path)]
        send_cmd.append(str(snapshot_path))

        ssh_args = self._ssh_args()
        recv_cmd = ssh_args + [
            self._remote_target(),
            f"btrfs receive {self.remote_dir}"
        ]

        logger.info("Sending snapshot %s to %s:%s", snapshot_path.name, self.host, self.remote_dir)
        self._run_piped(send_cmd, recv_cmd)
        logger.info("Transfer complete: %s", snapshot_path.name)

    def list_remote_snapshots(self, prefix):
        ssh_args = self._ssh_args()
        cmd = ssh_args + [
            self._remote_target(),
            f"btrfs subvolume list -o {self.remote_dir} 2>/dev/null | awk '{{print $NF}}' | xargs -I{{}} basename {{}}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []

        names = []
        for line in result.stdout.strip().splitlines():
            name = line.strip()
            if name.startswith(prefix):
                names.append(name)

        names.sort()
        return names

    def delete_remote_snapshot(self, name):
        path = f"{self.remote_dir}/{name}"
        ssh_args = self._ssh_args()
        cmd = ssh_args + [
            self._remote_target(),
            f"btrfs subvolume delete {path}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to delete remote snapshot {name}: {result.stderr}")

        logger.info("Deleted remote snapshot: %s", name)

    def ensure_remote_dir(self):
        ssh_args = self._ssh_args()
        cmd = ssh_args + [
            self._remote_target(),
            f"mkdir -p {self.remote_dir}"
        ]
        subprocess.run(cmd, check=True, capture_output=True)
