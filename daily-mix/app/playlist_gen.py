import random
from typing import List, Dict, Any, Set
from collections import defaultdict
import logging

from .navidrome import NavidromeClient
from .lastfm import LastFMClient, extract_primary_artist
from .config import config

# Import LLM client conditionally
try:
    from .llm import LLMClient
except ImportError:
    LLMClient = None

logger = logging.getLogger(__name__)


def normalize_artist_name(artist: str) -> str:
    """Normalize artist name for grouping (extracts primary artist)."""
    primary, _ = extract_primary_artist(artist)
    return primary.lower().strip()


def normalize_song_title(title: str) -> str:
    """Normalize song title for deduplication (removes version indicators)."""
    import re
    # Remove common version indicators - order matters, more specific first
    patterns = [
        # Parenthetical versions
        r'\s*\(original[^)]*\)\s*',
        r'\s*\(live[^)]*\)\s*',
        r'\s*\(ao vivo[^)]*\)\s*',
        r'\s*\(acoustic[^)]*\)\s*',
        r'\s*\(unplugged[^)]*\)\s*',
        r'\s*\(demo[^)]*\)\s*',
        r'\s*\(remix[^)]*\)\s*',
        r'\s*\(remaster[^)]*\)\s*',
        r'\s*\(radio edit[^)]*\)\s*',
        r'\s*\(single[^)]*\)\s*',
        r'\s*\(album[^)]*\)\s*',
        r'\s*\(explicit[^)]*\)\s*',
        r'\s*\(clean[^)]*\)\s*',
        r'\s*\(edit[^)]*\)\s*',
        r'\s*\(extended[^)]*\)\s*',
        r'\s*\(instrumental[^)]*\)\s*',
        r'\s*\(cover[^)]*\)\s*',
        r'\s*\(version[^)]*\)\s*',
        r'\s*\(\d{4}[^)]*\)\s*',  # Year in parens like (2024 Remaster)
        # Bracketed versions
        r'\s*\[original[^\]]*\]\s*',
        r'\s*\[live[^\]]*\]\s*',
        r'\s*\[acoustic[^\]]*\]\s*',
        r'\s*\[remaster[^\]]*\]\s*',
        r'\s*\[explicit[^\]]*\]\s*',
        r'\s*\[clean[^\]]*\]\s*',
        # Dash suffixes
        r'\s+-\s*live\s*$',
        r'\s+-\s*acoustic\s*$',
        r'\s+-\s*remaster(ed)?\s*$',
        r'\s+-\s*original\s*(mix|version)?\s*$',
        r'\s+-\s*radio edit\s*$',
        r'\s+-\s*single\s*(version)?\s*$',
    ]
    result = title.lower()
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    return result.strip()


def spread_artists(songs: List[Dict]) -> List[Dict]:
    """
    Shuffle songs while ensuring the same artist doesn't appear consecutively.
    Uses a round-robin approach to spread artists throughout the playlist.
    """
    if not songs:
        return songs

    # Group songs by normalized artist
    artist_queues: Dict[str, List[Dict]] = defaultdict(list)
    for song in songs:
        artist = normalize_artist_name(song.get("artist", "Unknown"))
        artist_queues[artist].append(song)

    # Shuffle each artist's queue
    for queue in artist_queues.values():
        random.shuffle(queue)

    # Sort artists by number of songs (most songs first)
    sorted_artists = sorted(artist_queues.keys(), key=lambda a: len(artist_queues[a]), reverse=True)

    # Round-robin selection
    result: List[Dict] = []
    last_artist = None

    while any(artist_queues.values()):
        # Find an artist different from the last one
        selected = None
        for artist in sorted_artists:
            if artist_queues[artist] and artist != last_artist:
                selected = artist
                break

        # If all remaining songs are from the same artist, just take it
        if selected is None:
            for artist in sorted_artists:
                if artist_queues[artist]:
                    selected = artist
                    break

        if selected is None:
            break

        song = artist_queues[selected].pop(0)
        result.append(song)
        last_artist = selected

        # Remove empty queues
        if not artist_queues[selected]:
            sorted_artists.remove(selected)

    return result


