---
name: people
description: Look up and update person notes in the Obsidian vault.
---

# People Skill

Bidirectional person knowledge management — read info about people and update their notes.

## Triggers

- **Read:** "who is X?", "what do I know about X?", "tell me about X", "quem é X?"
- **Update:** "X just got promoted", "X's birthday is...", "remember that X...", "anota que X..."
- Also triggered implicitly when the user shares info about a person

## Tool

```
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py <command> [args]
```

### Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `find-person` | `find-person "Name"` | Search for a person note (case-insensitive, partial match) |
| `ensure-person` | `ensure-person "Name" "tag" "company"` | Create person note if not exists |
| `add-person-context` | `add-person-context "Name" "context line"` | Append to Context section |
| `list-people` | `list-people` | List all known people |

## Read Flow

When the user asks about a person:

1. Search for the person:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py find-person "Name"
```

2. If found, read the note:
```
read_file: <path from find-person output>
```
Summarize the key info naturally — context, key details, company, recent interactions. Don't dump raw markdown.

3. If not found, tell the user and offer to create a note.

## Update Flow

When the user shares info about a person:

1. Ensure the person note exists:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py ensure-person "Full Name" "work" "Company"
```
Use `work`, `friend`, or `family` as the tag based on context.

2. Add the new context:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/meeting_notes.py add-person-context "Full Name" "Got promoted to Senior Engineer (2026-03-03)"
```
Always include the date in the context line.

3. Confirm: "Updated [[Name]]'s note."

## Rules

- **The user's name is defined in USER.md.** Any reference to "me", "I" means the user. Their note already exists — never create a duplicate.
- When reading person notes, present info naturally — don't dump raw markdown
- When updating, append to the Context section — never overwrite existing content
- Always write to `/notes/` — if a person exists only in `/vault/1. Notes/` (read-only), the script copies it automatically
- Use the date in context lines so the timeline is traceable
- Person notes MUST always use "First Last" format — never create notes with only a first name. Use `find-person` to resolve partial names, or ask the user.
- Tag types: `person/work`, `person/friend`, `person/family` — choose based on relationship context
- All notes must be written in English
