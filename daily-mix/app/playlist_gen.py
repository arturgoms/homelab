import random
from typing import List, Dict, Any, Set
from collections import defaultdict
import logging

from .navidrome import NavidromeClient
from .lastfm import LastFMClient
from .config import config

logger = logging.getLogger(__name__)


class PlaylistGenerator:
    """Generates personalized playlists using Navidrome and Last.fm data."""

    def __init__(self, navidrome: NavidromeClient, lastfm: LastFMClient):
        self.navidrome = navidrome
        self.lastfm = lastfm

    async def generate_for_you_playlist(self) -> List[str]:
        """
        Generate "For You" playlist based on:
        1. Get top played artists from Navidrome
        2. Find similar artists via Last.fm
        3. Match similar artists to library
        4. Pick tracks from those artists
        """
        logger.info("Generating 'For You' playlist...")

        # Get all songs with play counts
        all_songs = await self.navidrome.get_all_songs()
        logger.info(f"Total songs in library: {len(all_songs)}")

        # Build artist play count map
        artist_plays: Dict[str, int] = defaultdict(int)
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)

        for song in all_songs:
            artist = song.get("artist", "Unknown")
            play_count = song.get("playCount", 0)
            artist_plays[artist] += play_count
            artist_songs[artist].append(song)

        # Get top artists (by total plays)
        top_artists = sorted(
            [(artist, plays) for artist, plays in artist_plays.items()
             if plays >= config.MIN_PLAY_COUNT_FOR_TOP_ARTIST],
            key=lambda x: x[1],
            reverse=True
        )[:20]  # Top 20 artists

        logger.info(f"Top artists: {[a[0] for a in top_artists[:5]]}...")

        # Find similar artists via Last.fm
        similar_artists: Set[str] = set()
        library_artists = set(artist_plays.keys())
        library_artists_lower = {a.lower(): a for a in library_artists}

        for artist, _ in top_artists:
            try:
                similar = await self.lastfm.get_similar_artists(artist, limit=15)
                for sim in similar:
                    sim_name = sim["name"]
                    # Check if similar artist exists in library (case-insensitive)
                    sim_lower = sim_name.lower()
                    if sim_lower in library_artists_lower:
                        similar_artists.add(library_artists_lower[sim_lower])
            except Exception as e:
                logger.warning(f"Failed to get similar artists for {artist}: {e}")

        logger.info(f"Found {len(similar_artists)} similar artists in library")

        # Collect candidate songs
        candidate_songs: List[Dict] = []

        # Add songs from top artists (weight: 40%)
        for artist, _ in top_artists:
            songs = artist_songs.get(artist, [])
            # Prefer songs with lower play counts to add variety
            sorted_songs = sorted(songs, key=lambda s: s.get("playCount", 0))
            candidate_songs.extend(sorted_songs[:5])

        # Add songs from similar artists (weight: 60%)
        for artist in similar_artists:
            songs = artist_songs.get(artist, [])
            # Prefer less played songs
            sorted_songs = sorted(songs, key=lambda s: s.get("playCount", 0))
            candidate_songs.extend(sorted_songs[:3])

        # Remove duplicates and shuffle
        seen_ids: Set[str] = set()
        unique_songs: List[Dict] = []
        for song in candidate_songs:
            song_id = song.get("id")
            if song_id and song_id not in seen_ids:
                seen_ids.add(song_id)
                unique_songs.append(song)

        random.shuffle(unique_songs)

        # Select final playlist
        playlist_size = min(config.PLAYLIST_SIZE, len(unique_songs))
        selected_songs = unique_songs[:playlist_size]

        logger.info(f"Selected {len(selected_songs)} songs for 'For You' playlist")
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

        # Group by artist for efficient Last.fm lookups
        artist_songs: Dict[str, List[Dict]] = defaultdict(list)
        for song in low_play_songs:
            artist = song.get("artist", "Unknown")
            artist_songs[artist].append(song)

        # Get popularity data from Last.fm
        songs_with_popularity: List[tuple] = []

        for artist, songs in artist_songs.items():
            try:
                # Get top tracks for this artist
                top_tracks = await self.lastfm.get_artist_top_tracks(artist, limit=100)
                top_tracks_map = {t["name"].lower(): t for t in top_tracks}

                for song in songs:
                    title = song.get("title", "")
                    title_lower = title.lower()

                    # Try to match song to Last.fm data
                    if title_lower in top_tracks_map:
                        track_info = top_tracks_map[title_lower]
                        listeners = track_info.get("listeners", 0)
                    else:
                        # Fallback: get artist popularity
                        artist_info = await self.lastfm.get_artist_info(artist)
                        listeners = artist_info.get("listeners", 0) // 100  # Scale down

                    if listeners >= config.LASTFM_MIN_LISTENERS:
                        songs_with_popularity.append((song, listeners))

            except Exception as e:
                logger.warning(f"Failed to get Last.fm data for {artist}: {e}")

        # Sort by popularity (descending)
        songs_with_popularity.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Found {len(songs_with_popularity)} songs with sufficient Last.fm popularity")

        # Select top songs
        playlist_size = min(config.PLAYLIST_SIZE, len(songs_with_popularity))
        selected = songs_with_popularity[:playlist_size]

        # Shuffle to avoid always playing in popularity order
        random.shuffle(selected)

        logger.info(f"Selected {len(selected)} songs for 'Discover' playlist")
        return [s[0]["id"] for s in selected]

    async def generate_and_save_playlists(self) -> Dict[str, str]:
        """Generate both playlists and save them to Navidrome."""
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

        return results
