---
name: calendar
description: View, create, and manage calendar events across personal (Nextcloud) and work (Google) calendars.
---

# Calendar Skill

Manage the user's calendars:
- **Personal** (Nextcloud): full CRUD — view, create, delete events
- **Work** (Google Calendar): read-only — view events, check availability

## Commands

All commands use `exec`:

### Today's schedule (both calendars)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py today
```

### Upcoming events (next N days, default 7)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py upcoming
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py upcoming 14
```

### Free time slots (09:00-18:00)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py free
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py free 2026-03-05
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py free 2026-03-05 60
```

### Next upcoming event
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py next
```

### Event attendees
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py event-attendees "Meeting Title"
```
Searches today's events for a title match and prints attendee names + emails. Used by the meeting skill to get full attendee details.

### Add event (personal calendar only)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py add "Dentist" "14:00" "15:00"
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py add "Team dinner" "2026-03-10 19:00" "2026-03-10 22:00" "Celebration" "Madalosso"
```

Time formats:
- `HH:MM` — assumes today
- `YYYY-MM-DD HH:MM` — specific date

### Delete event (personal calendar only)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py delete "<event_id>"
```

The event_id is the CalDAV URL shown in event details. Get it from `today` or `upcoming` output first.

## Rules

1. Always show **both** calendars when asked about schedule — run `today` or `upcoming`
2. Work calendar is **read-only** — never try to add/delete work events
3. When adding events, confirm the details with the user before running `add`
4. When deleting, show the event details first and confirm before running `delete`
5. For "am I free at X?", use the `free` command
6. Times are in America/Sao_Paulo timezone
