#!/usr/bin/env python3
"""
Calendar CLI for nanobot — unified access to Nextcloud (personal) and Google (work) calendars.

Usage:
    python3 calendar_api.py today                                              # Today's schedule
    python3 calendar_api.py upcoming [days]                                    # Next N days (default 7)
    python3 calendar_api.py free [date] [min_minutes]                          # Free time slots
    python3 calendar_api.py next                                               # Next upcoming event
    python3 calendar_api.py add "title" "start" "end" ["description"] ["location"]
    python3 calendar_api.py delete <event_id>
"""

import os
import pickle
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

# Nextcloud CalDAV config
NEXTCLOUD_CALDAV_URL = os.environ.get("NEXTCLOUD_CALDAV_URL", "")
NEXTCLOUD_USERNAME = os.environ.get("NEXTCLOUD_USERNAME", "")
NEXTCLOUD_PASSWORD = os.environ.get("NEXTCLOUD_PASSWORD", "")

# Google Calendar config
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "")
GOOGLE_CREDENTIALS_FILE = Path(os.environ.get("GOOGLE_CREDENTIALS_FILE", "/root/.nanobot/google_credentials.json"))
_GOOGLE_TOKEN_SOURCE = Path(os.environ.get("GOOGLE_TOKEN_FILE", "/root/.nanobot/google_token.pickle"))
# Use a writable copy so token refresh works (source is mounted read-only)
GOOGLE_TOKEN_FILE = Path("/tmp/google_token.pickle")


# =============================================================================
# Data Classes
# =============================================================================

def _name_from_email(email: str) -> str:
    """Try to derive 'First Last' from an email like first.last@domain.com."""
    local = email.split("@")[0] if "@" in email else ""
    if not local:
        return ""
    # Split on . - _ and capitalize each part
    parts = [p for sep in [".", "-", "_"] for p in local.split(sep)] if any(c in local for c in ".-_") else []
    if len(parts) >= 2:
        # Re-split properly: use the first separator found
        for sep in [".", "-", "_"]:
            if sep in local:
                parts = local.split(sep)
                break
        return " ".join(p.capitalize() for p in parts if p)
    return ""


@dataclass
class EventAttendee:
    name: str
    email: str

    def resolved_name(self) -> str:
        """Return the best name available: displayName > derived from email > empty."""
        if self.name and self.name != self.email:
            return self.name
        return _name_from_email(self.email)

    def format(self) -> str:
        resolved = self.resolved_name()
        if resolved:
            return f"{resolved} <{self.email}>"
        return self.email


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    calendar: str  # "personal" or "work"
    description: str = ""
    location: str = ""
    all_day: bool = False
    attendees: Optional[List['EventAttendee']] = None

    def format_short(self) -> str:
        if self.all_day:
            time_str = "All day"
        else:
            time_str = f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"
        cal_tag = "[personal]" if self.calendar == "personal" else "[work]"
        return f"{cal_tag} {time_str}: {self.title}"

    def format_full(self) -> str:
        lines = [f"  Title: {self.title}"]
        lines.append(f"  Calendar: {'Personal (Nextcloud)' if self.calendar == 'personal' else 'Work (Google)'}")
        if self.all_day:
            lines.append(f"  Date: {self.start.strftime('%Y-%m-%d')} (All day)")
        else:
            if self.start.date() == self.end.date():
                lines.append(f"  Time: {self.start.strftime('%Y-%m-%d %H:%M')} - {self.end.strftime('%H:%M')}")
            else:
                lines.append(f"  Start: {self.start.strftime('%Y-%m-%d %H:%M')}")
                lines.append(f"  End: {self.end.strftime('%Y-%m-%d %H:%M')}")
        if self.location:
            lines.append(f"  Location: {self.location}")
        if self.description:
            desc = self.description[:200]
            lines.append(f"  Description: {desc}")
        lines.append(f"  ID: {self.id}")
        return "\n".join(lines)


# =============================================================================
# Nextcloud CalDAV Client
# =============================================================================