def spread_artists_and_albums(songs: List[Dict]) -> List[Dict]:
    """
    Shuffle songs while avoiding consecutive same-artist AND same-album songs.
    Provides better variety in the playlist.
    """
    if not songs:
        return songs

    # Group songs by (artist, album) tuple
    groups: Dict[tuple, List[Dict]] = defaultdict(list)
    for song in songs:
        artist = normalize_artist_name(song.get("artist", "Unknown"))
        album = song.get("albumId", song.get("album", "Unknown"))
        groups[(artist, album)].append(song)

    # Shuffle within each group
    for queue in groups.values():
        random.shuffle(queue)

    # Sort groups by size (most songs first for better distribution)
    sorted_keys = sorted(groups.keys(), key=lambda k: len(groups[k]), reverse=True)

    result: List[Dict] = []
    last_artist = None
    last_album = None

    while any(groups.values()):
        selected_key = None

        # Priority 1: Different artist AND different album
        for key in sorted_keys:
            if groups[key] and key[0] != last_artist and key[1] != last_album:
                selected_key = key
                break

        # Priority 2: At least different artist
        if selected_key is None:
            for key in sorted_keys:
                if groups[key] and key[0] != last_artist:
                    selected_key = key
                    break

        # Priority 3: At least different album
        if selected_key is None:
            for key in sorted_keys:
                if groups[key] and key[1] != last_album:
                    selected_key = key
                    break

        # Fallback: Take anything available
        if selected_key is None:
            for key in sorted_keys:
                if groups[key]:
                    selected_key = key
                    break

        if selected_key is None:
            break

        song = groups[selected_key].pop(0)
        result.append(song)
        last_artist = selected_key[0]
        last_album = selected_key[1]

        # Remove empty groups
        if not groups[selected_key]:
            sorted_keys.remove(selected_key)

    return result


