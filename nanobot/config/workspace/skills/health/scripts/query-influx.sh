#!/bin/bash
# Generic InfluxDB 1.x HTTP API query
# Usage: query-influx.sh "SELECT * FROM measurement LIMIT 10"

QUERY="$1"

if [ -z "$QUERY" ]; then
  echo "Usage: query-influx.sh \"SELECT ...\""
  exit 1
fi

curl -s -G \
  "http://${INFLUXDB_HOST}:${INFLUXDB_PORT}/query" \
  --data-urlencode "db=${INFLUXDB_DB}" \
  --data-urlencode "q=${QUERY}" \
  -u "${INFLUXDB_USER}:${INFLUXDB_PASSWORD}" \
  | jq -r '
    .results[0].series[0] // empty |
    .columns as $cols |
    .values[] |
    [range(0; length)] |
    map("\($cols[.]): \(.[])") |
    join(" | ")
  ' 2>/dev/null || echo "No data returned or query error"
