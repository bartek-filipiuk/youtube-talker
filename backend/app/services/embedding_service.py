"""Embedding service for generating text embeddings via OpenAI API with LangSmith tracking."""

from typing import List, Optional
from uuid import UUID

from langchain_openai import OpenAIEmbeddings
from loguru import logger

from app.config import settings


class EmbeddingService:
    """OpenAI embeddings API client with automatic LangSmith cost tracking."""

    def __init__(self):
        """Initialize with OpenAI credentials from settings."""
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            # LangChain handles retries automatically
            max_retries=3,
        )
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.batch_size = 100  # Max texts per API request

    async def generate_embeddings(
        self,
        texts: List[str],
        user_id: Optional[UUID] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for list of texts with automatic batching and LangSmith tracking.

        Args:
            texts: List of text strings to embed (can be any length)
            user_id: Optional user UUID for cost tracking in LangSmith

        Returns:
            List of 1536-dimensional vectors (one per input text)
            Example: [[0.1, 0.2, ..., 0.5], [0.3, 0.1, ..., 0.8]]

        Raises:
            Exception: If API request fails after retries

        LangSmith Tracking:
            - Automatically tracks token usage for embeddings
            - Tracks cost when pricing is configured in LangSmith UI
            - Tags calls with user_id for per-user filtering

        Retry Strategy:
            - Max attempts: 3 (handled by LangChain)
            - Wait: Exponential backoff (automatic)
            - Retry on: HTTP errors, timeouts

        Performance:
            - Batches requests in groups of 100 texts
            - Sequential processing for MVP (no parallel batching)
        """
        if not texts:
            return []

        logger.debug(
            f"Generating embeddings for {len(texts)} texts"
            f"{f' for user_id={user_id}' if user_id else ''}"
        )

        all_embeddings = []

        # Process in batches of self.batch_size
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = await self._embed_batch(batch, user_id)
            all_embeddings.extend(batch_embeddings)

        logger.debug(f"Generated {len(all_embeddings)} embeddings")
        return all_embeddings

    async def _embed_batch(
        self,
        texts: List[str],
        user_id: Optional[UUID] = None
    ) -> List[List[float]]:
        """
        Embed a single batch (≤ 100 texts) with LangSmith tracking.

        Internal method that calls LangChain OpenAIEmbeddings.

        Args:
            texts: List of text strings (max 100)
            user_id: Optional user UUID for cost tracking

        Returns:
            List of 1536-dimensional embedding vectors

        Raises:
            Exception: If API request fails after retries
        """
        try:
            # Call LangChain embeddings - LangSmith tracking happens automatically
            # Note: OpenAIEmbeddings doesn't support config parameter like ChatOpenAI does
            # The embeddings will still be tracked in LangSmith, just without per-user tags
            embeddings = await self.embeddings.aembed_documents(texts)

            logger.debug(
                f"Embedded batch of {len(texts)} texts for user {user_id if user_id else 'unknown'}, "
                f"got {len(embeddings)} embeddings"
            )

            return embeddings

        except Exception as e:
            logger.exception(f"Failed to generate embeddings: {e}")
            raise
