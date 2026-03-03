#!/bin/bash
# Get training readiness / recovery status
# Usage: recovery-status.sh

# Training Readiness
TR=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT score, level, sleepScore, recoveryTime, hrvFactorPercent, sleepScoreFactorPercent, stressHistoryFactorPercent, acuteLoad FROM TrainingReadiness ORDER BY time DESC LIMIT 1" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo "=== Training Readiness ==="
echo "$TR" | jq -r '
  .results[0].series[0] // empty |
  .values[0] |
  "Date: \(.[0])",
  "Score: \(.[1])",
  "Level: \(.[2])",
  "Sleep Score: \(.[3])",
  "Recovery Time: \(.[4])h",
  "HRV Factor: \(.[5])%",
  "Sleep Factor: \(.[6])%",
  "Stress History Factor: \(.[7])%",
  "Acute Load: \(.[8])"
' 2>/dev/null || echo "No training readiness data"

# Body Battery (current)
BB=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT bodyBatteryHighestValue, bodyBatteryLowestValue, bodyBatteryAtWakeTime, bodyBatteryDuringSleep FROM DailyStats ORDER BY time DESC LIMIT 1" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo ""
echo "=== Body Battery ==="
echo "$BB" | jq -r '
  .results[0].series[0] // empty |
  .values[0] |
  "Highest: \(.[1])",
  "Lowest: \(.[2])",
  "At Wake: \(.[3])",
  "During Sleep: \(.[4])"
' 2>/dev/null || echo "No body battery data"
