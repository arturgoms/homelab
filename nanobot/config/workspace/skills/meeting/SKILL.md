---
name: meeting
description: Create meeting notes in the Obsidian vault with attendee tracking and action items.
---

# Meeting Skill

When the user describes a meeting, create a structured meeting note in the vault.

## Triggers

- "meeting notes", "log meeting", "meeting with...", "had a meeting", "anotações da reunião"

## Tool

```
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py <command> [args]
```

### Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `create-meeting` | `create-meeting "Title" "YYYY-MM-DD" "att1,att2" "area" [--event "Event"] [--time "HH:MM-HH:MM"]` | Create meeting note from template |
| `write-section` | `write-section "Title" "section" "content"` | Write to a section (discussion, decisions, actions, agenda) |
| `ensure-person` | `ensure-person "Full Name" "tag" "company" ["email"]` | Create person note if not exists |
| `add-person-context` | `add-person-context "Full Name" "context"` | Append context to person note |

## Flow

When the user describes a meeting, follow these steps IN ORDER:

**Step 1 — Parse the summary.** Extract: title, date, attendees, area (work/personal), key discussion points, decisions, action items.

**Step 2 — Match calendar event.** Search today's calendar for a matching event:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py today
```
Match by title keywords, attendees, or time proximity. If a match is found, use the event time and title.

**Step 2b — Get attendee details from calendar.** If a calendar match was found, extract attendee names and emails:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/calendar_api.py event-attendees "Event Title"
```
This returns full names (derived from displayName or email) and email addresses.

**Step 2c — Resolve full names.** This is CRITICAL — all person notes and attendee references MUST use "First Last" format. For each attendee mentioned by the user:
1. Check `event-attendees` output for a matching full name (e.g., user says "Jane" → calendar shows "Jane Smith <jane@...>")
2. If not in calendar, search existing person notes:
   ```bash
   exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py find-person "Julian"
   ```
   If found (e.g., `/notes/Jane Smith.md`), use the filename as the full name.
3. If still only a first name, ask the user for the last name before proceeding.

**NEVER create a person note or meeting attendee entry with only a first name.** Always resolve to "First Last".

**Step 3 — Create the meeting note:**
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py create-meeting "Title" "YYYY-MM-DD" "attendee1,attendee2" "work" --event "Calendar Event Title" --time "14:00-15:00"
```
Omit `--event` and `--time` if no calendar match was found.

**Step 4 — Write sections.** Fill in the meeting content:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py write-section "Title" "discussion" "- Point 1\n- Point 2"
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py write-section "Title" "decisions" "- Decision 1"
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py write-section "Title" "actions" "- [ ] [[the user]]: Follow up on X by Friday\n- [ ] [[John Doe]]: Review the PR"
```

**Step 5 — Handle attendees.** For each attendee, create/verify their person note. If calendar attendee data is available from Step 2b, use the full name and email:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py ensure-person "Full Name" "work" "Company" "email@example.com"
```
Without calendar email (omit the email arg):
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py ensure-person "Full Name" "work" "Company"
```
If any new context about them was mentioned in the meeting:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py add-person-context "Full Name" "Led the program configuration discussion (2026-03-03)"
```

**Step 6 — Link to daily note.** Append a meeting reference to today's journal:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/journal_writer.py append "- [HH:MM] Meeting: [[Title]]"
```
Use the meeting start time if known, otherwise use current time.

**Step 7 — Link discovery.** Search the vault for notes related to topics discussed in the meeting:
```bash
exec: find /vault/1.\ Notes/ -iname "*keyword*" -name "*.md" 2>/dev/null | head -10
```
For each match, add `[[Note Title]]` wikilinks in the discussion section or body where relevant. Also check if any existing notes should link back to this meeting.

**Step 8 — Extract user action items.** Identify things the user personally needs to do and list them prominently.

**Step 9 — Confirm.** Show what was created: meeting note path, any new person notes, links discovered, and the user's action items.

## Rules

- **The user's name is defined in USER.md.** Any reference to "me", "I" in the meeting context means the user. Always include the user in the attendees list.
- The meeting title should be descriptive (e.g. "Program Configuration - How we render the view", not "Meeting with John")
- Default area tag is `work` unless the user specifies otherwise
- Attendees MUST always be "First Last" — never create notes or references with only a first name. Resolve via calendar data → find-person → ask user.
- Action items assigned to the user should be flagged prominently in the response
- All notes must be written in English
- Always use wikilinks `[[Name]]` for people references everywhere — in meeting body text, action items, decisions. Never use `@Name`.
- Action items format: `- [ ] [[Full Name]]: Task description`
