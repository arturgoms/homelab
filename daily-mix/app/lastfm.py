import httpx
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

LASTFM_API_URL = "https://ws.audioscrobbler.com/2.0/"


class LastFMClient:
    """Client for Last.fm public API (no user authentication needed)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, Any] = {}

    async def _request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Make request to Last.fm API."""
        request_params = {
            "method": method,
            "api_key": self.api_key,
            "format": "json",
        }
        if params:
            request_params.update(params)

        response = await self.client.get(LASTFM_API_URL, params=request_params)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            logger.warning(f"Last.fm API error: {data.get('message', 'Unknown error')}")
            return {}

        return data

    async def get_similar_artists(self, artist: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get similar artists for a given artist name."""
        cache_key = f"similar:{artist}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self._request("artist.getSimilar", {
            "artist": artist,
            "limit": limit,
        })

        similar = data.get("similarartists", {}).get("artist", [])
        if isinstance(similar, dict):
            similar = [similar]

        result = [
            {
                "name": a.get("name", ""),
                "match": float(a.get("match", 0)),
            }
            for a in similar
        ]

        self._cache[cache_key] = result
        return result

    async def get_artist_top_tracks(self, artist: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top tracks for an artist with listener counts."""
        cache_key = f"toptracks:{artist}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self._request("artist.getTopTracks", {
            "artist": artist,
            "limit": limit,
        })

        tracks = data.get("toptracks", {}).get("track", [])
        if isinstance(tracks, dict):
            tracks = [tracks]

        result = [
            {
                "name": t.get("name", ""),
                "artist": t.get("artist", {}).get("name", "") if isinstance(t.get("artist"), dict) else t.get("artist", ""),
                "playcount": int(t.get("playcount", 0)),
                "listeners": int(t.get("listeners", 0)),
            }
            for t in tracks
        ]

        self._cache[cache_key] = result
        return result

    async def get_track_info(self, artist: str, track: str) -> Dict[str, Any]:
        """Get detailed info about a track including listener count."""
        cache_key = f"track:{artist}:{track}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self._request("track.getInfo", {
            "artist": artist,
            "track": track,
        })

        track_data = data.get("track", {})
        result = {
            "name": track_data.get("name", ""),
            "artist": track_data.get("artist", {}).get("name", "") if isinstance(track_data.get("artist"), dict) else "",
            "playcount": int(track_data.get("playcount", 0)),
            "listeners": int(track_data.get("listeners", 0)),
        }

        self._cache[cache_key] = result
        return result

    async def get_artist_info(self, artist: str) -> Dict[str, Any]:
        """Get info about an artist including listener count."""
        cache_key = f"artist:{artist}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self._request("artist.getInfo", {
            "artist": artist,
        })

        artist_data = data.get("artist", {})
        stats = artist_data.get("stats", {})

        result = {
            "name": artist_data.get("name", ""),
            "listeners": int(stats.get("listeners", 0)),
            "playcount": int(stats.get("playcount", 0)),
        }

        self._cache[cache_key] = result
        return result

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
