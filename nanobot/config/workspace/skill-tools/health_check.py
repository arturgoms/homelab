#!/usr/bin/env python3
"""Proactive health alerts using Garmin data from InfluxDB.

Usage:
    health_check.py stress    — Stress alert (silent if OK)
    health_check.py activity  — New activity celebration (silent if none)
"""
import urllib.request
import urllib.parse
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from thresholds import (
    SLEEP_EXCELLENT, SLEEP_GOOD, SLEEP_FAIR,
    READINESS_PRIME, READINESS_READY, READINESS_FAIR,
    BATTERY_HIGH, BATTERY_MODERATE, BATTERY_LOW,
    STEPS_VERY_ACTIVE, STEPS_ACTIVE, STEPS_MODERATE, STEPS_LIGHT,
    STRESS_LOW, STRESS_MODERATE, STRESS_HIGH,
    STRESS_INTRADAY_HIGH, STRESS_SUSTAINED_COUNT,
    STRESS_DAILY_HIGH_PCT, STRESS_2H_HIGH_PCT,
    BATTERY_DRAIN_ALERT,
)

# --- Config ---

TZ = ZoneInfo("America/Sao_Paulo")
INFLUX_HOST = os.environ.get("INFLUXDB_HOST", "localhost")
INFLUX_PORT = os.environ.get("INFLUXDB_PORT", "8088")
INFLUX_DB = os.environ.get("INFLUXDB_DB", "GarminStats")
INFLUX_USER = os.environ.get("INFLUXDB_USER", "")
INFLUX_PASSWORD = os.environ.get("INFLUXDB_PASSWORD", "")

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".health_check_last_activity.json",
)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --- InfluxDB helpers ---

