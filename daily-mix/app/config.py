import os
from typing import Optional, List

class Config:
    """Configuration loaded from environment variables."""

    # Navidrome
    NAVIDROME_URL: str = os.getenv("NAVIDROME_URL", "")
    NAVIDROME_USER: str = os.getenv("NAVIDROME_USER", "")
    NAVIDROME_PASS: str = os.getenv("NAVIDROME_PASS", "")

    # Last.fm
    LASTFM_API_KEY: str = os.getenv("LASTFM_API_KEY", "")

    # LLM (vLLM with OpenAI-compatible API)
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://192.168.1.18:8080")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "default")

    # Playlist Configuration
    PLAYLIST_SIZE: int = int(os.getenv("PLAYLIST_SIZE", "50"))
    PLAYLIST_FOR_YOU_NAME: str = os.getenv("PLAYLIST_FOR_YOU_NAME", "Daily Mix - For You")
    PLAYLIST_DISCOVER_NAME: str = os.getenv("PLAYLIST_DISCOVER_NAME", "Daily Mix - Discover")

    # Mood playlist names (comma-separated moods to generate playlists for)
    MOOD_PLAYLISTS: List[str] = [
        m.strip() for m in os.getenv("MOOD_PLAYLISTS", "energetic,chill").split(",")
        if m.strip()
    ]
    PLAYLIST_MOOD_PREFIX: str = os.getenv("PLAYLIST_MOOD_PREFIX", "Daily Mix -")

    # Scheduler Configuration
    SCHEDULE_CRON: str = os.getenv("SCHEDULE_CRON", "0 6 * * *")

    # Algorithm Tuning
    MIN_PLAY_COUNT_FOR_TOP_ARTIST: int = int(os.getenv("MIN_PLAY_COUNT_FOR_TOP_ARTIST", "5"))
    MAX_PLAY_COUNT_FOR_DISCOVER: int = int(os.getenv("MAX_PLAY_COUNT_FOR_DISCOVER", "3"))
    MAX_SONGS_PER_ALBUM: int = int(os.getenv("MAX_SONGS_PER_ALBUM", "3"))
    SIMILAR_ARTIST_DEPTH: int = int(os.getenv("SIMILAR_ARTIST_DEPTH", "3"))
    LASTFM_MIN_LISTENERS: int = int(os.getenv("LASTFM_MIN_LISTENERS", "1000"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        required = [
            cls.NAVIDROME_URL,
            cls.NAVIDROME_USER,
            cls.NAVIDROME_PASS,
            cls.LASTFM_API_KEY,
        ]
        return all(required)


config = Config()
