# Daily Mix

Automatic playlist generator for [Navidrome](https://www.navidrome.org/). Generates 4 personalized playlists daily using your listening history, Last.fm popularity data, and an LLM for mood classification.

## Playlists

| Playlist | What it is |
|----------|------------|
| **For You** | The best songs from artists you love, ranked by Last.fm popularity |
| **Discover** | Popular but unplayed/underplayed gems you haven't explored yet |
| **Mood A** | LLM-analyzed mood playlist (e.g. "Brazilian Sunset") |
| **Mood B** | LLM-analyzed mood playlist (e.g. "Late Night Drive") |

Every song appears in exactly one playlist per run (cross-playlist deduplication). Songs that appeared in a playlist can't reappear in that same playlist for a configurable cooldown period (default 7 days), ensuring fresh content daily.

---

## How "For You" Works

The For You playlist answers: **"What are the best songs from the artists I care about most?"**

### Step 1: Artist Affinity Scoring

Every artist in the library gets an affinity score based on three signals:

```
artist_affinity = total_play_count + (starred_songs * 10) + (album_count * 5)
```

| Signal | Weight | Why |
|--------|--------|-----|
| Total plays across all songs | 1x per play | Core engagement signal |
| Number of starred/favorited songs | 10x per star | Explicit preference signal, worth more than passive plays |
| Number of albums in library | 5x per album | Having multiple albums means intentional collection |

Artists below `MIN_PLAY_COUNT_FOR_TOP_ARTIST` (default 5) are excluded. The top 25 artists are selected.

### Step 2: Proportional Slot Allocation

Playlist slots are distributed proportionally to each artist's affinity score, not a flat cap. This means your #1 artist gets more songs than your #15 artist.

```
target_slots = PLAYLIST_SIZE * 1.5    (overprovisioned to absorb filtering losses)
base_slots   = 1 per artist           (every artist gets at least 1 song)
remaining    = target_slots - 25

per_artist_extra = round((artist_affinity / total_affinity) * remaining)
per_artist_slots = 1 + per_artist_extra
```

The 1.5x overprovisioning is intentional. Downstream filters (cooldown, album cap, dedup) remove songs, so we start with ~75 candidates to reliably end up with 50.

**Example** from a real run with ~1380 songs:

| Artist | Affinity | Slots |
|--------|----------|-------|
| Linkin Park | 160 | 6 |
| AC/DC | 144 | 5 |
| Eminem | 119 | 4 |
| Charlie Brown Jr. | 85 | 3 |
| Stromae | 42 | 2 |
| Titãs | 30 | 1 |

### Step 3: Per-Artist Song Ranking

For each of the 25 artists, their songs are ranked by a composite score:

```
song_score = lastfm_popularity + starred_bonus + recency + jitter
```

| Component | Value | Description |
|-----------|-------|-------------|
| `lastfm_popularity` | 0.0 - 1.0 | `min(listeners / 1,000,000, 1.0)` from Last.fm top tracks |
| `starred_bonus` | 0.0 or 0.3 | +0.3 if the song is starred/favorited |
| `recency` | 0.0 - 0.15 | Linear decay: `recency_score(last_played) * 0.15`, where recency is 1.0 for today and decays to 0.0 over `RECENCY_DECAY_DAYS` (default 90) |
| `jitter` | -0.05 to +0.05 | Random noise so playlists aren't deterministic |

Songs not found in Last.fm's top tracks for the artist get a baseline of 0.1 for the popularity component.

The top N songs per artist are picked (where N = allocated slots), skipping:
- Songs on cooldown for this playlist
- Songs exceeding the per-album cap (`MAX_SONGS_PER_ALBUM`)
- Duplicate titles (normalized -- "Song (Remastered)" = "Song")

### Step 4: Spread and Trim

The final candidate list is deduplicated globally, then spread using a round-robin algorithm that avoids placing the same artist or album back-to-back. The list is trimmed to exactly `PLAYLIST_SIZE`.

---

## How "Discover" Works

The Discover playlist answers: **"What popular music in my library have I been overlooking?"**

### Step 1: Candidate Filtering

Only songs meeting ALL of these criteria enter the candidate pool:

- Play count <= `MAX_PLAY_COUNT_FOR_DISCOVER` (default 3)
- NOT starred AND played (starred+played = comfort music, not a discovery)
- NOT already used in the For You playlist (cross-playlist dedup)

### Step 2: Last.fm Popularity Lookup

For each candidate song, the system fetches Last.fm data:

1. **Track-level match**: If the song title matches one of the artist's top 100 tracks on Last.fm, use that track's listener count directly
2. **Artist-level fallback**: If no track match, use the artist's total listener count divided by 100 as an estimate
3. **Minimum threshold**: Songs below `LASTFM_MIN_LISTENERS` (default 1,000) are excluded entirely

### Step 3: Underrepresentation Boost

This is the key mechanism that prevents Discover from just being "songs by your most-collected artists that you haven't played yet."

Artists with fewer songs in your library get a **quadratic boost** to their popularity score, making their songs compete with heavy-hitter artists:

```
ratio = (artist_song_count - 1) / (max_artist_song_count - 1)
underrep_boost = 1.0 + 4.0 * ((1.0 - ratio) ^ 2)
boosted_popularity = min((listeners / max_listeners) * underrep_boost, 1.0)
```

| Artist's library size | Ratio | Boost multiplier |
|-----------------------|-------|-----------------|
| 1 song | 0.0 | **5.0x** |
| ~10% of max | ~0.1 | **4.24x** |
| ~25% of max | ~0.25 | **3.25x** |
| ~50% of max | ~0.5 | **2.0x** |
| ~75% of max | ~0.75 | **1.25x** |
| Max songs | 1.0 | **1.0x** |

The quadratic curve `(1-r)^2` is intentional: niche artists get a disproportionately large boost while well-represented artists stay roughly the same. Without this, artists like AC/DC (who may have 50+ songs in your library) would dominate Discover just because they have more low-play songs by volume.

### Step 4: Multi-Signal Scoring

After the underrepresentation boost is applied to Last.fm popularity, each song gets a composite score using the **discover** weight profile:

```
score = (play_count_inverted * 0.05)
      + (starred            * 0.20)
      + (recency            * 0.05)
      + (genre_affinity     * 0.20)
      + (lastfm_popularity  * 0.50)
      + jitter
```

| Component | Weight | Description |
|-----------|--------|-------------|
| `play_count` (inverted) | 0.05 | `1.0 - normalized_plays` -- fewer plays = higher score |
| `starred` | 0.20 | 1.0 if starred, else 0.0 -- starred-but-unplayed is a strong discovery signal |
| `recency` | 0.05 | Low weight -- recency matters less for discovery |
| `genre_affinity` | 0.20 | How much you listen to this genre overall (normalized 0-1 by total plays per genre) |
| `lastfm_popularity` | 0.50 | The boosted Last.fm popularity from Step 3 -- dominant signal |
| `jitter` | +-10% | Random noise for variety |

### Step 5: Filtering Pipeline

All scored candidates flow through the pipeline (no artificial top-N cutoff):

1. **Cooldown filter** -- remove songs used in this playlist within the last `COOLDOWN_DAYS`
2. **Deduplication** -- remove duplicate song IDs and normalized title matches (e.g. "Song" and "Song (Live)")
3. **Per-artist cap** -- max `MAX_SONGS_PER_ARTIST_DISCOVER` (default 2) songs per artist, much tighter than For You's cap to force maximum variety
4. **Artist spread** -- round-robin to avoid consecutive songs from the same artist
5. **Trim** -- take first `PLAYLIST_SIZE` songs

---

## How Mood Playlists Work

The mood playlists answer: **"What in my library fits a specific vibe?"**

Mood playlists require an LLM (`LLM_ENABLED=true`). Without one, only For You and Discover are generated.

### Mood Discovery (First Run)

On the first generation (or after a mood reset), the LLM analyzes your library to pick 2 mood categories that best represent your collection.

**Process:**
1. Sample 100 songs biased toward higher play counts (top 60 by plays + 40 random)
2. Send to LLM with genre and year metadata:
   ```
   - "Numb" by Linkin Park [Alternative Rock, 2003]
   - "Back in Black" by AC/DC [Hard Rock, 1980]
   ...
   ```
3. LLM responds with 2 specific mood categories (not generic ones like "happy" or "sad") and descriptions
4. Result is cached to `data/mood_config.json`

**Example output:**
```json
{
  "moods": ["Brazilian Sunset", "Late Night Drive"],
  "descriptions": {
    "Brazilian Sunset": "Warm, laid-back Brazilian and Latin vibes for golden hour",
    "Late Night Drive": "Dark, driving energy for midnight roads"
  }
}
```

### When Moods Change

Moods persist indefinitely once discovered. They only change when:

1. **Manual reset**: `POST /moods/reset` deletes `mood_config.json`, triggering re-discovery on the next generation
2. **File deletion**: Manually deleting `data/mood_config.json` from the host

Moods do NOT change automatically between runs. The same 2 categories are reused daily until explicitly reset.

### Song Classification

Once mood categories are determined, songs are classified into them:

1. **Exclude used songs** -- songs already in For You or Discover are removed from the pool
2. **Score and sample** -- 400 songs are sampled (200 top-scored by the For You profile + 200 random for diversity)
3. **LLM classification** -- songs are sent to the LLM in batches of 40 with genre/year metadata. The LLM assigns each song to exactly one mood category
4. **Per-mood filtering** -- for each mood playlist:
   - Cooldown filter
   - Title deduplication (global across both mood playlists)
   - Per-artist cap (`MAX_SONGS_PER_ARTIST`, default 4)
   - Artist spread
   - Trim to `PLAYLIST_SIZE`

A song can only appear in one mood playlist, enforced by global tracking across both mood playlists.

### LLM Playlist Descriptions

After each playlist is generated (all 4, not just moods), the LLM writes a 1-2 sentence evocative description of the playlist's vibe. This is set as the playlist comment in Navidrome via the Subsonic API.

---

## Song Cooldown System

The cooldown system ensures daily rotation. It tracks which songs appeared in which playlist and when.

**Storage**: `data/playlist_history.json`
```json
{
  "Daily Mix - For You": {
    "song_id_abc": "2026-02-06",
    "song_id_def": "2026-02-05"
  },
  "Daily Mix - Discover": { ... }
}
```

**Rules:**
- A song can't reappear in the **same** playlist for `COOLDOWN_DAYS` (default 7)
- A song CAN appear in different playlists on different days (but not the same run, due to cross-playlist dedup)
- Entries older than `COOLDOWN_DAYS` are automatically cleaned up on each run
- Data persists across container restarts via the `./data:/app/data` volume mount

---

## Global Filtering

These filters apply to all playlists before any scoring:

### Skit/Interlude Filtering
Songs with titles matching these patterns are excluded from the entire library:
- Words: `skit`, `interlude`, `intro`, `outro`, `intermission`
- Parenthetical: `(skit)`, `(interlude)`, `(intro)`, `(outro)`

### Artist Name Normalization
Multi-artist strings are normalized by extracting the primary artist:
- `"2Pac feat. Nate Dogg"` -> `"2pac"`
- `"Linkin Park & Jay-Z"` -> `"linkin park"`
- Splits on: `feat.`, `ft.`, `featuring`, `with`, `&`, `and`, `,`, `x`

This ensures per-artist caps and affinity scores count all variants together.

### Title Normalization
For deduplication, titles are normalized by stripping version indicators:
- `"Song (Remastered 2020)"` -> `"song"`
- `"Song [Live]"` -> `"song"`
- `"Song - Acoustic"` -> `"song"`

---

## Generation Order

Playlists are generated in a fixed order, and each step excludes songs already used:

```
1. For You      (picks first, gets the best songs from your top artists)
2. Discover     (excludes For You songs, surfaces underplayed gems)
3. Mood A       (excludes For You + Discover songs)
4. Mood B       (excludes For You + Discover + Mood A songs)
```

This priority order means For You gets first pick, Discover gets second pick, and mood playlists work with the remaining library.

---

## Configuration

All configuration is via environment variables (`.env` file).

### Required

| Variable | Description |
|----------|-------------|
| `NAVIDROME_URL` | Navidrome server URL |
| `NAVIDROME_USER` | Navidrome username |
| `NAVIDROME_PASS` | Navidrome password |
| `LASTFM_API_KEY` | Last.fm API key (public, no user auth needed) |

### Playlist Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYLIST_SIZE` | `50` | Songs per playlist |
| `PLAYLIST_FOR_YOU_NAME` | `Daily Mix - For You` | Name of the For You playlist in Navidrome |
| `PLAYLIST_DISCOVER_NAME` | `Daily Mix - Discover` | Name of the Discover playlist |
| `PLAYLIST_MOOD_PREFIX` | `Daily Mix -` | Prefix for mood playlist names |
| `SCHEDULE_CRON` | `0 6 * * *` | Cron schedule (default: 6 AM daily) |

### Algorithm Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `MIN_PLAY_COUNT_FOR_TOP_ARTIST` | `5` | Minimum affinity score for an artist to be considered for For You |
| `MAX_PLAY_COUNT_FOR_DISCOVER` | `3` | Maximum play count for a song to be considered a "discovery" |
| `MAX_SONGS_PER_ALBUM` | `3` | Max songs from the same album in For You |
| `MAX_SONGS_PER_ARTIST` | `4` | Per-artist cap for For You and mood playlists |
| `MAX_SONGS_PER_ARTIST_DISCOVER` | `2` | Per-artist cap for Discover (tighter for more variety) |
| `LASTFM_MIN_LISTENERS` | `1000` | Minimum Last.fm listeners for a song to appear in Discover |
| `COOLDOWN_DAYS` | `7` | Days before a song can reappear in the same playlist |
| `RECENCY_DECAY_DAYS` | `90` | Days over which the recency score decays from 1.0 to 0.0 |

### LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENABLED` | `false` | Enable LLM integration (mood playlists + descriptions) |
| `LLM_BASE_URL` | `http://192.168.1.18:8000` | vLLM server URL (OpenAI-compatible API) |
| `LLM_MODEL` | `default` | Model name (auto-detected from server if `default`) |
| `LLM_AUTO_MOODS` | `true` | Let LLM pick mood categories (vs manual `MOOD_PLAYLISTS`) |
| `LLM_PLAYLIST_DESCRIPTIONS` | `true` | Generate LLM descriptions for each playlist |
| `MOOD_PLAYLISTS` | `energetic,chill` | Manual mood categories (used when `LLM_AUTO_MOODS=false`) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check (for Docker) |
| `GET` | `/status` | Status, next run time, current moods, cooldown stats |
| `POST` | `/generate` | Trigger playlist generation manually |
| `POST` | `/moods/reset` | Delete cached moods, re-discover on next generation |

---

## Running

```bash
# Start
docker compose up -d

# View logs
docker compose logs -f

# Trigger manual generation
curl -X POST http://localhost:5050/generate

# Check status
curl http://localhost:5050/status

# Reset mood categories
curl -X POST http://localhost:5050/moods/reset

# Rebuild after code changes
docker compose build && docker compose up -d
```

## Architecture

```
app/
  main.py          FastAPI app, scheduler, endpoints
  config.py        Environment variable configuration
  navidrome.py     Navidrome Subsonic API client
  lastfm.py        Last.fm API client (popularity, artist info)
  llm.py           LLM client (mood discovery, classification, descriptions)
  playlist_gen.py  Core generation logic (For You, Discover, Mood)
  scoring.py       Multi-signal song scoring engine
  history.py       Song cooldown tracking (JSON persistence)

data/                         (persisted via Docker volume)
  playlist_history.json       Song cooldown records
  mood_config.json            Cached LLM mood categories
```
