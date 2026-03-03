---
name: vault
description: Create, edit, move, search, and archive notes in the Obsidian vault following established conventions.
---

# Vault Skill

Full control over the user's Obsidian vault at `/vault`. Create, edit, move, search, and archive notes following the vault's conventions.

## Triggers

- **Search:** "search my notes for X", "find in vault", "what did I write about X?"
- **Read:** "read my note about X", "show me my note on Y"
- **Create:** "create a note about X", "new note on Y", "cria uma nota sobre X"
- **Edit:** "update my note on X", "add this to my note about Y"
- **Move:** "move this note to archive", "organize this note"
- **Link:** "link these notes", "what's related to X?"

## Vault Structure

```
/vault/
├── 0. Overview/           # Control center
│   ├── 0.1 Inbox/         # Unsorted new notes
│   ├── 0.2 Dashboards/    # Dataview dashboards
│   └── 0.3 MOCs/          # Maps of Content
├── 1. Notes/              # Permanent knowledge (topics, sources, people, atomic)
├── 2. Time/               # Time-bound records
│   ├── 2.1 Weekly/        # Weekly reviews
│   ├── 2.2 Daily/         # Daily journal entries
│   └── 2.3 Meetings/      # Meeting notes
├── 3. Resources/
│   ├── 3.1 Attachments/   # Images, files
│   ├── 3.2 Templates/     # Note templates
│   └── 3.3 Conversations/ # AI conversation logs
├── 4. Archive/            # Retired/completed items
├── 5. Blog/               # Blog posts
│   └── posts/YYYY/
└── _scripts/              # Utility scripts
```

### Where notes go

| Note type | Folder | Tags required |
|-----------|--------|---------------|
| Topic/knowledge note | `1. Notes/` | `topic/...` |
| Source (book, article) | `1. Notes/` | `source`, `topic/...` |
| Atomic (single idea) | `1. Notes/` | `atomic`, `topic/...` |
| Person note | `1. Notes/` | `person/work`, `person/friend`, or `person/family` |
| Idea | `1. Notes/` | `extra/idea`, `topic/...`, `area/...` |
| Daily journal | `2. Time/2.2 Daily/` | `time/daily` |
| Weekly review | `2. Time/2.1 Weekly/` | `time/weekly` |
| Meeting | `2. Time/2.3 Meetings/` | `time/meeting`, `area/...` |
| Blog post | `5. Blog/posts/YYYY/` | `area/blog`, `topic/...` |
| Completed/inactive | `4. Archive/` | (keep original tags) |

---

## Tag System Reference

This is the vault's official tagging system. **Follow this exactly when creating or editing notes.**

### Tag Categories

**`#time/...`** — Notes tied to a specific point in time. Records of events.
- `time/daily` — Daily journal entries
- `time/weekly` — Weekly reviews
- `time/meeting` — Meeting notes
- `time/goal` — Goal tracking

**`#area/...`** — Which domain/responsibility in the user's life. "Which hat am I wearing?"
- `area/work` — Professional/job contexts
- `area/personal` — Personal life
- `area/learning` — Educational contexts
- `area/health` — Health & fitness
- `area/friday` — Friday AI assistant
- `area/blog` — Blog-related work
- `area/finances` — Financial contexts

**`#topic/...`** — What the note is *about*. Subject matter classification.
- `topic/tech/programming` — Programming languages & concepts
- `topic/tech/infrastructure` — Infrastructure & DevOps
- `topic/tech/databases` — Database systems
- `topic/tech/framework` — Web/application frameworks
- `topic/tech/ia` — AI/ML topics
- `topic/tech/linux` — Linux systems
- `topic/tech/algorithms` — Algorithms & data structures
- `topic/games/...` — Gaming (league-of-legends, magic, etc.)
- `topic/work/acme-corp` — Work-specific topics
- `topic/note-taking` — Note-taking systems
- `topic/productivity` — Productivity
- `topic/therapy` — Mental health
- And many more — use existing topic tags when possible, create new ones when needed.

**`#person/...`** — Social context. Used on person notes in `1. Notes/`.
- `person/work` — Professional relationships
- `person/friend` — Friendships
- `person/family` — Family members
- `person/me` — Self-reflection

**`#project/...`** — Groups notes related to a specific multi-step endeavor.
- `project/homelab`, `project/friday`, `project/kairos`, etc.

**`#source`** — Note content comes from an external source (book, article, video).
- Can add `source/book` for books specifically.

**`#atomic`** — Small, self-contained, reusable knowledge unit. A "knowledge brick."

**`#extra/...`** — Supplementary materials.
- `extra/template` — Template notes (never use this on real notes)
- `extra/dashboard` — Dataview dashboards
- `extra/to-read` — Reading list items
- `extra/idea` — Brainstorm ideas
- `extra/ai-conversation` — AI conversation logs