class PlaylistGenerator:
    """Generates personalized playlists using Navidrome and Last.fm data."""

    def __init__(self, navidrome: NavidromeClient, lastfm: LastFMClient, llm: "LLMClient" = None):
        self.navidrome = navidrome
        self.lastfm = lastfm
        self.llm = llm
        self._all_songs_cache: List[Dict] = None  # Cache songs across playlist generation

    async def _get_all_songs(self) -> List[Dict]:
        """Get all songs with caching."""
        if self._all_songs_cache is None:
            self._all_songs_cache = await self.navidrome.get_all_songs()
        return self._all_songs_cache

    async def generate_mood_playlists(self, moods: List[str] = None) -> Dict[str, List[str]]:
        """
        Generate mood-based playlists using LLM classification.

        Args:
            moods: List of mood categories (e.g., ["energetic", "chill"])

        Returns:
            Dict mapping mood -> list of song IDs
        """
        if not self.llm:
            logger.warning("LLM not available, skipping mood playlists")
            return {}

        if moods is None:
            moods = config.MOOD_PLAYLISTS

        logger.info(f"Generating mood playlists for: {moods}")

        # Get all songs
        all_songs = await self._get_all_songs()
        logger.info(f"Total songs in library: {len(all_songs)}")

        # Sample songs for classification (LLM can't process entire library at once)
        # Take a diverse sample: mix of popular and random songs
        sample_size = min(200, len(all_songs))

        # Sort by play count and take top 100
        by_plays = sorted(all_songs, key=lambda s: s.get("playCount", 0), reverse=True)
        popular_songs = by_plays[:100]

        # Random sample of the rest
        remaining = by_plays[100:]
        random.shuffle(remaining)
        random_songs = remaining[:sample_size - len(popular_songs)]

        sample = popular_songs + random_songs
        random.shuffle(sample)

        logger.info(f"Classifying {len(sample)} songs by mood...")

        # Classify songs in batches
        all_classifications: Dict[str, List[str]] = {mood: [] for mood in moods}

        batch_size = 40
        for i in range(0, len(sample), batch_size):
            batch = sample[i:i + batch_size]
            try:
                batch_results = await self.llm.classify_songs_by_mood(batch, moods)
                for mood, song_ids in batch_results.items():
                    if mood in all_classifications:
                        all_classifications[mood].extend(song_ids)
            except Exception as e:
                logger.warning(f"Failed to classify batch {i//batch_size + 1}: {e}")

        # Log results
        for mood, songs in all_classifications.items():
            logger.info(f"Mood '{mood}': {len(songs)} songs classified")

        # Deduplicate and spread artists for each mood
        # Use global tracking to ensure a song only appears in ONE mood playlist
        result: Dict[str, List[str]] = {}
        song_lookup = {s["id"]: s for s in sample}
        global_seen_ids: Set[str] = set()  # Track songs already used across all moods
        global_seen_titles: Set[tuple] = set()  # Track (artist, title) to avoid versions

        for mood, song_ids in all_classifications.items():
            # Get full song objects (exclude already used songs)
            mood_songs = [
                song_lookup[sid] for sid in song_ids
                if sid in song_lookup and sid not in global_seen_ids
            ]

            # Deduplicate by title (avoid different versions of same song)
            unique_songs: List[Dict] = []

            for song in mood_songs:
                artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
                title_norm = normalize_song_title(song.get("title", ""))
                title_key = (artist_norm, title_norm)

                if title_key not in global_seen_titles:
                    global_seen_titles.add(title_key)
                    unique_songs.append(song)

            # Spread artists (no consecutive same-artist songs)
            spread_songs = spread_artists(unique_songs)

            # Limit to playlist size
            playlist_size = min(config.PLAYLIST_SIZE, len(spread_songs))
            selected = spread_songs[:playlist_size]

            # Mark selected songs as used globally
            for song in selected:
                global_seen_ids.add(song["id"])

            result[mood] = [s["id"] for s in selected]
            logger.info(f"Selected {len(result[mood])} songs for '{mood}' playlist")

        return result

    async def generate_for_you_playlist(self) -> List[str]:
        """
        Generate "For You" playlist - comfort music you know you'll love.

        Strategy:
        1. Get your top played artists
        2. Select your MOST played songs from those artists
        3. Limit songs per album for variety
        4. Spread artists and albums throughout
        """
        logger.info("Generating 'For You' playlist...")

        # Get all songs with play counts
        all_songs = await self._get_all_songs()
        logger.info(f"Total songs in library: {len(all_songs)}")

        # Build artist and album maps
        artist_plays: Dict[str, int] = defaultdict(int)
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)
        normalized_to_original: Dict[str, str] = {}

        for song in all_songs:
            artist = song.get("artist", "Unknown")
            play_count = song.get("playCount", 0)

            normalized = normalize_artist_name(artist)
            artist_plays[normalized] += play_count
            artist_songs[normalized].append(song)

            if normalized not in normalized_to_original or len(artist) < len(normalized_to_original[normalized]):
                normalized_to_original[normalized] = artist

        # Get top artists (by total plays)
        top_artists = sorted(
            [(norm, plays, normalized_to_original.get(norm, norm))
             for norm, plays in artist_plays.items()
             if plays >= config.MIN_PLAY_COUNT_FOR_TOP_ARTIST],
            key=lambda x: x[1],
            reverse=True
        )[:25]  # Top 25 artists for more variety

        logger.info(f"Top artists: {[a[2] for a in top_artists[:5]]}...")

        # Collect candidate songs from top artists
        # Prioritize MOST played songs (comfort music)
        candidate_songs: List[Dict] = []
        album_count: Dict[str, int] = defaultdict(int)  # Track songs per album
        max_per_album = config.MAX_SONGS_PER_ALBUM

        for normalized, _, _ in top_artists:
            songs = artist_songs.get(normalized, [])
            # Sort by MOST played first (these are the songs you love)
            sorted_songs = sorted(songs, key=lambda s: s.get("playCount", 0), reverse=True)

            for song in sorted_songs:
                album_id = song.get("albumId", song.get("album", "unknown"))

                # Limit songs per album for variety
                if album_count[album_id] < max_per_album:
                    candidate_songs.append(song)
                    album_count[album_id] += 1

                # Take up to 8 songs per artist
                artist_songs_added = sum(1 for s in candidate_songs
                    if normalize_artist_name(s.get("artist", "")) == normalized)
                if artist_songs_added >= 8:
                    break

        logger.info(f"Candidate pool: {len(candidate_songs)} songs from {len(album_count)} albums")

        # Remove duplicates (by ID and by song title to avoid different versions)
        seen_ids: Set[str] = set()
        seen_titles: Set[tuple] = set()
        unique_songs: List[Dict] = []

        for song in candidate_songs:
            song_id = song.get("id")
            if not song_id or song_id in seen_ids:
                continue

            artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
            title_norm = normalize_song_title(song.get("title", ""))
            title_key = (artist_norm, title_norm)

            if title_key in seen_titles:
                continue

            seen_ids.add(song_id)
            seen_titles.add(title_key)
            unique_songs.append(song)

        # Spread artists AND albums throughout (no back-to-back same artist or album)
        spread_songs = spread_artists_and_albums(unique_songs)

        # Select final playlist
        playlist_size = min(config.PLAYLIST_SIZE, len(spread_songs))
        selected_songs = spread_songs[:playlist_size]

        # Log album variety stats
        final_albums = set(s.get("albumId", s.get("album", "")) for s in selected_songs)
        logger.info(f"Selected {len(selected_songs)} songs from {len(final_albums)} albums for 'For You' playlist")

        return [s["id"] for s in selected_songs]

    async def generate_discover_playlist(self) -> List[str]:
        """
        Generate "Discover" playlist based on:
        1. Get all songs from library
        2. Filter to songs with low local play count
        3. Rank by Last.fm popularity
        4. Select top popular but unplayed songs
        """
        logger.info("Generating 'Discover' playlist...")

        # Get all songs
        all_songs = await self.navidrome.get_all_songs()

        # Filter to low play count songs
        low_play_songs = [
            s for s in all_songs
            if s.get("playCount", 0) <= config.MAX_PLAY_COUNT_FOR_DISCOVER
        ]

        logger.info(f"Found {len(low_play_songs)} songs with low play count")

        # Group by normalized artist for efficient Last.fm lookups
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)
        normalized_to_original: Dict[str, str] = {}

        for song in low_play_songs:
            artist = song.get("artist", "Unknown")
            normalized = normalize_artist_name(artist)
            artist_songs[normalized].append(song)

            # Keep shortest original name (likely primary artist)
            if normalized not in normalized_to_original or len(artist) < len(normalized_to_original[normalized]):
                normalized_to_original[normalized] = artist

        # Get popularity data from Last.fm
        songs_with_popularity: List[tuple] = []
        processed_artists: Set[str] = set()

        for normalized, songs in artist_songs.items():
            if normalized in processed_artists:
                continue
            processed_artists.add(normalized)

            try:
                # Use primary artist for Last.fm lookup
                original = normalized_to_original.get(normalized, normalized)
                primary, _ = extract_primary_artist(original)

                # Get top tracks for this artist
                top_tracks = await self.lastfm.get_artist_top_tracks(primary, limit=100)
                top_tracks_map = {t["name"].lower(): t for t in top_tracks}

                # Cache artist info for fallback
                artist_info = None

                for song in songs:
                    title = song.get("title", "")
                    title_lower = title.lower()

                    # Try to match song to Last.fm data
                    if title_lower in top_tracks_map:
                        track_info = top_tracks_map[title_lower]
                        listeners = track_info.get("listeners", 0)
                    else:
                        # Fallback: get artist popularity (only fetch once per artist)
                        if artist_info is None:
                            artist_info = await self.lastfm.get_artist_info(primary)
                        listeners = artist_info.get("listeners", 0) // 100  # Scale down

                    if listeners >= config.LASTFM_MIN_LISTENERS:
                        songs_with_popularity.append((song, listeners))

            except Exception as e:
                logger.warning(f"Failed to get Last.fm data for {normalized}: {e}")

        # Sort by popularity (descending)
        songs_with_popularity.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Found {len(songs_with_popularity)} songs with sufficient Last.fm popularity")

        # Deduplicate by song title (avoid different versions of same song)
        seen_titles: Set[str] = set()  # (normalized_artist, normalized_title)
        deduplicated: List[tuple] = []

        for song, popularity in songs_with_popularity:
            artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
            title_norm = normalize_song_title(song.get("title", ""))
            title_key = (artist_norm, title_norm)

            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduplicated.append((song, popularity))

        # Select top songs (2x playlist size to allow for artist spreading)
        candidate_size = min(config.PLAYLIST_SIZE * 2, len(deduplicated))
        candidates = [s[0] for s in deduplicated[:candidate_size]]

        # Spread artists throughout the playlist
        spread_songs = spread_artists(candidates)

        # Final selection
        playlist_size = min(config.PLAYLIST_SIZE, len(spread_songs))
        selected = spread_songs[:playlist_size]

        logger.info(f"Selected {len(selected)} songs for 'Discover' playlist")
        return [s["id"] for s in selected]

    async def generate_and_save_playlists(self) -> Dict[str, str]:
        """Generate all playlists and save them to Navidrome."""
        results = {}

        # Generate "For You" playlist
        try:
            for_you_songs = await self.generate_for_you_playlist()
            if for_you_songs:
                playlist_id = await self.navidrome.get_or_create_playlist(
                    config.PLAYLIST_FOR_YOU_NAME,
                    for_you_songs
                )
                results["for_you"] = playlist_id
                logger.info(f"Saved 'For You' playlist: {playlist_id}")
        except Exception as e:
            logger.error(f"Failed to generate 'For You' playlist: {e}")

        # Generate "Discover" playlist
        try:
            discover_songs = await self.generate_discover_playlist()
            if discover_songs:
                playlist_id = await self.navidrome.get_or_create_playlist(
                    config.PLAYLIST_DISCOVER_NAME,
                    discover_songs
                )
                results["discover"] = playlist_id
                logger.info(f"Saved 'Discover' playlist: {playlist_id}")
        except Exception as e:
            logger.error(f"Failed to generate 'Discover' playlist: {e}")

        # Generate mood playlists (if LLM is available)
        if self.llm and config.MOOD_PLAYLISTS:
            try:
                mood_results = await self.generate_mood_playlists()
                for mood, song_ids in mood_results.items():
                    if song_ids:
                        playlist_name = f"{config.PLAYLIST_MOOD_PREFIX} {mood.title()}"
                        playlist_id = await self.navidrome.get_or_create_playlist(
                            playlist_name,
                            song_ids
                        )
                        results[f"mood_{mood}"] = playlist_id
                        logger.info(f"Saved '{playlist_name}' playlist: {playlist_id}")
            except Exception as e:
                logger.error(f"Failed to generate mood playlists: {e}")

        # Clear the song cache
        self._all_songs_cache = None

        return results
