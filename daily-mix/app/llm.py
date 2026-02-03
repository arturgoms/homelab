import httpx
import json
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

        # Format songs for the prompt
        song_list = "\n".join([
            f"{i+1}. \"{s.get('title', 'Unknown')}\" by {s.get('artist', 'Unknown')} (album: {s.get('album', 'Unknown')})"
            for i, s in enumerate(songs[:50])  # Limit to 50 songs per batch
        ])

        prompt = f"""Classify these songs into mood categories. For each song, assign ONE mood from this list: {', '.join(moods)}

Songs:
{song_list}

Respond with a JSON object where keys are mood names and values are arrays of song numbers (1-indexed).
Example format: {{"energetic": [1, 5, 12], "chill": [2, 3, 8], ...}}

Only include songs you're confident about. Skip songs you don't recognize.
Respond ONLY with valid JSON, no other text."""

        try:
            response = await self.complete(prompt, max_tokens=2048, temperature=0.2)

            # Parse JSON from response
            # Try to find JSON in the response (handle markdown code blocks)
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            mood_assignments = json.loads(json_str)

            # Convert song numbers to song IDs
            result: Dict[str, List[str]] = {mood: [] for mood in moods}
            for mood, song_nums in mood_assignments.items():
                mood_lower = mood.lower()
                if mood_lower not in result:
                    continue
                for num in song_nums:
                    idx = int(num) - 1  # Convert to 0-indexed
                    if 0 <= idx < len(songs):
                        result[mood_lower].append(songs[idx]["id"])

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            return {mood: [] for mood in moods}
        except Exception as e:
            logger.error(f"Failed to classify songs: {e}")
            return {mood: [] for mood in moods}

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
