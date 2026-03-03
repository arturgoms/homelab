#!/bin/bash
# Get recent running activities
# Usage: recent-runs.sh [number] (default: 5)

COUNT="${1:-5}"

RESULT=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT activityName, distance, movingDuration, averageSpeed, averageHR, maxHR, calories FROM ActivitySummary WHERE activityType = 'running' ORDER BY time DESC LIMIT ${COUNT}" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo "$RESULT" | jq -r '
  .results[0].series[0] // empty |
  .values[] |
  "Date: \(.[0])",
  "Name: \(.[1])",
  "Distance: \(.[2] / 1000 | . * 100 | floor / 100) km",
  "Duration: \(.[3] / 60000 | floor)m",
  "Avg Pace: \((.[3] / 60000) / (.[2] / 1000) | . * 10 | floor / 10) min/km",
  "Avg HR: \(.[5]) bpm (Max: \(.[6]))",
  "Calories: \(.[7])",
  "---"
' 2>/dev/null || echo "No running data available"
