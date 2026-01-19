#!/bin/bash

source "/srv/garmin-fetch-data/garmin-grafana/venv/bin/activate"
today=$(date +'%Y-%m-%d')

/srv/garmin-fetch-data/garmin-grafana/venv/bin/python /srv/garmin-fetch-data/garmin-grafana/src/garmin_grafana/influxdb_exporter.py --start-date=2025-01-01 --end-date=$today

date="2025-01-01_to_$today"
echo "Date: $date"

mkdir -p /srv/garmin-fetch-data/export/$date

file_path=$(find "/tmp/" -name "GarminStats*$date.zip")
echo "File path: $file_path"

unzip $file_path -d "/srv/garmin-fetch-data/export/$date"

rm $file_path