### How to Choose Between `#area` and `#topic`

This is a critical distinction. The purpose of the note determines which tag is needed:

| If the note is primarily... | `#area` tag is... | `#topic` tag is... |
|:---|:---|:---|
| **A logbook** (meetings, goals, plans, actions) | **Required** | Optional |
| **A library item** (ideas, summaries, concepts, knowledge) | Optional | **Required** |

**Rules:**
- **Action/responsibility notes** (projects, goals, meetings) → always need `#area`
- **Knowledge/library notes** (atomic, sources, topic explainers) → always need `#topic`
- **Atomic notes** and **Source notes** usually do NOT need `#area` — they're universal knowledge
- **Meeting notes** usually do NOT need `#topic` — they're event records
- Don't force a tag if it doesn't add clarity
- Combine multiple tags for rich context (a meeting can be `#time/meeting` + `#area/work` + `#project/contoso-deal`)

### The Power of Combining Tags

A single note should have multiple tags placing it at the intersection of contexts. Example — a client meeting note:
- `#time/meeting` (it was a meeting)
- `#area/work` (professional context)
- `#project/contoso-deal` (specific project)

This makes it appear in meeting dashboards, work dashboards, AND project dashboards automatically.

---

## Templates

Templates live in `/vault/3. Resources/3.2 Templates/`. When creating notes, follow the template structure but **always**:
- Remove `extra/template` from tags
- Remove the `id` field (deprecated)
- Replace `{{title}}` with the actual title using `[[Title]]` format
- Fill in the date as `YYYY-MM-DD`

### Available templates and when to use them

| Template | Use for | Key frontmatter |
|----------|---------|-----------------|
| `Note.md` | Topic/knowledge notes | `tags`, `aliases`, `related` |
| `Person.md` | Person notes | `tags`, `aliases`, `birthday`, `email`, `company`, `last_contacted` |
| `Meeting.md` | Meeting notes | `tags`, `date`, `attendees` |
| `Source.md` | Book/article summaries | `tags`, `author`, `rating`, `progress` |
| `Idea.md` | Brainstorm ideas | `tags`, `status: inbox` |
| `To Read.md` | Reading list items | `tags`, `status: to-read`, `link` |
| `Blog Post.md` | Blog posts | `tags`, `title`, `description`, `date`, `status: draft` |
| `Daily.md` | Daily journals (use journal skill) | `tags`, `date`, `day` |
| `Weekly.md` | Weekly reviews | `tags`, `week` |

---

## Operations

### Search
```bash
exec: grep -rli "search term" /vault/ --include="*.md" | head -20
```
For content search with context:
```bash
exec: grep -rn "search term" /vault/ --include="*.md" | head -30
```
For tag-based search:
```bash
exec: grep -rli "topic/programming" /vault/ --include="*.md"
```

### Read
```
read_file: /vault/1. Notes/Some Note.md
```

### Create
Use `write_file` to create a new note. Always:
1. Check if a similar note already exists first (search)
2. Use the appropriate template structure
3. Place in the correct folder
4. Include proper tags following the tag system above
5. **Run link discovery** (see below) to find and add connections
6. Use `aliases` in frontmatter for common short names

### Edit
Use `edit_file` to modify an existing note. Rules:
- Never overwrite existing content unless asked — append or insert
- Preserve existing frontmatter fields
- Preserve existing wikilinks and dataview queries
- When adding information, maintain the note's existing section structure
- **After every edit, check for new link opportunities** — does the new content mention concepts, people, or projects that exist as notes?

### Move
```bash
exec: mv "/vault/1. Notes/Old Location.md" "/vault/4. Archive/Old Location.md"
```
When archiving: keep original tags, just move the file.

---

## Link Discovery (CRITICAL)

**Links are the backbone of the vault.** Every note should be woven into the knowledge graph. When creating or editing ANY note, always perform link discovery.

### How to discover links

**Step 1 — Extract key concepts.** Read the note content and identify: people names, technologies, projects, topics, concepts, tools, companies.

**Step 2 — Search for matching notes.** For each concept, check if a note exists:
```bash
exec: find /vault/1.\ Notes/ /vault/0.\ Overview/ -iname "*concept*" -name "*.md" 2>/dev/null | head -10
```
Or search by content if the filename might differ:
```bash
exec: grep -rli "concept" /vault/1.\ Notes/ /vault/0.\ Overview/ --include="*.md" | head -10
```

**Step 3 — Add wikilinks.** For every match:
- In the note body, replace plain text mentions with `[[Note Title]]`
- In the `## Connections` or `## Related` section, add links with context:
  ```
  - **Related Topics:** [[Python]], [[Django]]
  - **Supporting Ideas:** [[Garbage Collector]]
  - **Relevant Projects:** [[Homelab]]
  ```

