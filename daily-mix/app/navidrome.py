import hashlib
import secrets
import httpx
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class NavidromeClient:
    """Client for Navidrome's Subsonic API."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_auth_params(self) -> Dict[str, str]:
        """Generate authentication parameters for Subsonic API."""
        salt = secrets.token_hex(8)
        token = hashlib.md5(f"{self.password}{salt}".encode()).hexdigest()
        return {
            "u": self.username,
            "t": token,
            "s": salt,
            "v": "1.16.1",
            "c": "daily-mix",
            "f": "json",
        }

    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Subsonic API."""
        url = f"{self.base_url}/rest/{endpoint}"
        request_params = self._get_auth_params()
        if params:
            request_params.update(params)

        response = await self.client.get(url, params=request_params)
        response.raise_for_status()
        data = response.json()

        subsonic_response = data.get("subsonic-response", {})
        if subsonic_response.get("status") != "ok":
            error = subsonic_response.get("error", {})
            raise Exception(f"Subsonic API error: {error.get('message', 'Unknown error')}")

        return subsonic_response

    async def get_all_songs(self) -> List[Dict[str, Any]]:
        """Get all songs from the library with play counts."""
        songs = []
        offset = 0
        size = 500

        while True:
            response = await self._request("search3", {
                "query": "",
                "songCount": size,
                "songOffset": offset,
                "artistCount": 0,
                "albumCount": 0,
            })

            search_result = response.get("searchResult3", {})
            batch = search_result.get("song", [])

            if not batch:
                break

            songs.extend(batch)
            offset += size

            if len(batch) < size:
                break

        logger.info(f"Fetched {len(songs)} songs from Navidrome")
        return songs

    async def get_artists(self) -> List[Dict[str, Any]]:
        """Get all artists from the library."""
        response = await self._request("getArtists")
        artists_data = response.get("artists", {})

        artists = []
        for index in artists_data.get("index", []):
            artists.extend(index.get("artist", []))

        logger.info(f"Fetched {len(artists)} artists from Navidrome")
        return artists

    async def get_artist_songs(self, artist_id: str) -> List[Dict[str, Any]]:
        """Get all songs by a specific artist."""
        response = await self._request("getArtist", {"id": artist_id})
        artist_data = response.get("artist", {})

        songs = []
        for album in artist_data.get("album", []):
            album_response = await self._request("getAlbum", {"id": album["id"]})
            album_data = album_response.get("album", {})
            songs.extend(album_data.get("song", []))

        return songs

    async def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists."""
        response = await self._request("getPlaylists")
        return response.get("playlists", {}).get("playlist", [])

    async def create_playlist(self, name: str, song_ids: List[str]) -> str:
        """Create a new playlist with the given songs."""
        params = {"name": name}
        for song_id in song_ids:
            params.setdefault("songId", []).append(song_id)

        # Subsonic API expects multiple songId parameters
        url = f"{self.base_url}/rest/createPlaylist"
        request_params = self._get_auth_params()
        request_params["name"] = name

        # Build URL with multiple songId params
        response = await self.client.get(
            url,
            params=[(k, v) for k, v in request_params.items()] + [("songId", sid) for sid in song_ids]
        )
        response.raise_for_status()
        data = response.json()

        subsonic_response = data.get("subsonic-response", {})
        if subsonic_response.get("status") != "ok":
            error = subsonic_response.get("error", {})
            raise Exception(f"Failed to create playlist: {error.get('message', 'Unknown error')}")

        playlist = subsonic_response.get("playlist", {})
        logger.info(f"Created playlist '{name}' with {len(song_ids)} songs")
        return playlist.get("id", "")

    async def update_playlist(self, playlist_id: str, song_ids: List[str]) -> None:
        """Update an existing playlist with new songs (replaces all songs)."""
        # First, get current songs to remove them
        response = await self._request("getPlaylist", {"id": playlist_id})
        playlist = response.get("playlist", {})
        current_songs = playlist.get("entry", [])

        # Remove all current songs
        if current_songs:
            indices = list(range(len(current_songs)))
            url = f"{self.base_url}/rest/updatePlaylist"
            request_params = self._get_auth_params()
            request_params["playlistId"] = playlist_id

            await self.client.get(
                url,
                params=[(k, v) for k, v in request_params.items()] + [("songIndexToRemove", i) for i in indices]
            )

        # Add new songs
        if song_ids:
            url = f"{self.base_url}/rest/updatePlaylist"
            request_params = self._get_auth_params()
            request_params["playlistId"] = playlist_id

            await self.client.get(
                url,
                params=[(k, v) for k, v in request_params.items()] + [("songIdToAdd", sid) for sid in song_ids]
            )

        logger.info(f"Updated playlist {playlist_id} with {len(song_ids)} songs")

    async def get_or_create_playlist(self, name: str, song_ids: List[str]) -> str:
        """Get existing playlist by name or create new one, then update with songs."""
        playlists = await self.get_playlists()

        for playlist in playlists:
            if playlist.get("name") == name:
                await self.update_playlist(playlist["id"], song_ids)
                return playlist["id"]

        return await self.create_playlist(name, song_ids)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
