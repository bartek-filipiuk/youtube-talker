"""Transcript service for fetching YouTube transcripts via SUPADATA API."""

import re
from typing import Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

from app.config import settings


class TranscriptService:
    """SUPADATA API client for fetching YouTube transcripts."""

    def __init__(self):
        """Initialize with SUPADATA credentials from settings."""
        self.api_key = settings.SUPADATA_API_KEY
        self.base_url = settings.SUPADATA_BASE_URL
        self.timeout = 30.0  # 30 seconds (SUPADATA can be slow for long videos)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def fetch_transcript(self, youtube_url: str) -> Dict:
        """
        Fetch transcript from SUPADATA API with retry logic.

        Args:
            youtube_url: YouTube URL (youtube.com/watch?v=ID or youtu.be/ID)

        Returns:
            {
                "youtube_video_id": str,
                "transcript_text": str,
                "metadata": {
                    "title": str,
                    "duration": int,
                    "language": str,
                    ...
                }
            }

        Raises:
            ValueError: If URL format is invalid
            httpx.HTTPError: If API request fails after retries

        Retry Strategy:
            - Max attempts: 3
            - Wait: Exponential backoff (2s, 4s, 8s)
            - Retry on: httpx.HTTPError, httpx.TimeoutException
        """
        video_id = self._extract_video_id(youtube_url)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transcript",
                json={"video_id": video_id},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "youtube_video_id": video_id,
            "transcript_text": data["transcript"],
            "metadata": data.get("metadata", {}),
        }

    def _extract_video_id(self, url: str) -> str:
        """
        Extract video ID from YouTube URL.

        Supports:
            - https://www.youtube.com/watch?v=VIDEO_ID
            - https://youtube.com/watch?v=VIDEO_ID
            - https://youtu.be/VIDEO_ID

        Args:
            url: YouTube URL

        Returns:
            Video ID (11-character string)

        Raises:
            ValueError: If URL doesn't match expected patterns
        """
        patterns = [
            r"(?:youtube\.com\/watch\?v=)([\w-]+)",
            r"(?:youtu\.be\/)([\w-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Invalid YouTube URL format: {url}")