def influx_query(query):
    """Execute InfluxDB 1.x HTTP query and return list of dicts."""
    params = urllib.parse.urlencode({"db": INFLUX_DB, "q": query})
    url = f"http://{INFLUX_HOST}:{INFLUX_PORT}/query?{params}"
    creds = base64.b64encode(f"{INFLUX_USER}:{INFLUX_PASSWORD}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"InfluxDB query error: {e}", file=sys.stderr)
        return []
    results = data.get("results", [{}])[0]
    series = results.get("series", [])
    if not series:
        return []
    cols = series[0]["columns"]
    rows = []
    for vals in series[0].get("values", []):
        rows.append(dict(zip(cols, vals)))
    return rows


def today_str():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def now_local():
    return datetime.now(TZ)


# --- Rating helpers ---

def sleep_score_rating(s):
    if s is None:
        return "no data"
    if s >= SLEEP_EXCELLENT:
        return "excellent"
    if s >= SLEEP_GOOD:
        return "good"
    if s >= SLEEP_FAIR:
        return "fair"
    return "poor"


def readiness_rating(s):
    if s is None:
        return "no data"
    if s >= READINESS_PRIME:
        return "prime"
    if s >= READINESS_READY:
        return "ready"
    if s >= READINESS_FAIR:
        return "fair"
    return "low"


def battery_rating(b):
    if b is None:
        return "no data"
    if b >= BATTERY_HIGH:
        return "high"
    if b >= BATTERY_MODERATE:
        return "moderate"
    if b >= BATTERY_LOW:
        return "low"
    return "depleted"


def steps_rating(s):
    if s is None:
        return "no data"
    if s >= STEPS_VERY_ACTIVE:
        return "very active"
    if s >= STEPS_ACTIVE:
        return "active"
    if s >= STEPS_MODERATE:
        return "moderate"
    if s >= STEPS_LIGHT:
        return "light"
    return "sedentary"


def stress_level_label(v):
    if v is None or v < 0:
        return "rest"
    if v <= STRESS_LOW:
        return "low"
    if v <= STRESS_MODERATE:
        return "moderate"
    if v <= STRESS_HIGH:
        return "high"
    return "very high"


def fmt_secs(secs):
    """Seconds to 'Xh Ym' or 'Xmin'."""
    if secs is None:
        return "—"
    secs = int(secs)
    h, m = divmod(secs // 60, 60)
    if h > 0:
        return f"{h}h {m:02d}min"
    return f"{m}min"


def fmt_pct(val):
    if val is None:
        return "—"
    return f"{val:.0f}%"


def safe(val, fmt="{}", default="—"):
    if val is None:
        return default
    return fmt.format(val)


def safe_int(val):
    if val is None:
        return None
    return int(val)


def safe_float(val):
    if val is None:
        return None
    return float(val)


# --- Stress (silent unless flagged) ---

def cmd_stress():
    now = now_local()
    date = today_str()
    next_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    hour_label = now.strftime("%H:%M")

    # Last 2h of intraday stress
    two_h_ago = (now - timedelta(hours=2)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_utc = now.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    readings = influx_query(
        f"SELECT stressLevel FROM StressIntraday "
        f"WHERE time >= '{two_h_ago}' AND time <= '{now_utc}' ORDER BY time ASC"
    )

    # Body battery last 2h
    battery = influx_query(
        f"SELECT bodyBatteryLevel FROM BodyBatteryIntraday "
        f"WHERE time >= '{two_h_ago}' AND time <= '{now_utc}' ORDER BY time ASC"
    )

    # Daily cumulative
    daily = influx_query(
        f"SELECT highStressPercentage, mediumStressPercentage, lowStressPercentage, "
        f"restStressPercentage FROM DailyStats "
        f"WHERE time >= '{date}T00:00:00Z' AND time < '{next_date}T00:00:00Z' LIMIT 1"
    )

    if not readings:
        return  # no data, stay silent

    # Analyze readings (filter out rest/sleep = -1)
    valid = [r for r in readings if r.get("stressLevel") is not None and r["stressLevel"] >= 0]
    if not valid:
        return

    # Count zones
    high_count = sum(1 for r in valid if r["stressLevel"] >= STRESS_INTRADAY_HIGH)
    total_count = len(valid)
    high_pct = (high_count / total_count * 100) if total_count else 0

    # Detect sustained high stress (consecutive readings >= threshold)
    max_consecutive = 0
    current_streak = 0
    streak_start_time = None
    longest_streak_start = None
    for r in valid:
        if r["stressLevel"] >= STRESS_INTRADAY_HIGH:
            if current_streak == 0:
                streak_start_time = r.get("time", "")
            current_streak += 1
            if current_streak > max_consecutive:
                max_consecutive = current_streak
                longest_streak_start = streak_start_time
        else:
            current_streak = 0
    sustained_minutes = max_consecutive * 3  # readings every 3 min

    # Body battery drain
    bb_drain = None
    bb_start = None
    bb_end = None
    if battery:
        bb_vals = [b.get("bodyBatteryLevel") for b in battery if b.get("bodyBatteryLevel") is not None]
        if len(bb_vals) >= 2:
            bb_start = bb_vals[0]
            bb_end = bb_vals[-1]
            bb_drain = bb_start - bb_end

    # Daily accumulation
    daily_high = None
    daily_med = None
    if daily:
        daily_high = safe_float(daily[0].get("highStressPercentage"))
        daily_med = safe_float(daily[0].get("mediumStressPercentage"))

    # Decision: should we alert?
    alerts = []

    if max_consecutive >= STRESS_SUSTAINED_COUNT:
        streak_time = ""
        if longest_streak_start:
            try:
                t = datetime.fromisoformat(longest_streak_start.replace("Z", "+00:00"))
                streak_time = f" around {t.astimezone(TZ).strftime('%H:%M')}"
            except Exception:
                pass
        alerts.append(f"Sustained high stress: {sustained_minutes}min continuous block{streak_time}")

    if bb_drain is not None and bb_drain >= BATTERY_DRAIN_ALERT:
        alerts.append(f"Body battery: dropped from {bb_start:.0f} to {bb_end:.0f} (-{bb_drain:.0f} in 2h)")

    if daily_high is not None and daily_high >= STRESS_DAILY_HIGH_PCT:
        alerts.append(f"Today so far: {daily_high:.0f}% high stress (building up)")

    if high_pct >= STRESS_2H_HIGH_PCT:
        alerts.insert(0, f"Last 2h: {high_pct:.0f}% medium/high stress ({high_count} of {total_count} readings above 50)")

    if not alerts:
        return  # all good, stay silent

    # Build output
    lines = [f"Stress alert ({hour_label})", ""]
    lines.extend(alerts)

    if daily_high is not None and daily_med is not None and f"Today so far" not in "\n".join(alerts):
        lines.append(f"\nToday so far: {daily_high:.0f}% high stress, {daily_med:.0f}% medium")

    lines.append("")
    lines.append("Take a break. Step outside, breathe, or do something low-stimulus for 15 minutes.")

    print("\n".join(lines))


# --- Activity (silent unless new) ---

def cmd_activity():
    now = now_local()
    now_utc = now.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load last check time
    last_check = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
                last_check = state.get("last_activity_check")
        except Exception:
            pass

    # Default: look back 2h if no state
    if not last_check:
        last_check = (now - timedelta(hours=2)).astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    activities = influx_query(
        f"SELECT activityName, activityType, distance, movingDuration, averageHR, "
        f"maxHR, calories, averageSpeed, trainingEffectLabel "
        f"FROM ActivitySummary WHERE time > '{last_check}' ORDER BY time ASC"
    )

    # Save new timestamp
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"last_activity_check": now_utc}, f)
    except Exception:
        pass

    # Filter out Garmin "END" / "No Activity" artifacts
    activities = [a for a in activities if a.get("activityType") not in (None, "No Activity") and a.get("activityName") != "END"]
    if not activities:
        return  # silent

    for a in activities:
        name = a.get("activityName") or a.get("activityType") or "Activity"
        dur = safe_float(a.get("movingDuration"))
        hr = safe_int(a.get("averageHR"))
        max_hr = safe_int(a.get("maxHR"))
        dist = safe_float(a.get("distance"))
        cals = safe_int(a.get("calories"))
        speed = safe_float(a.get("averageSpeed"))
        te_label = a.get("trainingEffectLabel")

        lines = [f"Activity logged: {name}", ""]

        parts = []
        if dur:
            parts.append(fmt_secs(dur))
        if dist and dist > 100:
            km = dist / 1000
            parts.append(f"{km:.2f}km")
            # Pace for running-like activities
            if speed and speed > 0 and dur:
                pace_sec = 1000 / speed  # sec per km
                pace_min = int(pace_sec // 60)
                pace_s = int(pace_sec % 60)
                parts.append(f"pace {pace_min}:{pace_s:02d}/km")
        if parts:
            lines.append("  " + " | ".join(parts))

        hr_parts = []
        if hr:
            hr_parts.append(f"avg HR {hr}")
        if max_hr:
            hr_parts.append(f"max {max_hr}")
        if hr_parts:
            lines.append("  " + " | ".join(hr_parts))

        if cals:
            lines.append(f"  Calories: {cals}")
        if te_label:
            lines.append(f"  Training effect: {te_label}")

        lines.append("")
        lines.append(_activity_verdict(a))
        print("\n".join(lines))


def _activity_verdict(a):
    name = (a.get("activityName") or a.get("activityType") or "").lower()
    dist = safe_float(a.get("distance"))
    dur = safe_float(a.get("movingDuration"))

    if "run" in name:
        if dist and dist > 5000:
            return "Nice run! Solid distance. Stretch and hydrate."
        return "Good effort on the run. Keep it up."
    if "pilates" in name or "yoga" in name:
        return "Great mobility work. Your body thanks you."
    if "strength" in name or "weight" in name or "gym" in name:
        return "Strength work done. Fuel up with protein."
    if "walk" in name or "hik" in name:
        return "Good to move. Every step counts."
    if "cycl" in name or "bik" in name:
        return "Ride logged. Nice work on the bike."

    if dur and dur > 3600:
        return "Solid session. That's dedication."
    return "Activity done. Keep moving!"


# --- Main ---

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "stress":
        cmd_stress()
    elif cmd == "activity":
        cmd_activity()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
