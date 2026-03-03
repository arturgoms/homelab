#!/usr/bin/env python3
"""Unified daily reports combining health, weather, and calendar data.

Usage:
    report.py morning   — Look-ahead: sleep, recovery, weather, schedule, AI insight
    report.py evening   — Look-behind: steps, stress, activities, AI insight
"""
import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from health_check import (
    influx_query, today_str, now_local,
    sleep_score_rating, readiness_rating, battery_rating, steps_rating,
    stress_level_label, fmt_secs, fmt_pct, safe, safe_int, safe_float,
    TZ, WEEKDAYS,
)
from weather_monitor import (
    fetch_forecast, get_today_forecasts, find_forecast_for_time, is_concerning,
)
from calendar_api import CalendarManager
from thresholds import (
    SLEEP_GOOD, SLEEP_FAIR,
    READINESS_READY, READINESS_FAIR,
    BATTERY_HIGH, BATTERY_WAKE_LOW, BATTERY_DEPLETED,
    HRV_HIGH, HRV_NORMAL,
    RHR_EXCELLENT, RHR_GOOD,
    SPO2_LOW,
    SLEEP_STRESS_CALM, SLEEP_STRESS_SOME,
    STEPS_GOOD_DAY, STEPS_LOW_DAY,
    STRESS_WELL_MANAGED_PCT, STRESS_HIGH_DAY_PCT,
    WEATHER_CONCERNING, WEATHER_POP_THRESHOLD, WEATHER_POP_MENTION,
)


# --- Morning report ---

