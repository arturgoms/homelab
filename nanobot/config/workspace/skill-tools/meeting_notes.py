#!/usr/bin/env python3
"""Meeting notes and person notes manager for Obsidian vault.

Subcommands:
  create-meeting  "Title" "YYYY-MM-DD" "attendee1,attendee2" "area_tag" [--event "Event"] [--time "HH:MM-HH:MM"]
  write-section   "Title" "section_name" "content"
  ensure-person   "Full Name" "tag" "company"
  add-person-context "Full Name" "context line"
  find-person     "Name"
  list-people
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

MEETING_DIR = "/time/2.3 Meetings"
NOTES_DIR = "/notes"
VAULT_NOTES_DIR = "/vault/1. Notes"
MEETING_TEMPLATE = "/vault/3. Resources/3.2 Templates/Meeting.md"
PERSON_TEMPLATE = "/vault/3. Resources/3.2 Templates/Person.md"

SP_TZ = timezone(timedelta(hours=-3))
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def today_str():
    return datetime.now(SP_TZ).strftime("%Y-%m-%d")


def format_date_long(date_str):
    """Convert YYYY-MM-DD to 'Wednesday, March 3, 2026' format."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = WEEKDAYS[d.weekday()]
    return d.strftime(f"{day_name}, %B %-d, %Y")


