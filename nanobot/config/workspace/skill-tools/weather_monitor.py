#!/usr/bin/env python3
"""Weather helper library — forecast fetching and concern detection.

Pure importable module, no CLI. Used by report.py and calendar_monitor.py.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from thresholds import (
    WEATHER_CONCERNING, WEATHER_POP_THRESHOLD,
    WEATHER_TEMP_HOT, WEATHER_TEMP_COLD, WEATHER_WIND_STRONG,
)

TZ = ZoneInfo("America/Sao_Paulo")

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
WEATHER_CITY = os.environ.get("WEATHER_CITY", "Curitiba")
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_forecast():
    """Fetch OWM 5-day/3-hour forecast. Returns list of forecast entries."""
    params = f"q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units=metric&lang=en"
    url = f"{OWM_FORECAST_URL}?{params}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("list", [])


def parse_forecast_entry(entry):
    """Parse a single forecast entry into a convenient dict."""
    dt = datetime.fromtimestamp(entry["dt"], tz=TZ)
    main = entry.get("main", {})
    weather = entry.get("weather", [{}])[0]
    wind = entry.get("wind", {})
    return {
        "dt": dt,
        "temp": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "weather_main": weather.get("main", ""),
        "weather_desc": weather.get("description", ""),
        "pop": entry.get("pop", 0),  # probability of precipitation (0-1)
        "wind_speed": wind.get("speed", 0),
        "rain_3h": entry.get("rain", {}).get("3h", 0),
        "snow_3h": entry.get("snow", {}).get("3h", 0),
    }


def get_today_forecasts(entries):
    """Filter forecast entries to today only."""
    now = datetime.now(TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    result = []
    for e in entries:
        f = parse_forecast_entry(e)
        if today_start <= f["dt"] < today_end:
            result.append(f)
    return result


def find_forecast_for_time(entries, target_time):
    """Find the forecast entry closest to a target time."""
    parsed = [parse_forecast_entry(e) for e in entries]
    best = None
    best_diff = None
    for f in parsed:
        diff = abs((f["dt"] - target_time).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best = f
    return best


def is_concerning(forecast):
    """Check if a forecast entry has concerning weather."""
    if not forecast:
        return False, []
    reasons = []
    if forecast["weather_main"] in WEATHER_CONCERNING:
        reasons.append(forecast["weather_desc"])
    if forecast["pop"] >= WEATHER_POP_THRESHOLD:
        reasons.append(f"{forecast['pop']*100:.0f}% chance of precipitation")
    if forecast["temp"] is not None and forecast["temp"] > WEATHER_TEMP_HOT:
        reasons.append(f"extreme heat ({forecast['temp']:.0f}\u00b0C)")
    if forecast["temp"] is not None and forecast["temp"] < WEATHER_TEMP_COLD:
        reasons.append(f"very cold ({forecast['temp']:.0f}\u00b0C)")
    if forecast["wind_speed"] > WEATHER_WIND_STRONG:
        reasons.append(f"strong wind ({forecast['wind_speed']:.0f} m/s)")
    return len(reasons) > 0, reasons
