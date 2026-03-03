#!/usr/bin/env python3
"""Calendar + weather event monitor — reminders with weather cross-reference.

Usage:
    calendar_monitor.py check   — Silent unless reminder or new event found
"""
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calendar_api import CalendarManager
from weather_monitor import fetch_forecast, find_forecast_for_time, is_concerning

TZ = ZoneInfo("America/Sao_Paulo")

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".calendar_monitor_state.json",
)


def load_state():
    """Load state from file. Returns empty state if missing or corrupt."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        # Reset reminded_event_ids daily
        last_check = state.get("last_check", "")
        if last_check:
            try:
                last_date = datetime.fromisoformat(last_check).date()
                if last_date < datetime.now(TZ).date():
                    state["reminded_event_ids"] = []
            except Exception:
                pass
        return state
    except Exception:
        return {}


def save_state(state):
    """Save state to file."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save state: {e}", file=sys.stderr)


def cmd_check():
    now = datetime.now(TZ)
    state = load_state()
    is_first_run = not state.get("known_event_ids")

    known_ids = set(state.get("known_event_ids", []))
    reminded_ids = set(state.get("reminded_event_ids", []))

    # Fetch events for today and tomorrow
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=2)

    mgr = CalendarManager()
    events = mgr.get_all_events(day_start, day_end)

    current_ids = {ev.id for ev in events}
    output_lines = []

    # --- Check 1: Upcoming meeting reminders (5-15 min window) ---
    reminder_start = now + timedelta(minutes=5)
    reminder_end = now + timedelta(minutes=15)

    reminder_events = []
    for ev in events:
        if ev.all_day:
            continue
        if ev.id in reminded_ids:
            continue
        if reminder_start <= ev.start <= reminder_end:
            reminder_events.append(ev)

    # Lazy-fetch forecast only when reminders exist
    raw_forecast = None
    if reminder_events:
        try:
            raw_forecast = fetch_forecast()
        except Exception:
            raw_forecast = None

    for ev in reminder_events:
        minutes_until = int((ev.start - now).total_seconds() / 60)
        cal_tag = "[personal]" if ev.calendar == "personal" else "[work]"
        line = f"Reminder: {cal_tag} {ev.title} starts in {minutes_until} min ({ev.start.strftime('%H:%M')})"
        if ev.location:
            line += f" — {ev.location}"
        # Weather cross-reference
        if raw_forecast:
            forecast = find_forecast_for_time(raw_forecast, ev.start)
            concerning, reasons = is_concerning(forecast)
            if concerning:
                line += f" | Weather: {', '.join(reasons)}"
        output_lines.append(line)
        reminded_ids.add(ev.id)

    # --- Check 2: New event detection ---
    new_events = []
    if is_first_run:
        # Bootstrap: store all current IDs without alerting
        pass
    else:
        new_ids = current_ids - known_ids
        if new_ids:
            for ev in events:
                if ev.id in new_ids:
                    new_events.append(ev)

    if new_events:
        if output_lines:
            output_lines.append("")
        output_lines.append("New events detected:")
        for ev in new_events:
            output_lines.append(f"  {ev.format_short()}")
            if ev.location:
                output_lines.append(f"    Location: {ev.location}")

    # Update state
    state["known_event_ids"] = list(current_ids)
    state["reminded_event_ids"] = list(reminded_ids)
    state["last_check"] = now.isoformat()
    save_state(state)

    if output_lines:
        print("\n".join(output_lines))


# --- Main ---

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "check":
        cmd_check()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