def cmd_morning():
    now = now_local()
    date = today_str()
    next_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    weekday = WEEKDAYS[now.weekday()]
    date_label = now.strftime("%b %d")

    # --- Health data ---
    sleep = influx_query(
        "SELECT sleepScore, sleepTimeSeconds, deepSleepSeconds, remSleepSeconds, "
        "lightSleepSeconds, awakeSleepSeconds, restingHeartRate, avgOvernightHrv, "
        "awakeCount, averageSpO2Value, avgSleepStress, bodyBatteryChange "
        "FROM SleepSummary ORDER BY time DESC LIMIT 1"
    )
    readiness = influx_query(
        "SELECT score, level, recoveryTime, hrvFactorPercent "
        "FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
    )
    daily = influx_query(
        f"SELECT bodyBatteryAtWakeTime FROM DailyStats "
        f"WHERE time >= '{date}T00:00:00Z' AND time < '{next_date}T00:00:00Z' LIMIT 1"
    )

    # --- Weather data ---
    raw_entries = []
    try:
        raw_entries = fetch_forecast()
    except Exception as e:
        print(f"Weather fetch error: {e}", file=sys.stderr)
    today_forecasts = get_today_forecasts(raw_entries) if raw_entries else []

    # --- Calendar data ---
    mgr = CalendarManager()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = mgr.get_all_events(day_start, day_end)

    # --- Build report ---
    lines = [f"Morning report ({weekday}, {date_label})", ""]

    # Sleep section
    if sleep:
        s = sleep[0]
        score = safe_int(s.get("sleepScore"))
        total_secs = safe_int(s.get("sleepTimeSeconds"))
        deep_secs = safe_int(s.get("deepSleepSeconds"))
        rem_secs = safe_int(s.get("remSleepSeconds"))
        awake_count = safe_int(s.get("awakeCount"))
        hrv = safe_float(s.get("avgOvernightHrv"))
        rhr = safe_int(s.get("restingHeartRate"))
        spo2 = safe_float(s.get("averageSpO2Value"))
        sleep_stress = safe_float(s.get("avgSleepStress"))

        total_h = total_secs / 3600 if total_secs else None
        deep_pct = (deep_secs / total_secs * 100) if (deep_secs and total_secs) else None
        rem_pct = (rem_secs / total_secs * 100) if (rem_secs and total_secs) else None

        lines.append(f"Sleep: {safe(score)}/100 ({sleep_score_rating(score)}) - {safe(total_h, '{:.1f}h')}")
        lines.append(f"  Deep {fmt_pct(deep_pct)} | REM {fmt_pct(rem_pct)} | Awake {safe(awake_count, '{}x')}")

        hrv_note = ""
        if hrv is not None:
            if hrv >= HRV_HIGH:
                hrv_note = "high"
            elif hrv >= HRV_NORMAL:
                hrv_note = "normal"
            else:
                hrv_note = "low"
        rhr_note = ""
        if rhr is not None:
            if rhr <= RHR_EXCELLENT:
                rhr_note = "excellent"
            elif rhr <= RHR_GOOD:
                rhr_note = "good"
            else:
                rhr_note = "elevated"

        lines.append(f"  HRV {safe(hrv, '{:.0f}ms')} ({hrv_note}) | RHR {safe(rhr, '{}bpm')} ({rhr_note})")

        if sleep_stress is not None:
            ss_label = ("very restful" if sleep_stress <= 15
                        else "calm" if sleep_stress <= SLEEP_STRESS_CALM
                        else "some stress" if sleep_stress <= SLEEP_STRESS_SOME
                        else "high stress")
            lines.append(f"  Sleep stress: {sleep_stress:.0f} ({ss_label})")
        if spo2 is not None and spo2 < SPO2_LOW:
            lines.append(f"  SpO2: {spo2:.1f}% (below normal, monitor)")
    else:
        lines.append("Sleep: no data")

    lines.append("")

    # Training readiness
    if readiness:
        r = readiness[0]
        tr_score = safe_int(r.get("score"))
        recovery = safe_int(r.get("recoveryTime"))
        hrv_factor = safe_float(r.get("hrvFactorPercent"))
        lines.append(f"Training readiness: {safe(tr_score)}/100 ({readiness_rating(tr_score)})")
        if recovery:
            rec_h = recovery / 60
            lines.append(f"  Recovery time: {rec_h:.0f}h")
        if hrv_factor is not None:
            lines.append(f"  HRV factor: {hrv_factor:.0f}%")
    else:
        lines.append("Training readiness: no data")

    # Body battery at wake
    bb_wake = None
    if daily:
        bb_wake = safe_int(daily[0].get("bodyBatteryAtWakeTime"))
        lines.append(f"Body battery at wake: {safe(bb_wake)} ({battery_rating(bb_wake)})")
    lines.append("")

    # Weather section
    if today_forecasts:
        temps = [f["temp"] for f in today_forecasts if f["temp"] is not None]
        temp_min = min(temps) if temps else None
        temp_max = max(temps) if temps else None
        conditions = list(dict.fromkeys(f["weather_desc"] for f in today_forecasts))
        max_pop = max(f["pop"] for f in today_forecasts)

        lines.append("Weather:")
        if temp_min is not None and temp_max is not None:
            lines.append(f"  Temperature: {temp_min:.0f}°C – {temp_max:.0f}°C")
        lines.append(f"  Conditions: {', '.join(conditions)}")
        if max_pop >= WEATHER_POP_MENTION:
            lines.append(f"  Rain chance: up to {max_pop*100:.0f}%")

        lines.append("  Hourly:")
        for f in today_forecasts:
            hour = f["dt"].strftime("%H:%M")
            pop_str = f" | {f['pop']*100:.0f}% rain" if f["pop"] >= 0.2 else ""
            lines.append(f"    {hour}: {f['temp']:.0f}°C, {f['weather_desc']}{pop_str}")
    else:
        lines.append("Weather: unavailable")

    lines.append("")

    # Schedule section
    if events:
        lines.append("Today's schedule:")
        for ev in events:
            lines.append(f"  {ev.format_short()}")
    else:
        lines.append("No events today.")

    # Weather-event cross-reference
    weather_alerts = []
    if today_forecasts and events:
        for ev in events:
            if ev.all_day:
                continue
            forecast = find_forecast_for_time(raw_entries, ev.start)
            concerning, reasons = is_concerning(forecast)
            if concerning:
                time_str = ev.start.strftime("%H:%M")
                weather_alerts.append(f"  {time_str} {ev.title}: {', '.join(reasons)}")

    if weather_alerts:
        lines.append("")
        lines.append("Weather alerts for events:")
        lines.extend(weather_alerts)

    # AI insight
    lines.append("")
    lines.append(_morning_insight(sleep, readiness, bb_wake, today_forecasts, events))

    print("\n".join(lines))


