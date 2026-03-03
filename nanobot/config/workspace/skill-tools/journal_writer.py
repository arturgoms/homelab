#!/usr/bin/env python3
"""Journal writer for daily notes in Obsidian format.

Subcommands:
  append         "- [HH:MM] entry"           Append single entry to today's journal
  append-multi   "- [HH:MM] a\n- [HH:MM] b" Append multiple entries
  append-insight "text"                      Write/replace AI Insight section
  populate       [morning|evening]          Fill weather/health/calendar sections
  read-journal   [YYYY-MM-DD]               Read journal + AI Insight sections
  read-session   [start] [end]              Extract session messages by date range
"""

import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TIME_DIR = "/time/2.2 Daily"
_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
SESSION_FILE = f"/root/.nanobot/workspace/sessions/telegram_{_chat_id}.jsonl"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SP_TZ = timezone(timedelta(hours=-3))


def now_sp():
    """Current datetime in America/Sao_Paulo."""
    return datetime.now(SP_TZ)


def today_str():
    return now_sp().strftime("%Y-%m-%d")


def yesterday_str(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def tomorrow_str(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def weekday_name(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return WEEKDAYS[d.weekday()]


def note_path(date_str):
    return os.path.join(TIME_DIR, f"{date_str}.md")


def create_note(date_str):
    """Create a new daily note from template."""
    yd = yesterday_str(date_str)
    td = tomorrow_str(date_str)
    day = weekday_name(date_str)

    content = f"""---
date: '{date_str}'
day: {day}
habits: []
sleep_duration: 0.00
sleep_score: 0
nap_duration: 0.00
tags:
  - time/daily
  - area/friday
temperature: 0.00
---

<< [[{yd}|Yesterday]] | [[{td}|Tomorrow]] >>

# [[{date_str}]]

## Weather


## Health


## Calendar


## Habits


## Journal

### Notes

-

### Reminder

- [ ]


## AI Insight

"""
    path = note_path(date_str)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


def read_note(date_str):
    """Read a daily note, creating it if missing."""
    path = note_path(date_str)
    if not os.path.exists(path):
        create_note(date_str)
    with open(path, "r") as f:
        return f.read()


def append_entries(entries):
    """Append journal entries to today's note.

    entries: list of strings like "- [14:30] Something happened"
    """
    date_str = today_str()
    content = read_note(date_str)

    # Find ### Notes section and ### Reminder
    notes_match = re.search(r"(### Notes\n)", content)
    reminder_match = re.search(r"(### Reminder)", content)

    if not notes_match:
        print(f"ERROR: Could not find '### Notes' in {date_str}.md", file=sys.stderr)
        sys.exit(1)

    notes_start = notes_match.end()
    if reminder_match:
        insert_point = reminder_match.start()
    else:
        insert_point = len(content)

    # Get existing notes section
    existing = content[notes_start:insert_point].strip()

    # Check for empty placeholder (just "- " or "-")
    is_empty = existing in ("- ", "-", "")

    # Build new entries block
    entries_block = "\n".join(entries)

    if is_empty:
        new_section = entries_block + "\n\n"
    else:
        new_section = existing + "\n" + entries_block + "\n\n"

    new_content = content[:notes_start] + new_section + content[insert_point:]

    path = note_path(date_str)
    with open(path, "w") as f:
        f.write(new_content)

    print(f"Logged to {date_str}")


def cmd_append(entry):
    append_entries([entry])


def cmd_append_multi(raw):
    entries = [e for e in raw.split("\\n") if e.strip()]
    if not entries:
        print("No entries to append.", file=sys.stderr)
        sys.exit(1)
    append_entries(entries)


def cmd_append_insight(text):
    """Write or replace the AI Insight section in today's note."""
    date_str = today_str()
    content = read_note(date_str)

    # Format as blockquote
    lines = text.strip().split("\n")
    blockquote = "\n".join(f"> {line}" for line in lines)

    insight_match = re.search(r"(## AI Insight\n)", content)
    if not insight_match:
        # Append section at end
        content = content.rstrip() + "\n\n## AI Insight\n\n" + blockquote + "\n"
    else:
        # Replace everything after "## AI Insight\n" until next "## " or end
        after = content[insight_match.end():]
        next_section = re.search(r"\n## ", after)
        if next_section:
            rest = after[next_section.start():]
        else:
            rest = ""
        content = content[:insight_match.end()] + "\n" + blockquote + "\n" + rest

    path = note_path(date_str)
    with open(path, "w") as f:
        f.write(content)

    print(f"AI Insight written to {date_str}")


# --- InfluxDB + Weather helpers for populate ---

INFLUX_HOST = os.environ.get("INFLUXDB_HOST", "localhost")
INFLUX_PORT = os.environ.get("INFLUXDB_PORT", "8088")
INFLUX_DB = os.environ.get("INFLUXDB_DB", "GarminStats")
INFLUX_USER = os.environ.get("INFLUXDB_USER", "")
INFLUX_PASSWORD = os.environ.get("INFLUXDB_PASSWORD", "")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
WEATHER_CITY = os.environ.get("WEATHER_CITY", "Curitiba")
CALENDAR_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar_api.py")


def influx_query(query):
    params = urllib.parse.urlencode({"db": INFLUX_DB, "q": query})
    url = f"http://{INFLUX_HOST}:{INFLUX_PORT}/query?{params}"
    creds = base64.b64encode(f"{INFLUX_USER}:{INFLUX_PASSWORD}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"InfluxDB error: {e}", file=sys.stderr)
        return []
    results = data.get("results", [{}])[0]
    series = results.get("series", [])
    if not series:
        return []
    cols = series[0]["columns"]
    return [dict(zip(cols, vals)) for vals in series[0].get("values", [])]


def safe_int(val):
    return int(val) if val is not None else None


def safe_float(val):
    return float(val) if val is not None else None


def fetch_weather():
    """Fetch current weather from OpenWeatherMap."""
    if not WEATHER_API_KEY:
        return None, None
    try:
        url = (f"https://api.openweathermap.org/data/2.5/weather?"
               f"q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units=metric")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return desc, temp
    except Exception as e:
        print(f"Weather error: {e}", file=sys.stderr)
        return None, None


def fetch_health_morning(date_str, next_date):
    """Fetch sleep + training readiness for morning population."""
    lines = []

    # Sleep
    sleep = influx_query(
        "SELECT sleepScore, sleepTimeSeconds, bodyBatteryChange "
        "FROM SleepSummary ORDER BY time DESC LIMIT 1"
    )
    sleep_duration_h = 0.0
    sleep_score_val = 0
    bb_recharge = 0
    if sleep:
        s = sleep[0]
        sleep_score_val = safe_int(s.get("sleepScore")) or 0
        total_secs = safe_int(s.get("sleepTimeSeconds")) or 0
        sleep_duration_h = total_secs / 3600
        bb_recharge = safe_int(s.get("bodyBatteryChange")) or 0
        h = int(sleep_duration_h)
        m = int((sleep_duration_h - h) * 60)
        lines.append(f"- **Sleep:** {h}:{m:02d} (score: {sleep_score_val}, +{bb_recharge}% battery)")

    # Naps
    naps = influx_query(
        f"SELECT sleepTimeSeconds, bodyBatteryChange, startTime, endTime "
        f"FROM NapSummary WHERE time >= '{date_str}T00:00:00Z' AND time < '{next_date}T00:00:00Z'"
    )
    nap_duration_h = 0.0
    if naps:
        for nap in naps:
            nsecs = safe_int(nap.get("sleepTimeSeconds")) or 0
            nap_duration_h += nsecs / 3600
            nh = int(nsecs / 3600)
            nm = int((nsecs % 3600) / 60)
            nap_bb = safe_int(nap.get("bodyBatteryChange")) or 0
            nap_display = f"{nh}h {nm:02d}m" if nh > 0 else f"{nm}m"
            # Try to get start/end times
            start_t = nap.get("startTime", "")
            end_t = nap.get("endTime", "")
            time_range = ""
            if start_t and end_t:
                try:
                    st = datetime.fromisoformat(str(start_t).replace("Z", "+00:00")).astimezone(SP_TZ)
                    et = datetime.fromisoformat(str(end_t).replace("Z", "+00:00")).astimezone(SP_TZ)
                    time_range = f" ({st.strftime('%H:%M')}-{et.strftime('%H:%M')},"
                except Exception:
                    time_range = " ("
            else:
                time_range = " ("
            lines.append(f"- **Nap:** {nap_display}{time_range} recharged {nap_bb}%)")

    # Training readiness
    readiness = influx_query(
        "SELECT score, level FROM TrainingReadiness ORDER BY time DESC LIMIT 1"
    )
    tr_score = 0
    tr_level = ""
    if readiness:
        tr_score = safe_int(readiness[0].get("score")) or 0
        tr_level = readiness[0].get("level", "")

    # HRV
    hrv_data = influx_query(
        "SELECT avgOvernightHrv FROM SleepSummary ORDER BY time DESC LIMIT 1"
    )
    hrv = 0
    if hrv_data:
        hrv = safe_int(hrv_data[0].get("avgOvernightHrv")) or 0

    return lines, {
        "sleep_duration": round(sleep_duration_h, 2),
        "sleep_score": sleep_score_val,
        "nap_duration": round(nap_duration_h, 2),
        "tr_score": tr_score,
        "tr_level": tr_level.upper() if tr_level else "",
        "hrv": hrv,
        "bb_recharge": bb_recharge,
    }


def fetch_health_evening(date_str, next_date):
    """Fetch day stats for evening population."""
    lines = []

    daily = influx_query(
        f"SELECT totalSteps, bodyBatteryHighestValue, bodyBatteryLowestValue, "
        f"bodyBatteryDrainedValue, restStressDuration, stressDuration "
        f"FROM DailyStats WHERE time >= '{date_str}T00:00:00Z' AND time < '{next_date}T00:00:00Z' LIMIT 1"
    )

    steps = 0
    bb_high = 0
    bb_low = 0
    bb_drain = 0
    rest_h = 0.0
    stress_h = 0.0
    rest_pct = 0

    if daily:
        d = daily[0]
        steps = safe_int(d.get("totalSteps")) or 0
        bb_high = safe_int(d.get("bodyBatteryHighestValue")) or 0
        bb_low = safe_int(d.get("bodyBatteryLowestValue")) or 0
        bb_drain = safe_int(d.get("bodyBatteryDrainedValue")) or 0
        rest_secs = safe_int(d.get("restStressDuration")) or 0
        stress_secs = safe_int(d.get("stressDuration")) or 0
        rest_h = rest_secs / 3600
        stress_h = stress_secs / 3600
        total = rest_h + stress_h
        rest_pct = int(rest_h / total * 100) if total > 0 else 0

    # Activities
    activities = influx_query(
        f"SELECT activityName, activityType, movingDuration "
        f"FROM ActivitySummary WHERE time >= '{date_str}T00:00:00Z' AND time < '{next_date}T00:00:00Z'"
    )
    activities = [a for a in activities if a.get("activityType") not in (None, "No Activity") and a.get("activityName") != "END"]

    habits = []
    habit_lines = []
    for a in activities:
        name = a.get("activityName") or a.get("activityType") or "Activity"
        dur = safe_float(a.get("movingDuration"))
        dur_str = f"{int(dur / 60)}min" if dur else ""
        habits.append(name)
        habit_lines.append(f"- **{name}** (Garmin)\n  - _{name}: {dur_str}_")

    return {
        "steps": steps,
        "bb_high": bb_high,
        "bb_low": bb_low,
        "bb_drain": bb_drain,
        "rest_h": rest_h,
        "stress_h": stress_h,
        "rest_pct": rest_pct,
        "habits": habits,
        "habit_lines": habit_lines,
    }


def fetch_calendar():
    """Fetch today's calendar via calendar_api.py."""
    try:
        result = subprocess.run(
            ["python3", CALENDAR_SCRIPT, "today"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"Calendar error: {e}", file=sys.stderr)
    return ""


def update_section(content, section_name, new_body):
    """Replace the body of a ## section in the note. If missing, insert before ## Journal."""
    pattern = rf"(## {re.escape(section_name)}\n).*?(?=\n## |\Z)"
    new_content, count = re.subn(pattern, rf"\g<1>{new_body}\n", content, count=1, flags=re.DOTALL)
    if count:
        return new_content
    # Section doesn't exist — insert before ## Journal
    journal_match = re.search(r"\n## Journal\n", content)
    if journal_match:
        insert = f"\n## {section_name}\n{new_body}\n"
        return content[:journal_match.start()] + insert + content[journal_match.start():]
    return content


def _format_fm_value(key, val):
    if isinstance(val, list):
        return "[" + ", ".join(f"'{v}'" for v in val) + "]" if val else "[]"
    elif isinstance(val, float):
        return f"{val:.2f}"
    elif isinstance(val, int):
        return str(val)
    return str(val)


def update_frontmatter(content, updates):
    """Update frontmatter YAML values. Adds missing keys before tags."""
    fm_match = re.match(r"(---\n)(.*?)(---\n)", content, re.DOTALL)
    if not fm_match:
        return content
    fm = fm_match.group(2)
    for key, val in updates.items():
        formatted = _format_fm_value(key, val)
        new_fm, count = re.subn(rf"^{key}:.*$", f"{key}: {formatted}", fm, flags=re.MULTILINE)
        if count:
            fm = new_fm
        else:
            # Key doesn't exist — insert before tags: line
            tags_match = re.search(r"^tags:\s*$", fm, re.MULTILINE)
            if tags_match:
                fm = fm[:tags_match.start()] + f"{key}: {formatted}\n" + fm[tags_match.start():]
            else:
                fm += f"{key}: {formatted}\n"
    return fm_match.group(1) + fm + fm_match.group(3) + content[fm_match.end():]


def cmd_populate(mode="morning"):
    """Populate today's note with weather, health, and calendar data.

    mode=morning: create note + weather + sleep + calendar
    mode=evening: update health day stats + habits
    """
    date_str = today_str()
    next_date = tomorrow_str(date_str)
    content = read_note(date_str)

    if mode == "morning":
        # Weather
        desc, temp = fetch_weather()
        if desc and temp is not None:
            content = update_section(content, "Weather", f"{desc}, {temp:.2f}°C")
            content = update_frontmatter(content, {"temperature": round(temp, 2)})

        # Health (sleep/readiness)
        health_lines, health_meta = fetch_health_morning(date_str, next_date)
        if health_lines:
            # We'll build partial health — full stats come in evening
            health_body = "\n".join(health_lines)
            content = update_section(content, "Health", health_body)
            content = update_frontmatter(content, {
                "sleep_duration": health_meta["sleep_duration"],
                "sleep_score": health_meta["sleep_score"],
                "nap_duration": health_meta["nap_duration"],
            })

        # Calendar
        cal = fetch_calendar()
        if cal:
            cal_lines = []
            for line in cal.split("\n"):
                line = line.strip()
                if not line or line.startswith("=") or line.startswith("Schedule") or line.startswith("Today"):
                    continue
                # Strip [work]/[personal] prefix and (done) suffix
                line = re.sub(r"^\[(work|personal)\]\s*", "", line)
                line = re.sub(r"\s*\(done\)\s*$", "", line)
                # Convert "HH:MM-HH:MM: Event" to "HH:MM - Event"
                m = re.match(r"(\d{2}:\d{2})-\d{2}:\d{2}:\s*(.*)", line)
                if m:
                    line = f"{m.group(1)} - {m.group(2)}"
                elif re.match(r"All day:\s*(.*)", line):
                    am = re.match(r"All day:\s*(.*)", line)
                    line = f"00:06 - {am.group(1)}"
                if line:
                    cal_lines.append(line)
            if cal_lines:
                content = update_section(content, "Calendar", "\n".join(cal_lines))

    elif mode == "evening":
        # Full health stats
        health_morning_lines, health_meta = fetch_health_morning(date_str, next_date)
        evening_data = fetch_health_evening(date_str, next_date)

        health_lines = list(health_morning_lines)  # sleep, nap
        health_lines.append(f"- **Body Battery:** {evening_data['bb_high']}%→{evening_data['bb_low']}% (-{evening_data['bb_drain']}% today)")
        health_lines.append(f"- **Stress:** {evening_data['rest_h']:.1f}h rest / {evening_data['stress_h']:.1f}h stress ({evening_data['rest_pct']}% rest)")
        health_lines.append(f"- **Training Readiness:** {health_meta['tr_score']} ({health_meta['tr_level']})")
        health_lines.append(f"- **HRV:** {health_meta['hrv']}ms")
        health_lines.append(f"- **Steps:** {evening_data['steps']}")

        content = update_section(content, "Health", "\n".join(health_lines))

        # Habits
        if evening_data["habit_lines"]:
            content = update_section(content, "Habits", "\n".join(evening_data["habit_lines"]))
            content = update_frontmatter(content, {"habits": evening_data["habits"]})

    path = note_path(date_str)
    with open(path, "w") as f:
        f.write(content)
    print(f"Populated {date_str} ({mode})")


def cmd_read_journal(date_str=None):
    if date_str is None:
        date_str = today_str()

    path = note_path(date_str)
    if not os.path.exists(path):
        print(f"No daily note for {date_str}")
        return

    with open(path, "r") as f:
        content = f.read()

    # Extract ## Journal section
    match = re.search(r"(## Journal.*?)(?=\n## |\Z)", content, re.DOTALL)
    if match:
        print(match.group(1).strip())
    else:
        print(f"No Journal section found in {date_str}")

    # Also include ## AI Insight if present
    insight_match = re.search(r"(## AI Insight.*?)(?=\n## |\Z)", content, re.DOTALL)
    if insight_match:
        text = insight_match.group(1).strip()
        if text != "## AI Insight":
            print()
            print(text)


def cmd_read_session(start_date=None, end_date=None):
    if start_date is None:
        start_date = today_str()
    if end_date is None:
        end_date = start_date

    # Date boundaries in SP timezone
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=SP_TZ)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=SP_TZ) + timedelta(days=1)

    if not os.path.exists(SESSION_FILE):
        print(f"Session file not found: {SESSION_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(SESSION_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue

            ts = msg.get("timestamp", "")
            if not ts:
                continue

            try:
                msg_dt = datetime.fromisoformat(ts)
                # If naive (no tzinfo), assume UTC
                if msg_dt.tzinfo is None:
                    msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                # Convert to SP timezone
                msg_dt = msg_dt.astimezone(SP_TZ)
            except (ValueError, TypeError):
                continue

            if msg_dt < start_dt or msg_dt >= end_dt:
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle structured content (text blocks)
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                content = " ".join(parts)

            # Truncate long assistant messages
            if role == "assistant" and len(content) > 200:
                content = content[:200] + "..."

            time_str = msg_dt.strftime("%H:%M")
            print(f"[{time_str}] {role}: {content}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "append":
        if len(sys.argv) < 3:
            print("Usage: journal_writer.py append \"- [HH:MM] entry\"", file=sys.stderr)
            sys.exit(1)
        cmd_append(sys.argv[2])

    elif cmd == "append-multi":
        if len(sys.argv) < 3:
            print("Usage: journal_writer.py append-multi \"- [HH:MM] a\\n- [HH:MM] b\"", file=sys.stderr)
            sys.exit(1)
        cmd_append_multi(sys.argv[2])

    elif cmd == "append-insight":
        if len(sys.argv) < 3:
            print("Usage: journal_writer.py append-insight \"insight text\"", file=sys.stderr)
            sys.exit(1)
        cmd_append_insight(sys.argv[2])

    elif cmd == "read-journal":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_read_journal(date_str)

    elif cmd == "populate":
        mode = sys.argv[2] if len(sys.argv) > 2 else "morning"
        if mode not in ("morning", "evening"):
            print("Usage: journal_writer.py populate [morning|evening]", file=sys.stderr)
            sys.exit(1)
        cmd_populate(mode)

    elif cmd == "read-session":
        start = sys.argv[2] if len(sys.argv) > 2 else None
        end = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_read_session(start, end)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
