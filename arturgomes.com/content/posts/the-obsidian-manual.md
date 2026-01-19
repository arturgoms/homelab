---
title: "The Obsidian Manual: How I Organize My Notes"
description: "My complete operating manual for organizing thoughts, projects, and knowledge with Obsidian"
date: 2026-01-19
tags:
  - productivity
  - obsidian
  - note-taking
  - knowledge-management
---

After trying every note-taking methodology out there, I developed my own system in Obsidian. This is my complete operating manual for organizing thoughts, projects, and knowledge with clarity and consistency.

## Core Philosophy

This system is built on a simple principle: **folders define the state of a note, while tags define its context.**

I use a minimal folder structure to separate broad categories (active notes vs. archived notes) and rely on a rich tagging system to dynamically connect and view information. Navigation happens through custom dashboards, not by clicking through folders.

## Why Other Systems Failed Me

There are many ways to organize files for productivity. After experimenting with most of them, I noticed they all sit somewhere on a graph with links, actions, folders, and knowledge as the axes.

### The Problem with Pure Zettelkasten

Link-based structures like Zettelkasten tend to become unorganized. You end up relying heavily on "Maps of Content" which are just another unorganized note with lots of links. You create a misconception that you have a note with many connected thoughts, when really it's just an umbrella note trying to catch whatever comes around that topic - often too broad or not broad enough.

### The Problem with Deep Folder Structures

Folders can also be a trap. You create more and more folders until you face a note that could live in two or more places. Then your system breaks. Imagine looking for a note, finally finding the folder that fits the topic, only to discover your note was somewhere else entirely.

### The Problem with P.A.R.A

P.A.R.A is good, but moving things around constantly means you can lose track of notes. The constant reorganization becomes overhead.

### My Solution

Folders should be **namespaces** - as broad as possible. An inbox folder groups things you're working on. An archive stores what's done. That's mostly it. The real organization happens through tags.

## The Folder Structure

Each folder has a distinct purpose. Numerical prefixes maintain logical order.

```
0. Overview/
   ├── 0.1 Inbox          # New notes before processing
   ├── 0.2 Dashboards     # Dynamic views of your data
   └── 0.3 Maps of Content # Curated topic guides

1. Notes/                  # Permanent knowledge library

2. Time/
   ├── 2.1 Weekly         # Weekly reviews
   ├── 2.2 Daily          # Journal entries
   └── 2.3 Meetings       # Meeting notes

3. Resources/
   ├── 3.1 Templates      # Reusable note structures
   └── 3.2 Attachments    # Images, PDFs, files

4. Archive/
   ├── 4.1 Projects       # Completed projects
   └── 4.2 Time           # Past time-based notes
```

### Folder Purposes

**0. Overview** - The control center and entry point for your vault.

**1. Notes** - The permanent library for processed, timeless knowledge. Move refined notes from the Inbox here. This is home for atomic notes (single ideas), topic notes (deep dives), and evergreen content.

**2. Time** - A flat folder for all active, time-sensitive notes. Contents are surfaced through Dashboards, not browsed directly.

**3. Resources** - Supplementary materials that support your knowledge work. Templates and attachments live here, keeping main folders clean.

**4. Archive** - Cold storage for completed or inactive items. Keeps your active workspace focused on what's relevant now.

## The Tagging System

Tags are the core of this organizational system. They create multiple dimensions of context for any single note.

### How to Choose the Right Tag

When creating or processing a note, ask yourself:

1. **Is this note tied to a specific date or event?**
   → Use `#time/...` (daily, meeting, goal, weekly)

2. **Which part of my life does this belong to?**
   → Use `#area/...` (work, personal, health, learning)

3. **Is this part of a specific project with a clear goal?**
   → Use `#project/...` (website-redesign, q3-launch)

4. **What is the subject matter?**
   → Use `#topic/...` (psychology, programming, finance)

5. **Does this involve interaction with people?**
   → Use `#person/...` (client, family, colleague)

6. **Is this a single, self-contained idea?**
   → Add `#atomic`

A single note often has multiple tags. A meeting note might be tagged `#time/meeting`, `#area/work`, and `#project/q3-launch`.

### Primary Tag Categories

**`#time/...`** - For notes in the Time folder
- `#time/daily` - Journal entries
- `#time/weekly` - Weekly reviews
- `#time/meeting` - Meeting notes
- `#time/goal` - Goals with deadlines

**`#area/...`** - High-level life domains
- `#area/work`
- `#area/personal`
- `#area/learning`
- `#area/health`

**`#project/[name]`** - Groups all notes for a specific endeavor

**`#topic/[name]`** - Subject matter classification

**`#source`** - Notes summarizing external content (books, articles)

**`#atomic`** - Single, self-contained ideas that can be linked from many notes

## Understanding `#area` vs `#topic`

This is the most nuanced distinction. Use the **"Hat vs. Library"** mental model:

- **`#area` is the hat you're wearing.** It represents a personal domain or role in *your life* (work, health, family).

- **`#topic` is the book you're reading.** It represents a universal subject of knowledge (history, marketing, psychology).

**Example:** A note about implementing a marketing strategy at your job gets:
- `#area/work` - because that's the hat you're wearing
- `#topic/marketing` - because that's the subject matter

## The Workflow

### 1. Capture

All new thoughts start in `0.1 Inbox`. Quick, low-friction.

**Example:** After a call, create `follow up with Contoso Corp` in the Inbox.

### 2. Process

Regularly review your Inbox. Refine notes, apply tags, move to permanent homes.

**Example:** The note becomes `Meeting - Contoso Corp Intro Call 2025-05-27`, tagged `#time/meeting`, `#project/contoso-deal`, `#person/client`, `#area/work`. Moved to `2. Time`.

### 3. View & Navigate

Start sessions from a dashboard in `0. Overview`, not the file explorer.

**Example:** Open your "Work Dashboard" which filters for `#area/work` and automatically shows all relevant notes.

### 4. Archive

When projects complete, move notes to `4. Archive` to keep your workspace clean.

**Example:** Deal is closed. Move all `#project/contoso-deal` notes to `4. Archive/4.1 Projects/Contoso Deal`.

## When to Create a Dashboard

**If you repeatedly search for the same type of information, build a dashboard for it.**

Good candidates:
- **Periodic Reviews** - Gather all `#time/daily` notes from a month
- **Project Tracking** - Display every note for `#project/alpha`
- **Context Switching** - Show only `#area/work` notes
- **Relationship Management** - List recent `#person/client` notes

## Key Takeaways

1. **Folders = State** (inbox, active, archived)
2. **Tags = Context** (area, topic, project, time)
3. **Dashboards = Navigation** (don't browse folders)
4. **Inbox = Capture first, organize later**
5. **Archive = Nothing is deleted, just stored**

The goal isn't a perfect system. It's a system that gets out of your way and helps you think.
