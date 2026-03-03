---
name: blog
description: Create and publish blog posts on arturgomes.com
---

# Blog Skill

## When the user asks to write a blog post, follow these steps IN ORDER:

**Step 1** — Search the vault for existing notes on the topic:
```
exec: grep -rli "topic keyword" /vault/ --include="*.md" | head -10
```
Read any matches to understand the user's existing take.

**Step 2** — Ask the user:
- What's the main point or angle?
- Any specific structure?
- Technical or general audience?

**Step 3** — Create the draft using `write_file`. The path MUST be:
```
/blog/posts/YYYY/<lowercase-words-separated-by-dashes>.md
```

The frontmatter MUST look **exactly** like this (note the double quotes):
```
---
title: "Short Title"
description: "A one-line summary"
date: YYYY-MM-DD
status: draft
tags:
  - area/blog
  - topic/something
---
```

**Frontmatter rules (CRITICAL — broken YAML kills the entire blog build):**
- `title` MUST be 3–4 words max, wrapped in double quotes
- `description` MUST be wrapped in double quotes
- Do NOT add `author` or any extra fields
- Do NOT use `tags: [...]` inline format
- Do NOT use any path other than `/blog/posts/YYYY/`

**Step 4** — Tell the user the file was created and offer to review/edit it.

**Step 5** — Only when the user says "publish", do THREE things:

1. Use `edit_file` to change `status: draft` to `status: published`.

2. Use `edit_file` to append the new post to `/blog/posts/YYYY/index.md` (the year index). Add a line at the end:
```
- [[slug-name|Post Title]] — Mon DD
```

3. Use `edit_file` to append the same line to `/blog/posts/index.md` (the main index), under the `## [YYYY]` section for the current year.

Example line: `- [[file-over-app-philosophy|File Over App]] — Mar 02`

The slug is the filename without `.md`. The title matches the frontmatter title. The date is abbreviated month + day.

You MUST update BOTH index files. The blog auto-deploys in ~60 seconds after all edits.

## When the user asks to delete a blog post:

**IMPORTANT: All blog operations use `/blog/` (read-write). NEVER use `/vault/` — it is read-only.**

**Step 1** — List posts so the user can confirm which one:
```
exec: ls /blog/posts/YYYY/
```

**Step 2** — Ask the user to confirm the exact post to delete. NEVER delete without confirmation.

**Step 3** — Once confirmed, do THREE things:

1. Delete the post file (use `/blog/`, NOT `/vault/`):
```
exec: rm /blog/posts/YYYY/slug-name.md
```

2. Use `edit_file` to remove the post's line from `/blog/posts/YYYY/index.md` (the year index).

3. Use `edit_file` to remove the post's line from `/blog/posts/index.md` (the main index).

The watcher will detect the deletion and rebuild the blog automatically.

---

## Cross-linking other posts

When writing a post, check if any existing posts are related. To find them:
```
exec: ls /blog/posts/YYYY/
```
Read any relevant ones with `read_file` to confirm they're related, then link to them using wikilinks:
```
[[slug-name|Display Title]]
```
Example: `[[obsidian-blog-sync|Publishing Posts from Obsidian]]`

The slug is the filename without `.md`. Place links naturally in the text where they're relevant — don't dump a list of links at the end.

## Writing Style (match existing posts)

- First person, conversational but technical
- `##` for section headers, `---` between major sections
- Code blocks with language tags
- Wikilinks `[[slug|Display Title]]` for cross-references to other posts
- Practical: what, why, how, gotchas

## Rules

- ALWAYS start with `status: draft`
- ALWAYS include `area/blog` tag
- NEVER publish without the user saying so
- Titles: 3–4 words max, in double quotes
- File names: all lowercase, words separated by `-`
- Live URL will be: `arturgomes.com/posts/YYYY/slug-name`
- YYYY = current year. Always use today's date for new posts.
