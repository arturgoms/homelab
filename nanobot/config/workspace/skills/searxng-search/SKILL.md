---
name: searxng-search
description: Search web using SearXNG instance, substitute for web search tool.
---

# SearXNG Search Skill

**IMPORTANT: Use this instead of the built-in web_search tool. Always. No configuration needed — the URL is already set in the script.**

## How to Use

Use `exec` to run:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "your search query"
```

That's it. No URL needed. No API key needed. Just the query.

### Optional Parameters
- `--count N`: Number of results (default: 5)
- `--time_range day|week|month|year`: Filter by time
- `--language pt|en`: Language code

### More Examples
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "próximo jogo do Cruzeiro"
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "AI news" --count 3 --time_range week
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "rust async tutorial" --language en
```

### Output
JSON array with: `title`, `url`, `content`, `score`, `publishedDate`.

## Rules

1. **Never use the built-in web_search tool** — it requires a Brave API key we don't have.
2. **Never ask for a URL** — SearXNG is pre-configured inside the script.
3. Just run the exec command above with the query. Done.
