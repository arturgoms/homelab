import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set
import logging

logger = logging.getLogger(__name__)


class PlaylistHistory:
    """Tracks song usage per playlist to enforce cooldown periods."""

    def __init__(self, history_file: str, cooldown_days: int = 7):
        self.history_file = history_file
        self.cooldown_days = cooldown_days
        self._data: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self):
        """Load history from JSON file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded playlist history from {self.history_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load history file, starting fresh: {e}")
                self._data = {}
        else:
            logger.info("No history file found, starting fresh")
            self._data = {}

    def _save(self):
        """Save history to JSON file."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        try:
            with open(self.history_file, "w") as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save history file: {e}")

    def is_on_cooldown(self, song_id: str, playlist_name: str) -> bool:
        """Check if song was used in this playlist within cooldown_days."""
        playlist_data = self._data.get(playlist_name, {})
        last_used = playlist_data.get(song_id)
        if not last_used:
            return False

        try:
            last_date = datetime.fromisoformat(last_used).date()
            cutoff = datetime.now().date() - timedelta(days=self.cooldown_days)
            return last_date > cutoff
        except ValueError:
            return False

    def get_cooldown_song_ids(self, playlist_name: str) -> Set[str]:
        """Get all song IDs currently on cooldown for a playlist."""
        result = set()
        playlist_data = self._data.get(playlist_name, {})
        cutoff = datetime.now().date() - timedelta(days=self.cooldown_days)

        for song_id, date_str in playlist_data.items():
            try:
                last_date = datetime.fromisoformat(date_str).date()
                if last_date > cutoff:
                    result.add(song_id)
            except ValueError:
                continue

        return result

    def record_playlist(self, playlist_name: str, song_ids: List[str]):
        """Record that these songs were used today in this playlist."""
        if playlist_name not in self._data:
            self._data[playlist_name] = {}

        today = datetime.now().date().isoformat()
        for song_id in song_ids:
            self._data[playlist_name][song_id] = today

        self.cleanup_old_entries()
        self._save()
        logger.info(f"Recorded {len(song_ids)} songs for '{playlist_name}' in history")

    def cleanup_old_entries(self):
        """Remove entries older than cooldown_days to keep file small."""
        cutoff = datetime.now().date() - timedelta(days=self.cooldown_days)

        for playlist_name in list(self._data.keys()):
            entries = self._data[playlist_name]
            self._data[playlist_name] = {
                song_id: date_str
                for song_id, date_str in entries.items()
                if self._is_recent(date_str, cutoff)
            }
            # Remove empty playlists
            if not self._data[playlist_name]:
                del self._data[playlist_name]

    @staticmethod
    def _is_recent(date_str: str, cutoff) -> bool:
        """Check if a date string is more recent than the cutoff."""
        try:
            return datetime.fromisoformat(date_str).date() > cutoff
        except ValueError:
            return False

    def get_stats(self) -> Dict[str, int]:
        """Get cooldown stats per playlist."""
        stats = {}
        for playlist_name, entries in self._data.items():
            cooldown_count = sum(
                1 for song_id in entries
                if self.is_on_cooldown(song_id, playlist_name)
            )
            stats[playlist_name] = cooldown_count
        return stats
