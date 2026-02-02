# Daily Mix

Automatic playlist generator for Navidrome that creates personalized daily playlists based on your listening habits and Last.fm popularity data.

## Playlists

### Daily Mix - For You
Recommendations based on artists similar to your most-played music.

**Algorithm:**
1. Get your top artists from Navidrome (artists with 5+ plays)
2. Find similar artists via Last.fm API
3. Match similar artists to songs in your library
4. Select tracks you haven't overplayed

### Daily Mix - Discover
Popular songs from your library that you haven't explored yet.

**Algorithm:**
1. Get all artists in your library
2. Query Last.fm for each artist's most popular tracks
3. Rank by external popularity (listeners on Last.fm)
4. Filter to songs with low local play count (<3 plays)

## Configuration

All configuration is done via environment variables in `.env`:

```env
# Navidrome Connection
NAVIDROME_URL=https://music.example.com
NAVIDROME_USER=username
NAVIDROME_PASS=password

# Last.fm API (public API for popularity data only)
LASTFM_API_KEY=your_api_key

# Playlist Configuration
PLAYLIST_SIZE=50
PLAYLIST_FOR_YOU_NAME=Daily Mix - For You
PLAYLIST_DISCOVER_NAME=Daily Mix - Discover

# Scheduler (cron format: minute hour day month weekday)
SCHEDULE_CRON=0 6 * * *

# Algorithm Tuning
MIN_PLAY_COUNT_FOR_TOP_ARTIST=5   # Min plays to consider artist "top"
MAX_PLAY_COUNT_FOR_DISCOVER=3     # Max local plays for Discover songs
SIMILAR_ARTIST_DEPTH=3            # Levels deep for similar artist search
LASTFM_MIN_LISTENERS=1000         # Min Last.fm listeners for popularity

# Logging
LOG_LEVEL=INFO
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/status` | GET | Shows config and next scheduled run |
| `/generate` | POST | Manually trigger playlist generation |

## Running

```bash
docker compose up -d
```

Access at `http://localhost:5050`

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Navidrome     │◄────│   Daily Mix     │────►│    Last.fm      │
│  (your library) │     │    Service      │     │  (public API)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

- **Navidrome**: Source of your music library and play counts (Subsonic API)
- **Last.fm**: Public API for artist similarity and track popularity data
- **Daily Mix**: Combines both to generate personalized playlists

Important: Only songs from your library are used. Last.fm provides metadata only.
