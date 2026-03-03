#!/bin/bash
# Get stress levels for a date
# Usage: stress.sh [YYYY-MM-DD] (default: today)

DATE="${1:-$(date +%Y-%m-%d)}"
NEXT_DATE=$(date -d "${DATE} + 1 day" +%Y-%m-%d 2>/dev/null || date -v+1d -j -f "%Y-%m-%d" "${DATE}" +%Y-%m-%d)

# Daily stress summary
DAILY=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT lowStressPercentage, mediumStressPercentage, highStressPercentage, restStressPercentage, bodyBatteryHighestValue, bodyBatteryLowestValue FROM DailyStats WHERE time >= '${DATE}T00:00:00Z' AND time < '${NEXT_DATE}T00:00:00Z' LIMIT 1" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo "=== Stress Summary for ${DATE} ==="
echo "$DAILY" | jq -r '
  .results[0].series[0] // empty |
  .values[0] |
  "Low Stress: \(.[1])%",
  "Medium Stress: \(.[2])%",
  "High Stress: \(.[3])%",
  "Rest: \(.[4])%",
  "Body Battery High: \(.[5])",
  "Body Battery Low: \(.[6])"
' 2>/dev/null || echo "No stress data for ${DATE}"

# Current stress (latest intraday reading)
CURRENT=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT last(\"stressLevel\") FROM \"StressIntraday\" WHERE time >= '${DATE}T00:00:00Z'" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo ""
echo "=== Current Stress ==="
echo "$CURRENT" | jq -r '
  .results[0].series[0] // empty |
  .values[0] |
  "Time: \(.[0])",
  "Level: \(.[1]) \(if .[1] <= 25 then "(rest)" elif .[1] <= 50 then "(low)" elif .[1] <= 75 then "(medium)" else "(high)" end)"
' 2>/dev/null || echo "No current stress reading"
