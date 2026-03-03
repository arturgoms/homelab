#!/bin/bash
# Run this on the ollama machine (192.168.1.18) with sudo:
#   sudo bash remote-setup.sh
set -euo pipefail

IFACE="eno1"

echo "=== Enabling WOL on $IFACE ==="
ethtool -s "$IFACE" wol g
ethtool "$IFACE" | grep Wake-on

echo "=== Persisting WOL via networkd-dispatcher ==="
mkdir -p /etc/networkd-dispatcher/configuring.d
cat > /etc/networkd-dispatcher/configuring.d/wol.sh << 'WOLEOF'
#!/bin/bash
ethtool -s eno1 wol g
WOLEOF
chmod +x /etc/networkd-dispatcher/configuring.d/wol.sh

echo "=== Installing autosleep script ==="
cat > /usr/local/bin/ollama-autosleep.sh << 'SLEEPEOF'
#!/bin/bash
# Don't suspend if models are loaded (ollama unloads after 5min idle)
MODELS_LOADED=$(curl -sf http://localhost:11434/api/ps 2>/dev/null | grep -c '"model"' || true)
[ "${MODELS_LOADED:-0}" -gt 0 ] && exit 0

# Don't suspend if someone is logged in via SSH
LOGGED_IN=$(who | wc -l)
[ "$LOGGED_IN" -gt 0 ] && exit 0

logger -t ollama-autosleep "Ollama idle, suspending"
systemctl suspend
SLEEPEOF
chmod +x /usr/local/bin/ollama-autosleep.sh

echo "=== Installing systemd service and timer ==="
cat > /etc/systemd/system/ollama-autosleep.service << 'SVCEOF'
[Unit]
Description=Ollama auto-sleep idle check

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ollama-autosleep.sh
SVCEOF

cat > /etc/systemd/system/ollama-autosleep.timer << 'TMREOF'
[Unit]
Description=Check Ollama idle every 2 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
TMREOF

systemctl daemon-reload
systemctl enable --now ollama-autosleep.timer

echo "=== Verifying ==="
systemctl status ollama-autosleep.timer --no-pager
echo ""
echo "Setup complete. WOL enabled, autosleep timer active."
