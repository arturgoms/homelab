#!/bin/bash
set -euo pipefail

echo "=== Installing srv backup system ==="

# Install dependencies
echo "[1/4] Installing dependencies..."
if ! command -v rsync &>/dev/null; then
  apt-get update -qq || true
  apt-get install -y -qq rsync
fi

if ! command -v yq &>/dev/null; then
  echo "  Installing yq..."
  wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
  chmod +x /usr/local/bin/yq
fi

# Make scripts executable
echo "[2/4] Setting permissions..."
chmod +x /srv/backup/backup.sh /srv/backup/restore.sh

# Symlink systemd units
echo "[3/4] Installing systemd units..."
ln -sf /srv/backup/srv-backup.service /etc/systemd/system/srv-backup.service
ln -sf /srv/backup/srv-backup.timer /etc/systemd/system/srv-backup.timer
systemctl daemon-reload

# Enable timer
echo "[4/4] Enabling backup timer..."
systemctl enable --now srv-backup.timer

echo ""
echo "=== Installation complete ==="
echo "Timer status:"
systemctl status srv-backup.timer --no-pager
echo ""
echo "Next run: $(systemctl list-timers srv-backup.timer --no-pager | tail -2 | head -1)"
echo ""
echo "To run a manual backup: sudo /srv/backup/backup.sh"
