import httpx
import json
import os
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for vLLM server with OpenAI-compatible API."""

    def __init__(self, base_url: str, model: str = "default", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = httpx.AsyncClient(timeout=timeout)
        self._available_model: Optional[str] = None

    async def _get_model(self) -> str:
        """Get the available model name from the server."""
        if self._available_model:
            return self._available_model

        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                if models:
                    self._available_model = models[0].get("id", self.model)
                    logger.info(f"Using LLM model: {self._available_model}")
                    return self._available_model
        except Exception as e:
            logger.warning(f"Could not fetch models list: {e}")

        return self.model

    async def complete(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.3) -> str:
        """Send a completion request to the LLM."""
        model = await self._get_model()

        try:
            response = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

            return ""
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def _parse_json_response(self, response: str) -> Any:
        """Parse JSON from an LLM response, handling markdown code blocks."""
        json_str = response.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        return json.loads(json_str.strip())

    async def discover_moods(self, songs: List[Dict[str, Any]], mood_config_file: str) -> Dict[str, str]:
        """
        Analyze the library and pick the 2 best mood/vibe categories.
        Results are cached to mood_config_file and reused on subsequent runs.

        Returns:
            Dict with "moods" list and "descriptions" dict
        """
        # Check for existing config
        if os.path.exists(mood_config_file):
            try:
                with open(mood_config_file, "r") as f:
                    cached = json.load(f)
                if cached.get("moods") and len(cached["moods"]) == 2:
                    logger.info(f"Using cached mood config: {cached['moods']}")
                    return cached
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load mood config, will re-discover: {e}")

        # Sample ~100 songs with genre data, biased toward higher play counts
        sample_size = min(100, len(songs))
        sorted_by_plays = sorted(songs, key=lambda s: s.get("playCount", 0), reverse=True)
        # Take top 60 + random 40 for diversity
        top_songs = sorted_by_plays[:60]
        remaining = sorted_by_plays[60:]
        import random
        random.shuffle(remaining)
        sample = top_songs + remaining[:max(0, sample_size - len(top_songs))]
        random.shuffle(sample)

        # Format songs with genre and year info
        song_list = "\n".join([
            f"- \"{s.get('title', 'Unknown')}\" by {s.get('artist', 'Unknown')} [{s.get('genre', 'Unknown')}, {s.get('year', 'Unknown')}]"
            for s in sample[:100]
        ])

        prompt = f"""Here is a sample of my music library with genres and years:
{song_list}

Based on this library, suggest exactly 2 mood/vibe playlist categories that would work best for this specific collection. Don't use generic categories like "happy" or "sad". Be specific to what this library contains. Examples of good categories: "Late Night Drive", "Sunday Morning", "Workout Energy", "Rainy Day", "Brazilian Sunset".

Respond with JSON only: {{"moods": ["mood1", "mood2"], "descriptions": {{"mood1": "one sentence description", "mood2": "one sentence description"}}}}"""

        try:
            response = await self.complete(prompt, max_tokens=512, temperature=0.7)
            result = self._parse_json_response(response)

            if not result.get("moods") or len(result["moods"]) != 2:
                raise ValueError(f"Expected 2 moods, got: {result.get('moods')}")

            # Cache the result
            os.makedirs(os.path.dirname(mood_config_file), exist_ok=True)
            with open(mood_config_file, "w") as f:
                json.dump(result, f, indent=2)

            logger.info(f"Discovered moods: {result['moods']}")
            return result

        except Exception as e:
            logger.error(f"Failed to discover moods: {e}")
            # Fallback to defaults
            return {
                "moods": ["energetic", "chill"],
                "descriptions": {
                    "energetic": "High-energy tracks to keep you moving",
                    "chill": "Relaxed vibes for unwinding",
                }
            }

    async def classify_songs_by_mood(
        self,
        songs: List[Dict[str, Any]],
        moods: List[str] = None
    ) -> Dict[str, List[str]]:
        """
        Classify songs into mood categories.

        Args:
            songs: List of song dicts with 'id', 'title', 'artist', 'album' keys
            moods: List of mood categories to classify into

        Returns:
            Dict mapping mood -> list of song IDs
        """
        if moods is None:
            moods = ["energetic", "chill", "melancholic", "romantic", "party"]

        # Format songs with genre and year for better classification
        song_list = "\n".join([
            f'{i+1}. "{s.get("title", "Unknown")}" by {s.get("artist", "Unknown")} [{s.get("genre", "Unknown")}, {s.get("year", "Unknown")}]'
            for i, s in enumerate(songs[:50])  # Limit to 50 songs per batch
        ])

        prompt = f"""Classify these songs into mood categories. For each song, assign ONE mood from this list: {', '.join(moods)}

Songs:
{song_list}

Respond with a JSON object where keys are mood names and values are arrays of song numbers (1-indexed).
Example format: {{"{moods[0]}": [1, 5, 12], "{moods[1]}": [2, 3, 8]}}

Only include songs you're confident about. Skip songs you don't recognize.
Respond ONLY with valid JSON, no other text."""

        try:
            response = await self.complete(prompt, max_tokens=2048, temperature=0.2)
            mood_assignments = self._parse_json_response(response)

            # Convert song numbers to song IDs
            result: Dict[str, List[str]] = {mood: [] for mood in moods}
            for mood, song_nums in mood_assignments.items():
                mood_lower = mood.lower()
                # Match against mood list (case-insensitive, partial match for LLM flexibility)
                matched_mood = None
                for m in moods:
                    if m.lower() == mood_lower or mood_lower in m.lower() or m.lower() in mood_lower:
                        matched_mood = m
                        break
                if matched_mood is None:
                    continue
                for num in song_nums:
                    idx = int(num) - 1  # Convert to 0-indexed
                    if 0 <= idx < len(songs):
                        result[matched_mood].append(songs[idx]["id"])

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return {mood: [] for mood in moods}
        except Exception as e:
            logger.error(f"Failed to classify songs: {e}")
            return {mood: [] for mood in moods}

    async def generate_description(self, playlist_name: str, songs: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate a 1-2 sentence description of a playlist's vibe.

        Args:
            playlist_name: Name of the playlist
            songs: List of song dicts in the playlist

        Returns:
            Description string, or None on failure
        """
        # Sample a subset of songs for the prompt
        sample = songs[:20]
        song_list = "\n".join([
            f'- "{s.get("title", "Unknown")}" by {s.get("artist", "Unknown")}'
            for s in sample
        ])

        prompt = f"""Here is a playlist called "{playlist_name}" with these songs:
{song_list}

Write a 1-2 sentence description of this playlist's vibe. Be evocative and specific, not generic. Don't mention specific song names or artists. Just describe the feeling.

Respond with the description only, no quotes or extra formatting."""

        try:
            response = await self.complete(prompt, max_tokens=128, temperature=0.7)
            description = response.strip().strip('"').strip("'")
            if description:
                logger.info(f"Generated description for '{playlist_name}': {description[:60]}...")
                return description
            return None
        except Exception as e:
            logger.error(f"Failed to generate description for '{playlist_name}': {e}")
            return None

    async def health_check(self) -> bool:
        """Check if the LLM server is accessible."""
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