**Step 4 — Backlink.** If note A now links to note B, check if note B would benefit from a link back to note A. If yes, edit note B's Connections/Related section to add the reverse link.

### What to link

| When you see... | Link to... |
|----------------|-----------|
| A person's name | `[[Full Name]]` (person note) |
| A technology (Python, React, Kubernetes) | `[[Technology Note]]` if it exists |
| A project name | `[[Project Note]]` |
| A company | `[[Company Note]]` (e.g., `[[Acme Corp]]`) |
| A concept from another note | `[[Concept Note]]` |
| A related meeting | `[[Meeting Title]]` |
| A book or source | `[[Source Title]]` |

### When to link

- **Creating a note** — always search for 3-5 linkable concepts before writing
- **Editing a note** — check if new content introduces linkable concepts
- **After a meeting** — link attendees, projects, and topics mentioned
- **When the user mentions a topic** — proactively suggest: "I see you have a note on [[X]], should I link it?"

---

## Navigating the Knowledge Graph

Friday can traverse the vault's link structure to build deep context on any topic. This is how to "unwrap" a subject.

### Following links (depth-first exploration)

When the user asks about a topic or you need to understand context:

**Step 1 — Find the entry point.** Search for the main note on the topic.

**Step 2 — Read it and extract outgoing links.** Every `[[Wikilink]]` in the note is a connection to explore.
```bash
exec: grep -oP '\[\[([^\]|]+)' "/vault/1. Notes/Topic.md" | sed 's/\[\[//' | sort -u
```
This extracts all wikilinks from a note.

**Step 3 — Follow relevant links.** Read the linked notes to build deeper understanding. Each linked note will have its own links — follow the ones relevant to the question.

**Step 4 — Find backlinks.** Discover what OTHER notes link TO this note (reverse connections):
```bash
exec: grep -rli "\[\[Topic Title\]\]" /vault/ --include="*.md" | head -20
```
Backlinks reveal context the original note doesn't know about — meetings where it was discussed, people connected to it, projects that use it.

### Example: "Tell me everything about Kubernetes in my vault"

1. `find /vault/ -iname "*kubernetes*" -name "*.md"` → find the main note
2. `read_file` the note → extract content + outgoing links (e.g., `[[Homelab]]`, `[[Docker]]`)
3. `grep -rli "\[\[Kubernetes\]\]" /vault/` → find backlinks (meetings, daily notes, project notes that mention it)
4. Read the most relevant backlinks for additional context
5. Synthesize everything into a comprehensive answer

### Example: "How does X relate to Y?"

1. Read note X → extract its links
2. Read note Y → extract its links
3. Find shared links (notes that both X and Y link to)
4. Find if X links to Y or Y links to X (direct connection)
5. `grep -rli "\[\[X\]\]" /vault/ --include="*.md"` + `grep -rli "\[\[Y\]\]" /vault/ --include="*.md"` → find notes that mention both
6. Explain the connection path

### Traversal rules

- **Go wide first, then deep.** Start by listing all links from the entry point. Then follow the most relevant 2-3.
- **Max depth: 3 hops.** Don't follow links more than 3 levels deep unless the user asks for exhaustive research.
- **Backlinks are gold.** They reveal connections the note's author didn't explicitly write. Always check backlinks.
- **Summarize, don't dump.** When presenting findings, synthesize the information naturally. Don't list raw file contents.
- **Offer to go deeper.** After presenting findings, offer: "I also found links to [[X]] and [[Y]] — want me to explore those?"

---

## Frontmatter Conventions

**Always present:**
- `tags:` — List format (never inline `[...]` format)
- `date:` — ISO format `YYYY-MM-DD`

**Common optional fields:**
- `aliases:` — Alternative names (list format). Always include first name for person notes.
- `language:` — `english` or `portuguese`
- `related: []` — Related note links

**Never include:**
- `id:` — Deprecated, do not add to new notes
- `extra/template` tag — Only for actual templates

**Person-specific fields:**
- `birthday:`, `email:`, `phone:`, `twitter:`, `github:`, `company:`, `last_contacted:`, `album:`

**Source-specific fields:**
- `author:`, `rating:`, `progress:`, `started:`, `finished:`, `link:`, `source_type:`

---

## Rules

- **The user's name is defined in USER.md.** References to "me", "I", "my" = the user.
- Always search before creating — avoid duplicate notes.
- Use wikilinks `[[Name]]` for all cross-references. Never use plain text for note/person names.
- Person references MUST always be "First Last" format — never first name only.
- File names use natural casing with spaces (e.g., `Sorting Algorithms.md`, not `sorting-algorithms.md`).
- All notes must be written in English.
- When unsure about folder placement, default to `1. Notes/`.
- When unsure about tags, refer to the tag system reference above.
- Tag for clarity, not for completion — if a tag doesn't add value, skip it.
- Preserve dataview queries in existing notes — never delete or modify them.