class NextcloudCalendar:
    def __init__(self):
        self.url = NEXTCLOUD_CALDAV_URL
        self.username = NEXTCLOUD_USERNAME
        self.password = NEXTCLOUD_PASSWORD
        self._client = None
        self._calendar = None

    def _connect(self):
        if self._calendar is not None:
            return self._calendar
        import caldav
        self._client = caldav.DAVClient(
            url=self.url, username=self.username, password=self.password
        )
        self._calendar = caldav.Calendar(client=self._client, url=self.url)
        return self._calendar

    def get_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        try:
            calendar = self._connect()
            events = calendar.search(start=start, end=end, event=True, expand=True)
            result = []
            for event in events:
                try:
                    vevent = event.vobject_instance.vevent
                    dtstart = vevent.dtstart.value
                    dtend = vevent.dtend.value if hasattr(vevent, 'dtend') else dtstart + timedelta(hours=1)
                    all_day = not isinstance(dtstart, datetime)
                    if all_day:
                        dtstart = datetime.combine(dtstart, datetime.min.time()).replace(tzinfo=TZ)
                        dtend = datetime.combine(dtend, datetime.min.time()).replace(tzinfo=TZ)
                    else:
                        if dtstart.tzinfo is None:
                            dtstart = dtstart.replace(tzinfo=TZ)
                        if dtend.tzinfo is None:
                            dtend = dtend.replace(tzinfo=TZ)
                    att_list = []
                    if hasattr(vevent, 'attendee'):
                        attendee_val = vevent.attendee
                        # Can be a single value or a list
                        att_items = attendee_val if isinstance(attendee_val, list) else [attendee_val]
                        for att in att_items:
                            email = str(att.value).replace('mailto:', '').replace('MAILTO:', '')
                            cn = att.params.get('CN', [''])[0] if hasattr(att, 'params') and att.params else ''
                            att_list.append(EventAttendee(name=str(cn), email=email))
                    result.append(CalendarEvent(
                        id=str(event.url),
                        title=str(vevent.summary.value) if hasattr(vevent, 'summary') else "No title",
                        start=dtstart, end=dtend, calendar="personal",
                        description=str(vevent.description.value) if hasattr(vevent, 'description') else "",
                        location=str(vevent.location.value) if hasattr(vevent, 'location') else "",
                        all_day=all_day,
                        attendees=att_list or None,
                    ))
                except Exception as e:
                    print(f"Warning: failed to parse Nextcloud event: {e}", file=sys.stderr)
            return result
        except Exception as e:
            print(f"Error fetching Nextcloud events: {e}", file=sys.stderr)
            return []

    def add_event(self, title: str, start: datetime, end: datetime,
                  description: str = "", location: str = "") -> Optional[str]:
        from icalendar import Calendar as iCalendar, Event as iEvent
        calendar = self._connect()
        cal = iCalendar()
        cal.add('prodid', '-//Friday AI Assistant//EN')
        cal.add('version', '2.0')
        event = iEvent()
        uid = str(uuid.uuid4())
        event.add('uid', uid)
        event.add('summary', title)
        event.add('dtstart', start)
        event.add('dtend', end)
        if description:
            event.add('description', description)
        if location:
            event.add('location', location)
        event.add('dtstamp', datetime.now(timezone.utc))
        cal.add_component(event)
        calendar.save_event(cal.to_ical().decode('utf-8'))
        return uid

    def delete_event(self, event_id: str) -> bool:
        import caldav
        self._connect()
        event = caldav.Event(client=self._client, url=event_id, parent=self._calendar)
        event.delete()
        return True


# =============================================================================
# Google Calendar Client (read-only)
# =============================================================================

class GoogleCalendar:
    def __init__(self):
        self.calendar_id = GOOGLE_CALENDAR_ID
        self._service = None

    def _connect(self):
        if self._service is not None:
            return self._service
        import shutil
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        # Copy token to writable location if not already there
        if not GOOGLE_TOKEN_FILE.exists() and _GOOGLE_TOKEN_SOURCE.exists():
            shutil.copy2(_GOOGLE_TOKEN_SOURCE, GOOGLE_TOKEN_FILE)

        creds = None
        if GOOGLE_TOKEN_FILE.exists():
            with open(GOOGLE_TOKEN_FILE, 'rb') as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(GOOGLE_TOKEN_FILE, 'wb') as f:
                    pickle.dump(creds, f)
            else:
                raise RuntimeError("Google token missing or invalid. Re-auth needed (run OAuth flow on host).")
        self._service = build('calendar', 'v3', credentials=creds)
        return self._service

    def get_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        try:
            service = self._connect()
            events_result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy='startTime',
            ).execute()
            result = []
            for ev in events_result.get('items', []):
                try:
                    start_data = ev.get('start', {})
                    end_data = ev.get('end', {})
                    all_day = 'date' in start_data
                    if all_day:
                        dtstart = datetime.fromisoformat(start_data['date'])
                        dtstart = datetime.combine(dtstart.date(), datetime.min.time()).replace(tzinfo=TZ)
                        dtend = datetime.fromisoformat(end_data['date'])
                        dtend = datetime.combine(dtend.date(), datetime.min.time()).replace(tzinfo=TZ)
                    else:
                        dtstart = datetime.fromisoformat(start_data['dateTime'].replace('Z', '+00:00'))
                        dtend = datetime.fromisoformat(end_data['dateTime'].replace('Z', '+00:00'))
                    att_list = []
                    for att in ev.get('attendees', []):
                        att_list.append(EventAttendee(
                            name=att.get('displayName', ''),
                            email=att.get('email', ''),
                        ))
                    result.append(CalendarEvent(
                        id=ev['id'], title=ev.get('summary', 'No title'),
                        start=dtstart, end=dtend, calendar="work",
                        description=ev.get('description', ''),
                        location=ev.get('location', ''), all_day=all_day,
                        attendees=att_list or None,
                    ))
                except Exception as e:
                    print(f"Warning: failed to parse Google event: {e}", file=sys.stderr)
            return result
        except Exception as e:
            print(f"Error fetching Google events: {e}", file=sys.stderr)
            return []


