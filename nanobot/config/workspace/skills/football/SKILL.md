---
name: football
description: Query football/soccer data — fixtures, scores, standings, teams.
---

# Football Skill

Query live football data using football-data.org. Use this for ANY football/soccer question.

**Rate limit: 10 requests/minute. Be efficient.**

## Commands

All commands use `exec`:

### Next matches for a team (look ahead 30 days)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py matches --team "cruzeiro" --days 30 --status SCHEDULED
```

### Recent results for a team
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py matches --team "cruzeiro" --status FINISHED
```

### All matches for a team (upcoming + past)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py matches --team "flamengo"
```

### If you already know the team ID (saves an API call)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py matches --team "cruzeiro" --team-id 1783
```

### Today's matches (all or by competition)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py today
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py today --competition brasileirao
```

### Live scores
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py live
```

### League standings
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py standings --competition brasileirao
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py standings --competition "premier league"
```

### Search for a team (finds ID across free competitions)
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py search-team "cruzeiro"
```

### List available competitions
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/football_api.py competitions
```

## Free Tier Competitions

| Name | Code |
|------|------|
| Brasileirão Série A | BSA |
| Premier League | PL |
| La Liga | PD |
| Bundesliga | BL1 |
| Serie A (Italy) | SA |
| Ligue 1 | FL1 |
| Eredivisie | DED |
| Primeira Liga | PPL |
| Championship | ELC |
| Champions League | CL |
| World Cup | WC |
| Euro | EC |

## Competitions NOT covered (use SearXNG instead)

State championships (estaduais) like Campeonato Mineiro, Carioca, Paulista, Gaúcho, etc. are **not** in this API.

For those, use the searxng-search skill:
```bash
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "próximo jogo cruzeiro campeonato mineiro 2026"
exec: python3 /root/.nanobot/workspace/skill-tools/searxng_search.py "tabela campeonato mineiro 2026"
```

Also use SearXNG for Copa do Brasil, Libertadores, Sulamericana, and any other competition not in the free tier list above.

## Rules

1. `search-team` costs multiple API calls (searches across competitions) — use it once, then remember the team ID
2. Interpret results naturally: "Cruzeiro plays Flamengo on Saturday at 4pm at the Mineirão"
3. Convert UTC dates to the user's timezone (America/Sao_Paulo, UTC-3)
4. For "when is the next game?", use `matches --team X --days 30 --status SCHEDULED`
5. For standings, just use the competition code directly — no search needed
6. If the question is about a state championship or unlisted competition, go straight to SearXNG — don't waste an API call