def _morning_insight(sleep, readiness, bb_wake, forecasts, events):
    """Compose a forward-looking AI insight from threshold-based signals."""
    signals = []

    # Sleep signal
    if sleep:
        score = safe_int(sleep[0].get("sleepScore"))
        if score is not None:
            if score >= SLEEP_GOOD:
                signals.append("Solid sleep")
            elif score >= SLEEP_FAIR:
                signals.append("Decent rest")
            else:
                signals.append("Rough night")

    # Body battery signal
    if bb_wake is not None:
        if bb_wake >= BATTERY_HIGH:
            signals.append("battery charged")
        elif bb_wake < BATTERY_WAKE_LOW:
            signals.append("low battery")

    # Training readiness signal
    if readiness:
        tr = safe_int(readiness[0].get("score"))
        if tr is not None:
            if tr >= READINESS_READY:
                signals.append("ready to train")
            elif tr >= READINESS_FAIR:
                signals.append("moderate readiness")
            else:
                signals.append("low readiness")

    # Weather signal
    if forecasts:
        any_concerning = any(
            f["weather_main"] in WEATHER_CONCERNING or f["pop"] >= WEATHER_POP_THRESHOLD
            for f in forecasts
        )
        if any_concerning:
            signals.append("rain expected")
        else:
            signals.append("clear skies")

    # Calendar signal
    timed_events = [ev for ev in events if not ev.all_day] if events else []
    if not timed_events:
        signals.append("meeting-free day")
    elif len(timed_events) == 1:
        ev = timed_events[0]
        signals.append(f"first up: {ev.title} at {ev.start.strftime('%H:%M')}")
    else:
        # Find the first upcoming event
        now = now_local()
        upcoming = [ev for ev in timed_events if ev.start >= now]
        if upcoming:
            ev = upcoming[0]
            signals.append(f"first up: {ev.title} at {ev.start.strftime('%H:%M')}")
        else:
            signals.append(f"{len(timed_events)} events today")

    # Compose
    if not signals:
        return "Insight: Have a good day."

    # Capitalize first signal, join with " and " or " — "
    head = signals[0]
    if len(signals) == 1:
        return f"Insight: {head.capitalize()}."

    # Split into primary (first 2-3) and tail
    primary = signals[:2]
    tail = signals[2:]

    result = f"{primary[0].capitalize()} and {primary[1]}"
    if tail:
        result += f" — {', '.join(tail)}"
    return f"Insight: {result}."


# --- Evening report ---

