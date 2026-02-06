import re
import random
from typing import List, Dict, Any, Set, Optional
from collections import defaultdict
import logging

from .navidrome import NavidromeClient
from .lastfm import LastFMClient, extract_primary_artist
from .config import config
from .history import PlaylistHistory
from .scoring import SongScorer

# Import LLM client conditionally
try:
    from .llm import LLMClient
except ImportError:
    LLMClient = None

logger = logging.getLogger(__name__)

# Patterns that indicate non-music tracks
_SKIT_PATTERNS = re.compile(
    r'\b(skit|interlude|intro|outro|intermission)\b'
    r'|\(skit\)|\(interlude\)|\(intro\)|\(outro\)',
    re.IGNORECASE
)


def is_skit_or_interlude(song: Dict) -> bool:
    """Check if a song is a skit, interlude, intro, or outro."""
    title = song.get("title", "")
    return bool(_SKIT_PATTERNS.search(title))


def normalize_artist_name(artist: str) -> str:
    """Normalize artist name for grouping (extracts primary artist)."""
    primary, _ = extract_primary_artist(artist)
    return primary.lower().strip()


def normalize_song_title(title: str) -> str:
    """Normalize song title for deduplication (removes version indicators)."""
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


def deduplicate_songs(songs: List[Dict], extra_exclude_ids: Set[str] = None) -> List[Dict]:
    """Remove duplicate songs by ID and by normalized (artist, title)."""
    if extra_exclude_ids is None:
        extra_exclude_ids = set()

    seen_ids: Set[str] = set()
    seen_titles: Set[tuple] = set()
    unique: List[Dict] = []

    for song in songs:
        song_id = song.get("id")
        if not song_id or song_id in seen_ids or song_id in extra_exclude_ids:
            continue

        artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
        title_norm = normalize_song_title(song.get("title", ""))
        title_key = (artist_norm, title_norm)

        if title_key in seen_titles:
            continue

        seen_ids.add(song_id)
        seen_titles.add(title_key)
        unique.append(song)

    return unique


def cap_artist_songs(songs: List[Dict], max_per_artist: int) -> List[Dict]:
    """Limit the number of songs per artist to enforce diversity."""
    artist_count: Dict[str, int] = defaultdict(int)
    result: List[Dict] = []

    for song in songs:
        artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
        if artist_count[artist_norm] < max_per_artist:
            result.append(song)
            artist_count[artist_norm] += 1

    return result


