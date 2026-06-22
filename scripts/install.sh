#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/btrfs-snapshot-sync"
BIN_LINK="/usr/local/bin/btrfs-snapshot-sync"
CONFIG_DIR="/etc/btrfs-snapshot-sync"
SYSTEMD_DIR="/etc/systemd/system"

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root." >&2
    exit 1
fi

echo "Installing btrfs-snapshot-sync..."

cp -r . "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/btrfs_backup.py"

ln -sf "$INSTALL_DIR/btrfs_backup.py" "$BIN_LINK"

mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
    cp config/config.json "$CONFIG_DIR/config.json"
    echo "Default config written to $CONFIG_DIR/config.json"
    echo "Edit it before enabling the timer."
fi

cp systemd/btrfs-snapshot-sync.service "$SYSTEMD_DIR/"
cp systemd/btrfs-snapshot-sync.timer "$SYSTEMD_DIR/"

systemctl daemon-reload

echo ""
echo "Installation complete."
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_DIR/config.json"
echo "  2. Set up SSH key: ssh-keygen -t ed25519 -f /root/.ssh/backup_id_ed25519"
echo "  3. Copy public key to backup server: ssh-copy-id -i /root/.ssh/backup_id_ed25519.pub backup@<host>"
echo "  4. Enable the timer: systemctl enable --now btrfs-snapshot-sync.timer"
echo "  5. Test manually: btrfs-snapshot-sync run"