def cmd_evening():
    now = now_local()
    date = today_str()
    next_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    weekday = WEEKDAYS[now.weekday()]
    date_label = now.strftime("%b %d")

    # Daily stats
    daily = influx_query(
        f"SELECT totalSteps, totalDistanceMeters, moderateIntensityMinutes, "
        f"vigorousIntensityMinutes, bodyBatteryHighestValue, bodyBatteryLowestValue, "
        f"bodyBatteryDrainedValue, activeKilocalories, "
        f"highStressDuration, highStressPercentage, mediumStressDuration, mediumStressPercentage, "
        f"lowStressDuration, lowStressPercentage, restStressDuration, restStressPercentage, "
        f"activityStressDuration, activityStressPercentage, stressPercentage, stressDuration "
        f"FROM DailyStats WHERE time >= '{date}T00:00:00Z' AND time < '{next_date}T00:00:00Z' LIMIT 1"
    )

    # Activities today
    activities = influx_query(
        f"SELECT activityName, activityType, distance, movingDuration, averageHR, calories "
        f"FROM ActivitySummary WHERE time >= '{date}T00:00:00Z' AND time < '{next_date}T00:00:00Z'"
    )

    # Calendar (for meeting count in insight)
    mgr = CalendarManager()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = mgr.get_all_events(day_start, day_end)

    lines = [f"Evening report ({weekday}, {date_label})", ""]

    if daily:
        d = daily[0]
        steps = safe_int(d.get("totalSteps"))
        dist = safe_float(d.get("totalDistanceMeters"))
        mod_min = safe_int(d.get("moderateIntensityMinutes"))
        vig_min = safe_int(d.get("vigorousIntensityMinutes"))
        bb_high = safe_int(d.get("bodyBatteryHighestValue"))
        bb_low = safe_int(d.get("bodyBatteryLowestValue"))
        bb_drain = safe_int(d.get("bodyBatteryDrainedValue"))
        cals = safe_int(d.get("activeKilocalories"))

        dist_km = dist / 1000 if dist else None
        active_min = ((mod_min or 0) + (vig_min or 0)) or None

        lines.append(f"Steps: {safe(steps, '{:,}')} ({steps_rating(steps)}) - {safe(dist_km, '{:.1f}km')}")

        if active_min:
            parts = []
            if mod_min:
                parts.append(f"{mod_min} moderate")
            if vig_min:
                parts.append(f"{vig_min} vigorous")
            lines.append(f"Active minutes: {active_min} ({' + '.join(parts)})")

        lines.append(f"Body battery: {safe(bb_high)} high / {safe(bb_low)} low (drained {safe(bb_drain)})")
        lines.append(f"Calories burned: {safe(cals, '{:,}')}")
        lines.append("")

        # Stress breakdown
        rest_pct = safe_float(d.get("restStressPercentage"))
        low_pct = safe_float(d.get("lowStressPercentage"))
        med_pct = safe_float(d.get("mediumStressPercentage"))
        high_pct = safe_float(d.get("highStressPercentage"))
        act_pct = safe_float(d.get("activityStressPercentage"))
        total_pct = safe_float(d.get("stressPercentage"))

        lines.append("Stress breakdown:")
        lines.append(f"  Rest/recovery: {fmt_pct(rest_pct)} | Low: {fmt_pct(low_pct)} | Medium: {fmt_pct(med_pct)} | High: {fmt_pct(high_pct)}")
        lines.append(f"  Activity stress: {fmt_pct(act_pct)} | Total stress time: {fmt_pct(total_pct)}")
    else:
        lines.append("No daily stats available.")

    # Activities
    activities = [a for a in activities if a.get("activityType") not in (None, "No Activity") and a.get("activityName") != "END"]
    if activities:
        lines.append("")
        lines.append("Activities:")
        for a in activities:
            name = a.get("activityName") or a.get("activityType") or "Activity"
            dur = safe_float(a.get("movingDuration"))
            hr = safe_int(a.get("averageHR"))
            dist_a = safe_float(a.get("distance"))

            parts = []
            if dur:
                parts.append(fmt_secs(dur))
            if hr:
                parts.append(f"avg HR {hr}")
            if dist_a and dist_a > 100:
                parts.append(f"{dist_a / 1000:.1f}km")
            lines.append(f"  {name}: {', '.join(parts)}")

    # AI insight
    lines.append("")
    lines.append(_evening_insight(daily, activities, events))

    print("\n".join(lines))


def _evening_insight(daily, activities, events):
    """Compose a reflective AI insight summarizing the day."""
    signals = []

    # Steps signal
    if daily:
        d = daily[0]
        steps = safe_int(d.get("totalSteps"))
        high_pct = safe_float(d.get("highStressPercentage"))

        if steps is not None:
            if steps >= STEPS_GOOD_DAY:
                signals.append(f"Active day with {steps // 1000}k steps")
            elif steps < STEPS_LOW_DAY:
                signals.append("Quiet movement day")

        # Stress signal
        if high_pct is not None:
            if high_pct <= STRESS_WELL_MANAGED_PCT:
                signals.append("stress stayed low")
            elif high_pct >= STRESS_HIGH_DAY_PCT:
                signals.append("high stress built up")
            elif high_pct >= 10:
                signals.append("moderate stress")

    # Activity signal
    if activities:
        if len(activities) == 1:
            name = activities[0].get("activityName") or activities[0].get("activityType") or "workout"
            signals.append(f"solid {name}")
        else:
            signals.append(f"{len(activities)} workouts logged")

    # Meeting count signal
    timed_events = [ev for ev in events if not ev.all_day] if events else []
    if len(timed_events) >= 3:
        signals.append(f"despite {len(timed_events)} meetings")
    elif not timed_events:
        signals.append("meeting-free day")

    if not signals:
        return "Insight: Day's done. Time to wind down."

    # Compose sentence
    main_parts = signals[:3]
    result = ". ".join(s.capitalize() if i == 0 or s[0].islower() else s for i, s in enumerate(main_parts))
    result += ". Time to wind down."
    return f"Insight: {result}"


# --- Main ---

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "morning":
        cmd_morning()
    elif cmd == "evening":
        cmd_evening()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