class PlaylistGenerator:
    """Generates personalized playlists using Navidrome and Last.fm data."""

    def __init__(self, navidrome: NavidromeClient, lastfm: LastFMClient,
                 llm: "LLMClient" = None, history: PlaylistHistory = None):
        self.navidrome = navidrome
        self.lastfm = lastfm
        self.llm = llm
        self.history = history
        self._all_songs_cache: List[Dict] = None
        self._scorer: SongScorer = None
        # Track song IDs used across all playlists in a single run
        self._used_song_ids: Set[str] = set()

    async def _get_all_songs(self) -> List[Dict]:
        """Get all songs with caching. Filters out skits/interludes."""
        if self._all_songs_cache is None:
            raw = await self.navidrome.get_all_songs()
            skits = [s for s in raw if is_skit_or_interlude(s)]
            self._all_songs_cache = [s for s in raw if not is_skit_or_interlude(s)]
            if skits:
                logger.info(f"Filtered {len(skits)} skits/interludes from library")
        return self._all_songs_cache

    async def _get_scorer(self) -> SongScorer:
        """Get or create the scorer (lazy init after songs are loaded)."""
        if self._scorer is None:
            all_songs = await self._get_all_songs()
            self._scorer = SongScorer(
                all_songs,
                recency_decay_days=config.RECENCY_DECAY_DAYS
            )
        return self._scorer

    def _filter_cooldown(self, songs: List[Dict], playlist_name: str) -> List[Dict]:
        """Filter out songs that are on cooldown for this playlist."""
        if not self.history:
            return songs

        cooldown_ids = self.history.get_cooldown_song_ids(playlist_name)
        if not cooldown_ids:
            return songs

        filtered = [s for s in songs if s.get("id") not in cooldown_ids]
        removed = len(songs) - len(filtered)
        if removed > 0:
            logger.info(f"Filtered {removed} songs on cooldown for '{playlist_name}'")
        return filtered

    def _record_playlist(self, playlist_name: str, song_ids: List[str]):
        """Record playlist songs in history for cooldown tracking."""
        if self.history:
            self.history.record_playlist(playlist_name, song_ids)

    async def generate_for_you_playlist(self) -> List[str]:
        """
        Generate "For You" playlist - the best songs from artists you love.

        Strategy:
        1. Rank artists by affinity (total plays + starred count + album count)
        2. Pick top 25 artists
        3. Allocate playlist slots proportionally to each artist's affinity
        4. For each artist, pick their best N songs by Last.fm popularity + starred
        5. Apply album cap, cooldown, dedup, spread
        """
        logger.info("Generating 'For You' playlist...")
        playlist_name = config.PLAYLIST_FOR_YOU_NAME

        all_songs = await self._get_all_songs()
        logger.info(f"Total songs in library: {len(all_songs)}")

        # Step 1: Build artist affinity scores
        artist_plays: Dict[str, int] = defaultdict(int)
        artist_starred: Dict[str, int] = defaultdict(int)
        artist_albums: Dict[str, Set[str]] = defaultdict(set)
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)
        normalized_to_original: Dict[str, str] = {}

        for song in all_songs:
            artist = song.get("artist", "Unknown")
            normalized = normalize_artist_name(artist)
            play_count = song.get("playCount", 0)

            artist_plays[normalized] += play_count
            if song.get("starred"):
                artist_starred[normalized] += 1
            album_id = song.get("albumId", song.get("album", "unknown"))
            artist_albums[normalized].add(album_id)
            artist_songs[normalized].append(song)

            if normalized not in normalized_to_original or len(artist) < len(normalized_to_original[normalized]):
                normalized_to_original[normalized] = artist

        # Composite artist affinity: plays + starred*10 + albums*5
        artist_affinity = {}
        for norm in artist_plays:
            artist_affinity[norm] = (
                artist_plays[norm]
                + artist_starred.get(norm, 0) * 10
                + len(artist_albums.get(norm, set())) * 5
            )

        # Step 2: Top 25 artists
        top_artists = sorted(
            [(norm, score, normalized_to_original.get(norm, norm))
             for norm, score in artist_affinity.items()
             if score >= config.MIN_PLAY_COUNT_FOR_TOP_ARTIST],
            key=lambda x: x[1],
            reverse=True
        )[:25]

        logger.info(f"Top artists: {[(a[2], a[1]) for a in top_artists[:8]]}...")

        # Step 3: Allocate playlist slots proportionally to affinity
        # Overprovision by 50% to account for cooldown/album-cap filtering losses
        target_slots = int(config.PLAYLIST_SIZE * 1.5)
        total_affinity = sum(a[1] for a in top_artists)

        # Each artist gets at least 1 slot, rest distributed by affinity
        artist_slots: Dict[str, int] = {}
        remaining_slots = target_slots - len(top_artists)  # Reserve 1 per artist

        for norm, affinity, original in top_artists:
            # 1 base slot + proportional share of remaining
            extra = round((affinity / total_affinity) * remaining_slots) if total_affinity > 0 else 0
            artist_slots[norm] = max(1, 1 + extra)

        # Adjust to sum to exactly target_slots (rounding may over/under-allocate)
        current_total = sum(artist_slots.values())
        if current_total != target_slots:
            sorted_by_affinity = sorted(artist_slots.keys(),
                                        key=lambda n: artist_affinity.get(n, 0),
                                        reverse=(current_total < target_slots))
            diff = target_slots - current_total
            step = 1 if diff > 0 else -1
            for i in range(abs(diff)):
                norm = sorted_by_affinity[i % len(sorted_by_affinity)]
                artist_slots[norm] = max(1, artist_slots[norm] + step)

        logger.info(f"Slot allocation: {[(normalized_to_original.get(n, n), s) for n, s in sorted(artist_slots.items(), key=lambda x: -x[1])[:10]]}...")

        # Step 4: For each artist, pick their best N songs
        from .scoring import recency_score as _recency_score
        selected_songs: List[Dict] = []

        for normalized, affinity, original in top_artists:
            slots = artist_slots.get(normalized, 1)
            songs = artist_songs.get(normalized, [])
            primary, _ = extract_primary_artist(original)

            # Get Last.fm top tracks for ranking
            try:
                top_tracks = await self.lastfm.get_artist_top_tracks(primary, limit=100)
                top_tracks_map = {t["name"].lower(): t for t in top_tracks}
            except Exception as e:
                logger.warning(f"Failed to get Last.fm top tracks for {primary}: {e}")
                top_tracks_map = {}

            # Score each song
            scored: List[tuple] = []
            for song in songs:
                title_lower = song.get("title", "").lower()

                # Last.fm popularity (0-1)
                if title_lower in top_tracks_map:
                    track = top_tracks_map[title_lower]
                    listeners = int(track.get("listeners", 0))
                    lastfm_score = min(listeners / 1_000_000, 1.0)
                else:
                    lastfm_score = 0.1

                starred_bonus = 0.3 if song.get("starred") else 0.0
                recency = _recency_score(song.get("played"), config.RECENCY_DECAY_DAYS) * 0.15
                jitter = random.uniform(-0.05, 0.05)

                song_score = lastfm_score + starred_bonus + recency + jitter
                scored.append((song, song_score))

            scored.sort(key=lambda x: x[1], reverse=True)

            # Pick top songs, respecting album cap and cooldown
            cooldown_ids = self.history.get_cooldown_song_ids(playlist_name) if self.history else set()
            album_count: Dict[str, int] = defaultdict(int)
            picked = 0
            seen_titles: Set[str] = set()

            for song, score in scored:
                if picked >= slots:
                    break
                song_id = song.get("id")
                if song_id in cooldown_ids:
                    continue
                album_id = song.get("albumId", song.get("album", "unknown"))
                if album_count[album_id] >= config.MAX_SONGS_PER_ALBUM:
                    continue
                title_norm = normalize_song_title(song.get("title", ""))
                if title_norm in seen_titles:
                    continue

                selected_songs.append(song)
                album_count[album_id] += 1
                seen_titles.add(title_norm)
                picked += 1

        logger.info(f"Picked {len(selected_songs)} songs from {len(top_artists)} artists")

        # Step 5: Deduplicate globally, spread, and trim to playlist size
        unique_songs = deduplicate_songs(selected_songs)
        spread_songs = spread_artists_and_albums(unique_songs)
        final_songs = spread_songs[:config.PLAYLIST_SIZE]

        final_albums = set(s.get("albumId", s.get("album", "")) for s in final_songs)
        final_artists = set(normalize_artist_name(s.get("artist", "")) for s in final_songs)
        logger.info(f"Final 'For You': {len(final_songs)} songs from {len(final_artists)} artists, {len(final_albums)} albums")

        song_ids = [s["id"] for s in final_songs]
        self._used_song_ids.update(song_ids)
        self._record_playlist(playlist_name, song_ids)
        return song_ids

    async def generate_discover_playlist(self) -> List[str]:
        """
        Generate "Discover" playlist - popular but unplayed/underplayed gems.

        Strategy:
        1. Filter to low play count songs, exclude comfort music
        2. Get Last.fm popularity data
        3. Boost songs from underrepresented artists (fewer songs in library = higher boost)
        4. Score, filter cooldown, deduplicate, cap per artist, spread
        """
        logger.info("Generating 'Discover' playlist...")
        playlist_name = config.PLAYLIST_DISCOVER_NAME

        all_songs = await self._get_all_songs()
        scorer = await self._get_scorer()

        # Build artist song count across the FULL library (for underrepresentation boost)
        library_artist_count: Dict[str, int] = defaultdict(int)
        for s in all_songs:
            library_artist_count[normalize_artist_name(s.get("artist", "Unknown"))] += 1
        max_artist_songs = max(library_artist_count.values()) if library_artist_count else 1

        # Filter to low play count songs
        # Exclude starred songs that have been played — those are comfort music, not discoveries
        low_play_songs = [
            s for s in all_songs
            if s.get("playCount", 0) <= config.MAX_PLAY_COUNT_FOR_DISCOVER
            and not (s.get("starred") and s.get("playCount", 0) > 0)
            and s.get("id") not in self._used_song_ids
        ]

        logger.info(f"Found {len(low_play_songs)} candidate songs for Discover")

        # Group by normalized artist for efficient Last.fm lookups
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)
        normalized_to_original: Dict[str, str] = {}

        for song in low_play_songs:
            artist = song.get("artist", "Unknown")
            normalized = normalize_artist_name(artist)
            artist_songs[normalized].append(song)
            if normalized not in normalized_to_original or len(artist) < len(normalized_to_original[normalized]):
                normalized_to_original[normalized] = artist

        # Get popularity data from Last.fm and build popularity map
        lastfm_popularities: Dict[str, float] = {}
        max_listeners = 1
        songs_with_listeners: List[tuple] = []
        processed_artists: Set[str] = set()

        for normalized, songs in artist_songs.items():
            if normalized in processed_artists:
                continue
            processed_artists.add(normalized)

            try:
                original = normalized_to_original.get(normalized, normalized)
                primary, _ = extract_primary_artist(original)
                top_tracks = await self.lastfm.get_artist_top_tracks(primary, limit=100)
                top_tracks_map = {t["name"].lower(): t for t in top_tracks}
                artist_info = None

                for song in songs:
                    title = song.get("title", "")
                    title_lower = title.lower()

                    if title_lower in top_tracks_map:
                        track_info = top_tracks_map[title_lower]
                        listeners = track_info.get("listeners", 0)
                    else:
                        if artist_info is None:
                            artist_info = await self.lastfm.get_artist_info(primary)
                        listeners = artist_info.get("listeners", 0) // 100

                    if listeners >= config.LASTFM_MIN_LISTENERS:
                        songs_with_listeners.append((song, listeners))
                        if listeners > max_listeners:
                            max_listeners = listeners

            except Exception as e:
                logger.warning(f"Failed to get Last.fm data for {normalized}: {e}")

        # Normalize Last.fm listeners to 0-1 and apply underrepresentation boost
        # Artists with fewer songs in library get a much higher multiplier
        # so they can compete with heavy-hitter artists who dominate Last.fm
        import math
        for song, listeners in songs_with_listeners:
            normalized = normalize_artist_name(song.get("artist", "Unknown"))
            artist_count = library_artist_count.get(normalized, 1)
            # Exponential inverse: fewer songs = much bigger boost
            # ratio goes from 0.0 (1 song) to 1.0 (max songs)
            # boost goes from 5.0x (1 song) down to 1.0x (max songs)
            ratio = (artist_count - 1) / max(max_artist_songs - 1, 1)
            underrep_boost = 1.0 + 4.0 * ((1.0 - ratio) ** 2)
            boosted_popularity = min((listeners / max_listeners) * underrep_boost, 1.0)
            lastfm_popularities[song["id"]] = boosted_popularity

        logger.info(f"Found {len(songs_with_listeners)} songs with sufficient Last.fm popularity")

        # Score songs with discover profile
        eligible_songs = [s for s, _ in songs_with_listeners]
        scored = scorer.score_songs(eligible_songs, profile="discover", lastfm_popularities=lastfm_popularities)

        # Take all scored candidates — the per-artist cap will enforce variety
        candidates = [song for song, score in scored]

        # Filter cooldown
        candidates = self._filter_cooldown(candidates, playlist_name)

        # Deduplicate
        candidates = deduplicate_songs(candidates)

        # Cap songs per artist — Discover uses a tighter cap for more variety
        candidates = cap_artist_songs(candidates, max_per_artist=config.MAX_SONGS_PER_ARTIST_DISCOVER)

        # Spread artists
        spread_songs = spread_artists(candidates)

        # Final selection
        playlist_size = min(config.PLAYLIST_SIZE, len(spread_songs))
        selected = spread_songs[:playlist_size]

        logger.info(f"Selected {len(selected)} songs for 'Discover' playlist")
        song_ids = [s["id"] for s in selected]
        self._used_song_ids.update(song_ids)
        self._record_playlist(playlist_name, song_ids)
        return song_ids

    async def generate_mood_playlists(self) -> Dict[str, List[str]]:
        """
        Generate mood-based playlists using LLM classification.
        Moods are either auto-discovered by the LLM or configured manually.

        Returns:
            Dict mapping mood name -> list of song IDs
        """
        if not self.llm:
            logger.warning("LLM not available, skipping mood playlists")
            return {}

        all_songs = await self._get_all_songs()
        scorer = await self._get_scorer()
        logger.info(f"Total songs in library: {len(all_songs)}")

        # Determine mood categories
        if config.LLM_AUTO_MOODS:
            mood_config = await self.llm.discover_moods(all_songs, config.MOOD_CONFIG_FILE)
            moods = mood_config.get("moods", config.MOOD_PLAYLISTS)
        else:
            moods = config.MOOD_PLAYLISTS

        logger.info(f"Generating mood playlists for: {moods}")

        # Exclude songs already used in For You / Discover
        available_songs = [s for s in all_songs if s.get("id") not in self._used_song_ids]
        logger.info(f"Available songs after cross-playlist dedup: {len(available_songs)}")

        # Sample songs for classification — bias toward higher-scoring songs
        scored_songs = scorer.score_songs(available_songs, profile="for_you")
        sample_size = min(400, len(scored_songs))

        # Take top 200 scored + 200 random for diversity
        top_scored = [s for s, _ in scored_songs[:200]]
        remaining = [s for s, _ in scored_songs[200:]]
        random.shuffle(remaining)
        random_sample = remaining[:max(0, sample_size - len(top_scored))]

        sample = top_scored + random_sample
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

        for mood, songs_ids in all_classifications.items():
            logger.info(f"Mood '{mood}': {len(songs_ids)} songs classified")

        # Deduplicate and spread artists for each mood
        # Track songs globally to ensure a song only appears in ONE mood playlist
        result: Dict[str, List[str]] = {}
        song_lookup = {s["id"]: s for s in sample}
        global_seen_ids: Set[str] = set()
        global_seen_titles: Set[tuple] = set()

        for mood, song_ids in all_classifications.items():
            playlist_name = f"{config.PLAYLIST_MOOD_PREFIX} {mood.title()}"

            # Get full song objects (exclude already used songs)
            mood_songs = [
                song_lookup[sid] for sid in song_ids
                if sid in song_lookup and sid not in global_seen_ids
            ]

            # Filter cooldown
            mood_songs = self._filter_cooldown(mood_songs, playlist_name)

            # Deduplicate by title (avoid different versions of same song)
            unique_songs: List[Dict] = []
            for song in mood_songs:
                artist_norm = normalize_artist_name(song.get("artist", "Unknown"))
                title_norm = normalize_song_title(song.get("title", ""))
                title_key = (artist_norm, title_norm)

                if title_key not in global_seen_titles:
                    global_seen_titles.add(title_key)
                    unique_songs.append(song)

            # Cap songs per artist per mood playlist
            capped_songs = cap_artist_songs(unique_songs, max_per_artist=config.MAX_SONGS_PER_ARTIST)

            # Spread artists
            spread_songs = spread_artists(capped_songs)

            # Limit to playlist size
            playlist_size = min(config.PLAYLIST_SIZE, len(spread_songs))
            selected = spread_songs[:playlist_size]

            # Mark selected songs as used globally
            for song in selected:
                global_seen_ids.add(song["id"])

            selected_ids = [s["id"] for s in selected]
            self._used_song_ids.update(selected_ids)
            result[mood] = selected_ids
            self._record_playlist(playlist_name, selected_ids)
            logger.info(f"Selected {len(selected_ids)} songs for '{mood}' playlist")

        return result

    async def generate_and_save_playlists(self) -> Dict[str, str]:
        """Generate all playlists and save them to Navidrome."""
        results = {}

        # Generate "For You" playlist
        try:
            for_you_songs = await self.generate_for_you_playlist()
            if for_you_songs:
                comment = None
                if self.llm and config.LLM_PLAYLIST_DESCRIPTIONS:
                    all_songs = await self._get_all_songs()
                    song_lookup = {s["id"]: s for s in all_songs}
                    playlist_songs = [song_lookup[sid] for sid in for_you_songs if sid in song_lookup]
                    comment = await self.llm.generate_description(config.PLAYLIST_FOR_YOU_NAME, playlist_songs)

                playlist_id = await self.navidrome.get_or_create_playlist(
                    config.PLAYLIST_FOR_YOU_NAME,
                    for_you_songs,
                    comment=comment,
                )
                results["for_you"] = playlist_id
                logger.info(f"Saved 'For You' playlist: {playlist_id}")
        except Exception as e:
            logger.error(f"Failed to generate 'For You' playlist: {e}")

        # Generate "Discover" playlist
        try:
            discover_songs = await self.generate_discover_playlist()
            if discover_songs:
                comment = None
                if self.llm and config.LLM_PLAYLIST_DESCRIPTIONS:
                    all_songs = await self._get_all_songs()
                    song_lookup = {s["id"]: s for s in all_songs}
                    playlist_songs = [song_lookup[sid] for sid in discover_songs if sid in song_lookup]
                    comment = await self.llm.generate_description(config.PLAYLIST_DISCOVER_NAME, playlist_songs)

                playlist_id = await self.navidrome.get_or_create_playlist(
                    config.PLAYLIST_DISCOVER_NAME,
                    discover_songs,
                    comment=comment,
                )
                results["discover"] = playlist_id
                logger.info(f"Saved 'Discover' playlist: {playlist_id}")
        except Exception as e:
            logger.error(f"Failed to generate 'Discover' playlist: {e}")

        # Generate mood playlists (if LLM is available)
        if self.llm:
            try:
                mood_results = await self.generate_mood_playlists()
                for mood, song_ids in mood_results.items():
                    if song_ids:
                        playlist_name = f"{config.PLAYLIST_MOOD_PREFIX} {mood.title()}"

                        comment = None
                        if config.LLM_PLAYLIST_DESCRIPTIONS:
                            all_songs = await self._get_all_songs()
                            song_lookup = {s["id"]: s for s in all_songs}
                            playlist_songs = [song_lookup[sid] for sid in song_ids if sid in song_lookup]
                            comment = await self.llm.generate_description(playlist_name, playlist_songs)

                        playlist_id = await self.navidrome.get_or_create_playlist(
                            playlist_name,
                            song_ids,
                            comment=comment,
                        )
                        results[f"mood_{mood}"] = playlist_id
                        logger.info(f"Saved '{playlist_name}' playlist: {playlist_id}")
            except Exception as e:
                logger.error(f"Failed to generate mood playlists: {e}")

        # Clear the song cache
        self._all_songs_cache = None
        self._scorer = None

        return results