# =============================================================================
# Unified Calendar Manager
# =============================================================================

class CalendarManager:
    def __init__(self):
        self._nextcloud = None
        self._google = None

    @property
    def nextcloud(self) -> NextcloudCalendar:
        if self._nextcloud is None:
            self._nextcloud = NextcloudCalendar()
        return self._nextcloud

    @property
    def google(self) -> GoogleCalendar:
        if self._google is None:
            self._google = GoogleCalendar()
        return self._google

    def get_all_events(self, start: datetime, end: datetime) -> List[CalendarEvent]:
        events = []
        try:
            events.extend(self.nextcloud.get_events(start, end))
        except Exception as e:
            print(f"Warning: personal calendar unavailable: {e}", file=sys.stderr)
        try:
            events.extend(self.google.get_events(start, end))
        except Exception as e:
            print(f"Warning: work calendar unavailable: {e}", file=sys.stderr)
        events.sort(key=lambda e: e.start)
        return events

    def find_free_slots(self, date: datetime, min_duration_minutes: int = 30,
                        work_start: int = 9, work_end: int = 18) -> List[Tuple[datetime, datetime]]:
        start_of_day = date.replace(hour=work_start, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=work_end, minute=0, second=0, microsecond=0)
        events = self.get_all_events(start_of_day, end_of_day)
        timed_events = sorted([e for e in events if not e.all_day], key=lambda e: e.start)
        free_slots = []
        current_time = start_of_day
        for event in timed_events:
            if event.start > current_time:
                gap = (event.start - current_time).total_seconds() / 60
                if gap >= min_duration_minutes:
                    free_slots.append((current_time, event.start))
            current_time = max(current_time, event.end)
        if current_time < end_of_day:
            gap = (end_of_day - current_time).total_seconds() / 60
            if gap >= min_duration_minutes:
                free_slots.append((current_time, end_of_day))
        return free_slots


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_today(mgr: CalendarManager):
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = mgr.get_all_events(start, end)
    if not events:
        print(f"No events today ({now.strftime('%A, %Y-%m-%d')}).")
        return
    print(f"Schedule for today ({now.strftime('%A, %Y-%m-%d')}):\n")
    for ev in events:
        status = ""
        if not ev.all_day:
            if ev.start <= now < ev.end:
                status = " << NOW"
            elif ev.end <= now:
                status = " (done)"
        print(f"  {ev.format_short()}{status}")


def cmd_upcoming(mgr: CalendarManager, days: int = 7):
    now = datetime.now(TZ)
    end = now + timedelta(days=days)
    events = mgr.get_all_events(now, end)
    if not events:
        print(f"No events in the next {days} days.")
        return
    print(f"Upcoming events (next {days} days):\n")
    current_date = None
    for ev in events:
        ev_date = ev.start.date()
        if ev_date != current_date:
            current_date = ev_date
            day_name = ev.start.strftime('%A, %Y-%m-%d')
            print(f"\n  {day_name}:")
        print(f"    {ev.format_short()}")


