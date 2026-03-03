#!/bin/bash
# Get latest sleep summary from Garmin data
# Usage: sleep-summary.sh [number_of_nights] (default: 1)

NIGHTS="${1:-1}"

RESULT=$(curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=SELECT sleepScore, sleepTimeSeconds, deepSleepSeconds, lightSleepSeconds, remSleepSeconds, awakeSleepSeconds, restingHeartRate, avgOvernightHrv, restlessMomentsCount, awakeCount, averageSpO2Value, lowestSpO2Value, avgSleepStress, bodyBatteryChange FROM SleepSummary ORDER BY time DESC LIMIT ${NIGHTS}" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}")

echo "$RESULT" | jq -r '
  .results[0].series[0] // empty |
  .values[] |
  "Date: \(.[0])",
  "Sleep Score: \(.[1])",
  "Total Sleep: \(.[2] / 3600 | floor)h \((.[2] % 3600) / 60 | floor)m",
  "Deep: \(.[3] / 3600 | . * 10 | floor / 10)h (\(.[3] / .[2] * 100 | floor)%)",
  "Light: \(.[4] / 3600 | . * 10 | floor / 10)h (\(.[4] / .[2] * 100 | floor)%)",
  "REM: \(.[5] / 3600 | . * 10 | floor / 10)h (\(.[5] / .[2] * 100 | floor)%)",
  "Awake: \(.[6] / 60 | floor)m",
  "Resting HR: \(.[7]) bpm",
  "HRV: \(.[8]) ms",
  "Restless Moments: \(.[9])",
  "Awake Count: \(.[10])",
  "SpO2 Avg: \(.[11])% (Low: \(.[12])%)",
  "Sleep Stress: \(.[13])",
  "Body Battery Change: \(.[14])",
  "---"
' 2>/dev/null || echo "No sleep data available"
