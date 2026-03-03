#!/bin/bash
# Check health of homelab services
# Usage: service-check.sh [service-name] (default: all)

FILTER="${1:-}"
IP="${HOMELAB_IP:-localhost}"

declare -A SERVICES
SERVICES=(
  ["Portainer"]="http://${IP}:9000"
  ["Traefik"]="http://traefik.arturgomes.com/"
  ["Dashy"]="https://dashy.arturgomes.com/"
  ["Home Assistant"]="http://${IP}:8123"
  ["Immich"]="http://${IP}:3001"
  ["n8n"]="http://${IP}:5678"
  ["Grafana"]="http://${IP}:8087"
  ["InfluxDB"]="http://${IP}:8086/health"
  ["InfluxDB 1.x"]="http://${IP}:8088/ping"
  ["Prometheus"]="http://${IP}:9090"
  ["Graphite"]="http://${IP}:8050"
  ["Whisper ASR"]="http://${IP}:8001"
  ["Open WebUI"]="http://${IP}:8010"
  ["SearXNG"]="http://${IP}:8888"
  ["Syncthing"]="http://${IP}:8384"
  ["Glances"]="http://${IP}:61208/api/4/status"
)

UP=0
DOWN=0
TOTAL=0

for NAME in "${!SERVICES[@]}"; do
  # Filter by name if specified
  if [ -n "$FILTER" ]; then
    if ! echo "$NAME" | grep -qi "$FILTER"; then
      continue
    fi
  fi

  URL="${SERVICES[$NAME]}"
  TOTAL=$((TOTAL + 1))

  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$URL" 2>/dev/null)

  if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
    echo "OK  | ${NAME} (${HTTP_CODE})"
    UP=$((UP + 1))
  else
    echo "FAIL| ${NAME} (${HTTP_CODE})"
    DOWN=$((DOWN + 1))
  fi
done

echo ""
echo "Summary: ${UP}/${TOTAL} up, ${DOWN} down"
