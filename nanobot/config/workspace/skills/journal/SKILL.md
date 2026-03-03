# Journal Skill

Manages daily journal entries and generates weekly therapy summaries.

## Triggers

- "therapy prep" / "weekly summary" / "what happened this week" / "resumo da semana" → weekly therapy summary
- "log this" / "add to journal" / "anota isso" → manual journal entry
- "what's in my journal?" / "o que tem no meu diário?" → read today's journal

## Tool

```
exec: python3 /root/.nanobot/workspace/skill-tools/journal_writer.py <command> [args]
```

### Commands

| Command | Usage | Description |
|---------|-------|-------------|
| `append` | `append "- [HH:MM] entry"` | Append single entry to today's note |
| `append-multi` | `append-multi "- [HH:MM] a\n- [HH:MM] b"` | Append multiple entries |
| `append-insight` | `append-insight "reflection text"` | Write/replace AI Insight section |
| `populate` | `populate [morning\|evening]` | Fill weather/health/calendar/habits sections |
| `read-journal` | `read-journal [YYYY-MM-DD]` | Read journal + AI Insight sections (default: today) |
| `read-session` | `read-session [start] [end]` | Read session messages in date range (default: today) |

## Manual Entry

When user says "log this" or similar:
1. Format their input as `- [HH:MM] description` using current time
2. Run: `python3 /root/.nanobot/workspace/skill-tools/journal_writer.py append "- [HH:MM] description"`
3. Confirm: "Logged."

## Weekly Therapy Summary

When user says "therapy prep" or similar:

1. Determine last 7 days date range (today back to today-6)
2. For each day, read the daily note: `read_file: /time/2.2 Daily/YYYY-MM-DD.md`
3. Read session history: `exec: python3 /root/.nanobot/workspace/skill-tools/journal_writer.py read-session START_DATE END_DATE`
4. Compile a structured summary:
   - **Key events & activities** — what happened day by day
   - **Emotional & stress patterns** — Garmin stress data + 🔴 stress context logs
   - **Concerns & worries** — things expressed in conversation
   - **Wins & positive moments** — celebrations, accomplishments
   - **Recurring themes** — patterns across the week
5. Send summary to chat (don't write to file unless asked)

## Rules

- Only generate therapy summaries when explicitly asked
- Be honest and factual — don't diagnose or interpret emotions beyond what was said
- 🔴 Stress context logs are especially important — always include them prominently
- Match language (pt-BR or English) based on how the user asked
- Keep the summary focused and readable — this goes to a therapy session