def read_template(path):
    """Read a template file."""
    if not os.path.exists(path):
        print(f"ERROR: Template not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return f.read()


def remove_frontmatter_field(fm, field):
    """Remove a field from frontmatter text."""
    return re.sub(rf"^{re.escape(field)}:.*\n", "", fm, flags=re.MULTILINE)


def remove_frontmatter_tag(fm, tag):
    """Remove a specific tag line from frontmatter."""
    return re.sub(rf"^\s*- {re.escape(tag)}\s*\n", "", fm, flags=re.MULTILINE)


# --- create-meeting ---

def cmd_create_meeting(args):
    if len(args) < 4:
        print("Usage: meeting_notes.py create-meeting \"Title\" \"YYYY-MM-DD\" \"attendees\" \"area_tag\" [--event \"Event\"] [--time \"HH:MM-HH:MM\"]", file=sys.stderr)
        sys.exit(1)

    title = args[0]
    date_str = args[1]
    attendees_raw = args[2]
    area_tag = args[3]

    # Parse optional flags
    event_title = None
    time_range = None
    i = 4
    while i < len(args):
        if args[i] == "--event" and i + 1 < len(args):
            event_title = args[i + 1]
            i += 2
        elif args[i] == "--time" and i + 1 < len(args):
            time_range = args[i + 1]
            i += 2
        else:
            i += 1

    attendees = [a.strip() for a in attendees_raw.split(",") if a.strip()]
    attendees_fm = "\n".join(f'  - "[[{a}]]"' for a in attendees)
    attendees_inline = ", ".join(f"[[{a}]]" for a in attendees)

    # Read and process template
    template = read_template(MEETING_TEMPLATE)

    # Split frontmatter and body
    fm_match = re.match(r"(---\n)(.*?)(---\n)(.*)", template, re.DOTALL)
    if not fm_match:
        print("ERROR: Could not parse template frontmatter", file=sys.stderr)
        sys.exit(1)

    fm = fm_match.group(2)
    body = fm_match.group(4)

    # Build frontmatter
    # Remove template tag and id field
    fm = remove_frontmatter_tag(fm, "extra/template")
    fm = remove_frontmatter_field(fm, "id")

    # Remove the empty person/ tag
    fm = remove_frontmatter_tag(fm, "person/")

    # Set area tag
    fm = re.sub(r"^\s*- area/\s*$", f"  - area/{area_tag}", fm, flags=re.MULTILINE)

    # Set date
    fm = re.sub(r'^date:\n\s*".*?":\s*$', f"date: {date_str}", fm, flags=re.MULTILINE)
    # Fallback if date format is different
    fm = re.sub(r"^date:.*$", f"date: {date_str}", fm, flags=re.MULTILINE)

    # Set attendees
    fm = re.sub(
        r"^attendees:\n\s*- *\n?",
        f"attendees:\n{attendees_fm}\n",
        fm,
        flags=re.MULTILINE,
    )

    # Build body
    # Replace title placeholder
    body = re.sub(r"# \{\{title\}\}", f"# [[{title}]]", body)

    # Fill meeting details table
    date_long = format_date_long(date_str)
    time_display = time_range if time_range else ""
    date_time_str = f"{date_long} at {time_display}" if time_display else date_long

    body = re.sub(
        r"\| \*\*Date & Time\*\* \|.*\|",
        f"| **Date & Time** | {date_time_str} |",
        body,
    )

    # Add calendar event row if provided
    if event_title:
        body = re.sub(
            r"(\| \*\*Purpose\*\*\s*\|.*\|)",
            f'| **Calendar Event** | {event_title} |\n\\1',
            body,
        )

    # Replace attendees in the table (add an Attendees row after Date & Time)
    body = re.sub(
        r"(\| \*\*Date & Time\*\* \|.*\|)",
        f"\\1\n| **Attendees**   | {attendees_inline} |",
        body,
    )

    # Write the file
    content = f"---\n{fm}---\n{body}"
    out_path = os.path.join(MEETING_DIR, f"{title}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(content)

    print(f"created: {out_path}")


# --- write-section ---

def cmd_write_section(args):
    if len(args) < 3:
        print('Usage: meeting_notes.py write-section "Title" "section" "content"', file=sys.stderr)
        sys.exit(1)

    title = args[0]
    section = args[1]
    content = args[2].replace("\\n", "\n")

    file_path = os.path.join(MEETING_DIR, f"{title}.md")
    if not os.path.exists(file_path):
        print(f"ERROR: Meeting note not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r") as f:
        note = f.read()

    section_map = {
        "discussion": "## Discussion & Notes",
        "decisions": "### Decisions Made",
        "actions": "### Action Items",
        "agenda": "## Agenda",
    }

    header = section_map.get(section)
    if not header:
        print(f"ERROR: Unknown section '{section}'. Use: {', '.join(section_map.keys())}", file=sys.stderr)
        sys.exit(1)

    # Find the section and replace its content (up to the next section of same or higher level)
    header_level = header.count("#")
    pattern = rf"({re.escape(header)}\n).*?(?=\n{'#' * header_level} |\n{'#' * (header_level - 1)} |\Z)"
    match = re.search(pattern, note, re.DOTALL)

    if not match:
        print(f"ERROR: Section '{header}' not found in note", file=sys.stderr)
        sys.exit(1)

    # Get everything after the header line, find the description line (italic) and placeholder
    section_start = match.start()
    section_text = match.group(0)

    # Keep the header and any italic description line, replace the rest
    lines = section_text.split("\n")
    kept = [lines[0]]  # header
    for line in lines[1:]:
        if line.startswith("_") and line.endswith("_"):
            kept.append(line)
            break
        elif line.strip() == "":
            kept.append(line)
        else:
            break

    new_section = "\n".join(kept) + "\n\n" + content + "\n"
    note = note[:section_start] + new_section + note[match.end():]

    with open(file_path, "w") as f:
        f.write(note)

    print(f"Updated '{section}' in {file_path}")


# --- ensure-person ---

def find_person_file(name):
    """Find an existing person note by exact name match."""
    filename = f"{name}.md"
    # Check writable /notes/ first
    path = os.path.join(NOTES_DIR, filename)
    if os.path.exists(path):
        return path
    # Check read-only vault
    path = os.path.join(VAULT_NOTES_DIR, filename)
    if os.path.exists(path):
        return path
    return None


def cmd_ensure_person(args):
    if len(args) < 2:
        print('Usage: meeting_notes.py ensure-person "Full Name" "tag" ["company"] ["email"]', file=sys.stderr)
        sys.exit(1)

    name = args[0]
    tag = args[1]
    company = args[2] if len(args) > 2 and args[2] else ""
    email = args[3] if len(args) > 3 and args[3] else ""

    existing = find_person_file(name)
    if existing:
        print(f"exists: {existing}")
        return

    # Create from template
    template = read_template(PERSON_TEMPLATE)

    fm_match = re.match(r"(---\n)(.*?)(---\n)(.*)", template, re.DOTALL)
    if not fm_match:
        print("ERROR: Could not parse person template frontmatter", file=sys.stderr)
        sys.exit(1)

    fm = fm_match.group(2)
    body = fm_match.group(4)

    # Process frontmatter
    fm = remove_frontmatter_tag(fm, "extra/template")
    fm = remove_frontmatter_field(fm, "id")

    # Set person tag
    fm = re.sub(r"^\s*- person/\s*$", f"  - person/{tag}", fm, flags=re.MULTILINE)

    # Set company
    if company:
        fm = re.sub(r"^company:\s*$", f'company: "[[{company}]]"', fm, flags=re.MULTILINE)

    # Set email
    if email:
        fm = re.sub(r"^email:\s*$", f"email: {email}", fm, flags=re.MULTILINE)

    # Set aliases (first name)
    first_name = name.split()[0] if " " in name else ""
    if first_name:
        # Insert aliases after tags block
        tags_end = re.search(r"^  - person/.*\n", fm, re.MULTILINE)
        if tags_end:
            insert_at = tags_end.end()
            fm = fm[:insert_at] + f"aliases:\n  - {first_name}\n" + fm[insert_at:]
        else:
            fm += f"aliases:\n  - {first_name}\n"

    # Set last_contacted
    fm = re.sub(r'^last_contacted:\n\s*".*?":\s*$', f"last_contacted: {today_str()}", fm, flags=re.MULTILINE)
    # Fallback
    fm = re.sub(r"^last_contacted:.*$", f"last_contacted: {today_str()}", fm, flags=re.MULTILINE)

    # Process body - replace title placeholder
    body = re.sub(r"# \[\[\{\{title\}\}\]\]", f"# [[{name}]]", body)

    content = f"---\n{fm}---\n{body}"
    out_path = os.path.join(NOTES_DIR, f"{name}.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(content)

    print(f"created: {out_path}")


# --- add-person-context ---

def cmd_add_person_context(args):
    if len(args) < 2:
        print('Usage: meeting_notes.py add-person-context "Full Name" "context line"', file=sys.stderr)
        sys.exit(1)

    name = args[0]
    context_line = args[1]

    existing = find_person_file(name)
    if not existing:
        print(f"ERROR: Person note not found for '{name}'. Use ensure-person first.", file=sys.stderr)
        sys.exit(1)

    # Read the file
    with open(existing, "r") as f:
        content = f.read()

    # If file is in vault (read-only), copy to /notes/ first
    write_path = existing
    if existing.startswith(VAULT_NOTES_DIR):
        write_path = os.path.join(NOTES_DIR, f"{name}.md")
        os.makedirs(os.path.dirname(write_path), exist_ok=True)
        with open(write_path, "w") as f:
            f.write(content)

    # Find ## Context or ## Biography section and append
    context_match = re.search(r"(## Context\n(?:.*?\n)*?)(?=\n---|\n## |\Z)", content, re.DOTALL)
    bio_match = re.search(r"(## Biography\n(?:.*?\n)*?)(?=\n---|\n## |\Z)", content, re.DOTALL)

    target_match = context_match or bio_match
    if not target_match:
        print(f"ERROR: No Context or Biography section found in {existing}", file=sys.stderr)
        sys.exit(1)

    section_text = target_match.group(0)
    insert_pos = target_match.end()

    # Append the new line before the section ends
    new_line = f"- {context_line}\n"
    content = content[:insert_pos] + new_line + content[insert_pos:]

    # Update last_contacted in frontmatter
    content = re.sub(r"^last_contacted:.*$", f"last_contacted: {today_str()}", content, flags=re.MULTILINE)

    with open(write_path, "w") as f:
        f.write(content)

    print(f"Updated: {write_path}")


# --- find-person ---

def cmd_find_person(args):
    if len(args) < 1:
        print('Usage: meeting_notes.py find-person "Name"', file=sys.stderr)
        sys.exit(1)

    query = args[0].lower()
    results = []

    for search_dir in [NOTES_DIR, VAULT_NOTES_DIR]:
        if not os.path.isdir(search_dir):
            continue
        for fname in os.listdir(search_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(search_dir, fname)
            name_part = fname[:-3].lower()

            # Skip if already found from /notes/ (avoid duplicates)
            if any(os.path.basename(r) == fname for r in results):
                continue

            # Check filename match
            if query in name_part:
                results.append(fpath)
                continue

            # Check aliases in frontmatter + person tag
            try:
                with open(fpath, "r") as f:
                    head = f.read(2000)
                # Only consider files with person/ tag
                if "person/" not in head:
                    continue
                if query in head.lower():
                    results.append(fpath)
            except (OSError, UnicodeDecodeError):
                continue

    if results:
        for r in results:
            print(r)
    else:
        print(f"No person note found for '{args[0]}'")


# --- list-people ---

def cmd_list_people():
    seen = set()
    for search_dir in [NOTES_DIR, VAULT_NOTES_DIR]:
        if not os.path.isdir(search_dir):
            continue
        for fname in sorted(os.listdir(search_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(search_dir, fname)
            name = fname[:-3]
            if name in seen:
                continue
            # Check if it's a person note
            try:
                with open(fpath, "r") as f:
                    head = f.read(500)
                if "person/" in head:
                    seen.add(name)
                    print(name)
            except (OSError, UnicodeDecodeError):
                continue


# --- main ---

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "create-meeting":
        cmd_create_meeting(args)
    elif cmd == "write-section":
        cmd_write_section(args)
    elif cmd == "ensure-person":
        cmd_ensure_person(args)
    elif cmd == "add-person-context":
        cmd_add_person_context(args)
    elif cmd == "find-person":
        cmd_find_person(args)
    elif cmd == "list-people":
        cmd_list_people()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
