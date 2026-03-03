#!/bin/bash
# Get step count for a date
# Usage: steps.sh [YYYY-MM-DD] (default: today)

DATE="${1:-$(date +%Y-%m-%d)}"
NEXT_DATE=$(date -d "${DATE} + 1 day" +%Y-%m-%d 2>/dev/null || date -v+1d -j -f "%Y-%m-%d" "${DATE}" +%Y-%m-%d)

RESULT=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT totalSteps, totalDistanceMeters, activeKilocalories, moderateIntensityMinutes, vigorousIntensityMinutes, floorsAscended FROM DailyStats WHERE time >= '${DATE}T00:00:00Z' AND time < '${NEXT_DATE}T00:00:00Z' LIMIT 1" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo "$RESULT" | jq -r '
  .results[0].series[0] // empty |
  .values[0] |
  "Date: \(.[0])",
  "Steps: \(.[1])",
  "Distance: \(.[2] / 1000 | . * 100 | floor / 100) km",
  "Active Calories: \(.[3])",
  "Moderate Minutes: \(.[4])",
  "Vigorous Minutes: \(.[5])",
  "Floors: \(.[6])"
' 2>/dev/null || echo "No step data for ${DATE}"