def cmd_free(mgr: CalendarManager, date_str: str = "", min_minutes: int = 30):
    if date_str:
        target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=TZ)
    else:
        target = datetime.now(TZ)
    slots = mgr.find_free_slots(target, min_minutes)
    date_label = target.strftime('%A, %Y-%m-%d')
    if not slots:
        print(f"No free slots >= {min_minutes}min on {date_label} (09:00-18:00).")
        return
    print(f"Free slots on {date_label} (>= {min_minutes}min):\n")
    for s, e in slots:
        dur = int((e - s).total_seconds() / 60)
        print(f"  {s.strftime('%H:%M')} - {e.strftime('%H:%M')} ({dur}min)")


def cmd_next(mgr: CalendarManager):
    now = datetime.now(TZ)
    events = mgr.get_all_events(now, now + timedelta(days=7))
    for ev in events:
        if ev.start > now:
            delta = ev.start - now
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            if hours > 0:
                time_str = f"{hours}h {minutes}min"
            else:
                time_str = f"{minutes}min"
            print(f"Next event (in {time_str}):\n")
            print(ev.format_full())
            return
    print("No upcoming events in the next 7 days.")


def cmd_add(mgr: CalendarManager, title: str, start_str: str, end_str: str,
            description: str = "", location: str = ""):
    now = datetime.now(TZ)
    # Parse start
    if len(start_str) <= 5:
        start = datetime.strptime(f"{now.strftime('%Y-%m-%d')} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    else:
        start = datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    # Parse end
    if len(end_str) <= 5:
        end = datetime.strptime(f"{start.strftime('%Y-%m-%d')} {end_str}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    else:
        end = datetime.strptime(end_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)

    uid = mgr.nextcloud.add_event(title, start, end, description, location)
    print(f"Event added to Personal (Nextcloud) calendar.")
    print(f"  Title: {title}")
    print(f"  Time: {start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')}")
    if description:
        print(f"  Description: {description}")
    if location:
        print(f"  Location: {location}")
    print(f"  UID: {uid}")


def cmd_event_attendees(mgr: CalendarManager, query: str):
    """Find a matching event by title keywords and print its attendees."""
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = mgr.get_all_events(start, end)

    query_lower = query.lower()
    matched = None
    for ev in events:
        if query_lower in ev.title.lower():
            matched = ev
            break

    if not matched:
        # Try partial word matching
        query_words = query_lower.split()
        for ev in events:
            title_lower = ev.title.lower()
            if all(w in title_lower for w in query_words):
                matched = ev
                break

    if not matched:
        print(f"No event matching '{query}' found today.")
        return

    print(f"Event: {matched.title}")
    if not matched.attendees:
        print("No attendees listed.")
        return

    print(f"Attendees ({len(matched.attendees)}):")
    for att in matched.attendees:
        print(f"  {att.format()}")


def cmd_delete(mgr: CalendarManager, event_id: str):
    mgr.nextcloud.delete_event(event_id)
    print(f"Event deleted from Personal (Nextcloud) calendar.")
    print(f"  ID: {event_id}")


# =============================================================================
# Main
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: calendar_api.py <command> [args...]")
        print("Commands: today, upcoming, free, next, add, delete, event-attendees")
        sys.exit(1)

    cmd = sys.argv[1]
    mgr = CalendarManager()

    try:
        if cmd == "today":
            cmd_today(mgr)
        elif cmd == "upcoming":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            cmd_upcoming(mgr, days)
        elif cmd == "free":
            date_str = sys.argv[2] if len(sys.argv) > 2 else ""
            min_min = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            cmd_free(mgr, date_str, min_min)
        elif cmd == "next":
            cmd_next(mgr)
        elif cmd == "add":
            if len(sys.argv) < 5:
                print("Usage: calendar_api.py add \"title\" \"start\" \"end\" [\"description\"] [\"location\"]")
                sys.exit(1)
            title = sys.argv[2]
            start_str = sys.argv[3]
            end_str = sys.argv[4]
            description = sys.argv[5] if len(sys.argv) > 5 else ""
            location = sys.argv[6] if len(sys.argv) > 6 else ""
            cmd_add(mgr, title, start_str, end_str, description, location)
        elif cmd == "event-attendees":
            if len(sys.argv) < 3:
                print("Usage: calendar_api.py event-attendees \"search query\"")
                sys.exit(1)
            cmd_event_attendees(mgr, sys.argv[2])
        elif cmd == "delete":
            if len(sys.argv) < 3:
                print("Usage: calendar_api.py delete <event_id>")
                sys.exit(1)
            cmd_delete(mgr, sys.argv[2])
        else:
            print(f"Unknown command: {cmd}")
            print("Commands: today, upcoming, free, next, add, delete, event-attendees")
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
