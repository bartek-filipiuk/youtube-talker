"""Embedding service for generating text embeddings via OpenAI API."""

from typing import List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

from app.config import settings


class EmbeddingService:
    """OpenAI embeddings API client with automatic batching."""

    def __init__(self):
        """Initialize with OpenAI credentials from settings."""
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.base_url = "https://api.openai.com/v1"
        self.batch_size = 100  # Max texts per API request
        self.timeout = 30.0

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for list of texts with automatic batching.

        Args:
            texts: List of text strings to embed (can be any length)

        Returns:
            List of 1024-dimensional vectors (one per input text)
            Example: [[0.1, 0.2, ..., 0.5], [0.3, 0.1, ..., 0.8]]

        Raises:
            httpx.HTTPError: If API request fails after retries

        Retry Strategy:
            - Max attempts: 3
            - Wait: Exponential backoff (2s, 4s, 8s)
            - Retry on: httpx.HTTPError, httpx.TimeoutException

        Performance:
            - Batches requests in groups of 100 texts
            - Sequential processing for MVP (no parallel batching)
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches of self.batch_size
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a single batch (≤ 100 texts).

        Internal method with retry decorator.

        Args:
            texts: List of text strings (max 100)

        Returns:
            List of 1024-dimensional embedding vectors

        Raises:
            httpx.HTTPError: If API request fails after retries
            httpx.TimeoutException: If request times out after retries
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float",
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

        # Extract embeddings from response
        # Response format: {"data": [{"embedding": [...], "index": 0}, ...]}
        embeddings = [item["embedding"] for item in data["data"]]

        return embeddings
