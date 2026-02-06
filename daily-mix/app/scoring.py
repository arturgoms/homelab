import random
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def recency_score(last_played_iso: Optional[str], decay_days: int = 90) -> float:
    """
    Score based on how recently a song was played.
    Returns 1.0 for today, linearly decays to 0.0 over decay_days.
    Returns 0.0 if never played.
    """
    if not last_played_iso:
        return 0.0

    try:
        last_played = datetime.fromisoformat(last_played_iso.replace("Z", "+00:00"))
        now = datetime.now(last_played.tzinfo) if last_played.tzinfo else datetime.now()
        days_ago = (now - last_played).days
        if days_ago < 0:
            return 1.0
        if days_ago >= decay_days:
            return 0.0
        return 1.0 - (days_ago / decay_days)
    except (ValueError, TypeError):
        return 0.0


def build_genre_affinity(all_songs: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Build genre affinity map: total play counts per genre, normalized 0-1.
    The genre with the most plays gets 1.0, others are proportional.
    """
    genre_plays: Dict[str, int] = defaultdict(int)

    for song in all_songs:
        genre = song.get("genre", "").strip()
        if not genre:
            continue
        play_count = song.get("playCount", 0)
        genre_plays[genre] += play_count

    if not genre_plays:
        return {}

    max_plays = max(genre_plays.values())
    if max_plays == 0:
        return {g: 0.0 for g in genre_plays}

    return {genre: plays / max_plays for genre, plays in genre_plays.items()}


def normalize_values(values: List[float]) -> List[float]:
    """Normalize a list of values to 0-1 range."""
    if not values:
        return values
    max_val = max(values)
    if max_val == 0:
        return [0.0] * len(values)
    return [v / max_val for v in values]


class SongScorer:
    """Computes composite 0.0-1.0 scores per song using multiple signals."""

    # Weight profiles per playlist type
    PROFILES = {
        "for_you": {
            "play_count": 0.35,
            "starred": 0.25,
            "recency": 0.25,
            "genre_affinity": 0.15,
        },
        "discover": {
            "play_count": 0.05,  # inverted: low plays = high score
            "starred": 0.20,
            "recency": 0.05,
            "genre_affinity": 0.20,
            "lastfm_popularity": 0.50,
        },
    }

    def __init__(self, all_songs: List[Dict[str, Any]], recency_decay_days: int = 90, jitter: float = 0.10):
        self.recency_decay_days = recency_decay_days
        self.jitter = jitter
        self.genre_affinity = build_genre_affinity(all_songs)
        # Pre-compute max play count for normalization
        self._max_play_count = max((s.get("playCount", 0) for s in all_songs), default=1) or 1

    def score_song(self, song: Dict[str, Any], profile: str = "for_you",
                   lastfm_popularity: float = 0.0) -> float:
        """
        Compute composite score for a single song.

        Args:
            song: Song dict from Navidrome API
            profile: Scoring profile ("for_you" or "discover")
            lastfm_popularity: Normalized 0-1 Last.fm popularity (for discover)

        Returns:
            Score between 0.0 and 1.0
        """
        weights = self.PROFILES.get(profile, self.PROFILES["for_you"])
        score = 0.0

        # Play count component
        play_count = song.get("playCount", 0)
        normalized_plays = min(play_count / self._max_play_count, 1.0)

        if profile == "discover":
            # Inverted: low plays = high score
            score += weights["play_count"] * (1.0 - normalized_plays)
        else:
            score += weights["play_count"] * normalized_plays

        # Starred component
        starred = 1.0 if song.get("starred") else 0.0
        score += weights["starred"] * starred

        # Recency component
        last_played = song.get("played")
        rec_score = recency_score(last_played, self.recency_decay_days)
        score += weights["recency"] * rec_score

        # Genre affinity component
        genre = song.get("genre", "").strip()
        genre_score = self.genre_affinity.get(genre, 0.0)
        score += weights["genre_affinity"] * genre_score

        # Last.fm popularity (discover only)
        if "lastfm_popularity" in weights:
            score += weights["lastfm_popularity"] * lastfm_popularity

        # Add random jitter for variety
        jitter_amount = random.uniform(-self.jitter, self.jitter)
        score = max(0.0, min(1.0, score + jitter_amount))

        return score

    def score_songs(self, songs: List[Dict[str, Any]], profile: str = "for_you",
                    lastfm_popularities: Optional[Dict[str, float]] = None) -> List[tuple]:
        """
        Score and rank a list of songs.

        Args:
            songs: List of song dicts
            profile: Scoring profile
            lastfm_popularities: Optional dict of song_id -> normalized popularity

        Returns:
            List of (song, score) tuples sorted by score descending
        """
        if lastfm_popularities is None:
            lastfm_popularities = {}

        scored = []
        for song in songs:
            song_id = song.get("id", "")
            popularity = lastfm_popularities.get(song_id, 0.0)
            score = self.score_song(song, profile=profile, lastfm_popularity=popularity)
            scored.append((song, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
