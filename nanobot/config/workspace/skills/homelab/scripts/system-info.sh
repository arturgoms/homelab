#!/bin/bash
# Get system info from Glances API
# Usage: system-info.sh

GLANCES="${GLANCES_URL:-http://localhost:61208}"

echo "=== CPU ==="
curl -s "${GLANCES}/api/4/cpu" | jq -r '"Usage: \(.total)%\nUser: \(.user)%\nSystem: \(.system)%"' 2>/dev/null || echo "Glances CPU unavailable"

echo ""
echo "=== Memory ==="
curl -s "${GLANCES}/api/4/mem" | jq -r '"Usage: \(.percent)%\nUsed: \(.used / 1073741824 | . * 10 | floor / 10) GB\nTotal: \(.total / 1073741824 | . * 10 | floor / 10) GB"' 2>/dev/null || echo "Glances memory unavailable"

echo ""
echo "=== Disk ==="
curl -s "${GLANCES}/api/4/fs" | jq -r '.[] | "\(.mnt_point): \(.percent)% used (\(.used / 1073741824 | . * 10 | floor / 10) / \(.size / 1073741824 | . * 10 | floor / 10) GB)"' 2>/dev/null || echo "Glances disk unavailable"

echo ""
echo "=== Uptime ==="
curl -s "${GLANCES}/api/4/uptime" | jq -r '.' 2>/dev/null || echo "Glances uptime unavailable"
