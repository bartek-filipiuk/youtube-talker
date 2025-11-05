"""Qdrant service for vector database operations."""

import re
from typing import List, Dict, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http import exceptions as qdrant_exceptions

from app.config import settings


class QdrantService:
    """Qdrant vector database client for chunk storage and search."""

    COLLECTION_NAME = "youtube_chunks"
    VECTOR_SIZE = 1536  # OpenAI text-embedding-3-small dimension

    def __init__(self):
        """Initialize async Qdrant client."""
        self.client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
        )

    @staticmethod
    def sanitize_collection_name(name: str) -> str:
        """
        Sanitize channel name for use as Qdrant collection name.

        Qdrant collection name requirements:
        - Must start with letter or underscore
        - Can contain only: letters, numbers, underscores, hyphens
        - Length: 1-255 characters

        Sanitization process:
        1. Convert to lowercase
        2. Replace spaces and special chars with underscore
        3. Remove consecutive underscores
        4. Ensure starts with letter/underscore
        5. Truncate to 255 chars

        Args:
            name: Raw channel name (e.g., "Python Basics!", "Machine Learning 101")

        Returns:
            Sanitized collection name (e.g., "python_basics", "machine_learning_101")

        Examples:
            >>> QdrantService.sanitize_collection_name("Python Basics")
            'python_basics'
            >>> QdrantService.sanitize_collection_name("123 Start")
            '_123_start'
        """
        # Convert to lowercase
        sanitized = name.lower()

        # Replace spaces and special characters with underscores
        sanitized = re.sub(r'[^\w\-]', '_', sanitized)

        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        # Ensure starts with letter or underscore (prepend if starts with number)
        if sanitized and not re.match(r'^[a-z_]', sanitized):
            sanitized = '_' + sanitized

        # Fallback if empty
        if not sanitized:
            sanitized = 'channel'

        # Truncate to 255 characters
        sanitized = sanitized[:255]

        return sanitized

    async def create_collection(self) -> None:
        """
        Create youtube_chunks collection with indexes.

        Idempotent: No-op if collection already exists.

        Collection Config:
            - Vectors: 1536-dim, cosine distance
            - Payload indexes: user_id (keyword), youtube_video_id (keyword)
        """
        # Check if collection exists
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if self.COLLECTION_NAME in collection_names:
            return  # Collection already exists

        # Create collection
        await self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=self.VECTOR_SIZE, distance=models.Distance.COSINE
            ),
        )

        # Create payload indexes for filtering
        await self.client.create_payload_index(
            collection_name=self.COLLECTION_NAME,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        await self.client.create_payload_index(
            collection_name=self.COLLECTION_NAME,
            field_name="youtube_video_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    async def create_channel_collection(self, collection_name: str) -> None:
        """
        Create a channel-specific Qdrant collection with indexes.

        Idempotent: No-op if collection already exists.

        Collection Config:
            - Vectors: 1536-dim, cosine distance
            - Payload indexes: channel_id (keyword), youtube_video_id (keyword)

        Args:
            collection_name: Sanitized collection name (e.g., "channel_python_basics")

        Note: Call sanitize_collection_name() before passing collection_name
        """
        # Check if collection exists
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if collection_name in collection_names:
            return  # Collection already exists

        # Create collection
        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=self.VECTOR_SIZE, distance=models.Distance.COSINE
            ),
        )

        # Create payload indexes for filtering
        await self.client.create_payload_index(
            collection_name=collection_name,
            field_name="channel_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

        await self.client.create_payload_index(
            collection_name=collection_name,
            field_name="youtube_video_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((qdrant_exceptions.UnexpectedResponse,)),
    )
    async def upsert_chunks(
        self,
        chunk_ids: List[str],
        vectors: List[List[float]],
        user_id: str,
        youtube_video_id: str,
        chunk_indices: List[int],
        chunk_texts: List[str],
        collection_name: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        """
        Batch upsert chunks to Qdrant with retry logic.

        Args:
            chunk_ids: List of chunk UUIDs (from PostgreSQL)
            vectors: List of 1536-dim embeddings
            user_id: User UUID (for filtering - used for user collections)
            youtube_video_id: YouTube video ID (for filtering)
            chunk_indices: Chunk sequence numbers (0, 1, 2, ...)
            chunk_texts: List of chunk text content (for RAG retrieval)
            collection_name: Optional collection name (defaults to youtube_chunks)
            channel_id: Optional channel UUID (for channel collections)

        Creates points with payload:
            User collection:
            {
                "chunk_id": str,
                "user_id": str,
                "youtube_video_id": str,
                "chunk_index": int,
                "chunk_text": str
            }

            Channel collection:
            {
                "chunk_id": str,
                "channel_id": str,
                "youtube_video_id": str,
                "chunk_index": int,
                "chunk_text": str
            }

        Note: chunk_id is used as both point ID and in payload

        Raises:
            qdrant_exceptions.UnexpectedResponse: If upsert fails after retries
        """
        # Use default collection if not specified
        target_collection = collection_name or self.COLLECTION_NAME

        # Build payload based on collection type
        points = []
        for chunk_id, vector, chunk_index, chunk_text in zip(
            chunk_ids, vectors, chunk_indices, chunk_texts, strict=True
        ):
            payload = {
                "chunk_id": chunk_id,
                "youtube_video_id": youtube_video_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
            }

            # Add either user_id or channel_id
            if channel_id:
                payload["channel_id"] = channel_id
            else:
                payload["user_id"] = user_id

            points.append(
                models.PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload=payload,
                )
            )

        await self.client.upsert(collection_name=target_collection, points=points)

    async def search(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int = 12,
        youtube_video_id: Optional[str] = None,
        collection_name: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Semantic search with user/channel ID filtering.

        Args:
            query_vector: 1536-dim query embedding
            user_id: Filter by user (used for user collections)
            top_k: Number of results (default: 12 from config)
            youtube_video_id: Optional filter by specific video
            collection_name: Optional collection name (defaults to youtube_chunks)
            channel_id: Optional channel UUID (for channel collections)

        Returns:
            List of dicts sorted by score (descending):
            [
                {
                    "chunk_id": "uuid-string",
                    "score": 0.95,
                    "payload": {
                        "chunk_id": "uuid-string",
                        "user_id": "user-uuid" OR "channel_id": "channel-uuid",
                        "youtube_video_id": "VIDEO_ID",
                        "chunk_index": 0
                    }
                },
                ...
            ]

        Filter Logic:
            - User collection: filter by user_id
            - Channel collection: filter by channel_id
            - Optionally filter by youtube_video_id (single video search)
        """
        # Use default collection if not specified
        target_collection = collection_name or self.COLLECTION_NAME

        # Build filter conditions based on collection type
        must_conditions = []
        if channel_id:
            must_conditions.append(
                models.FieldCondition(
                    key="channel_id", match=models.MatchValue(value=channel_id)
                )
            )
        else:
            must_conditions.append(
                models.FieldCondition(
                    key="user_id", match=models.MatchValue(value=user_id)
                )
            )

        if youtube_video_id:
            must_conditions.append(
                models.FieldCondition(
                    key="youtube_video_id",
                    match=models.MatchValue(value=youtube_video_id),
                )
            )

        query_filter = models.Filter(must=must_conditions)

        # Perform search
        results = await self.client.search(
            collection_name=target_collection,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )

        # Format results
        formatted_results = [
            {
                "chunk_id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]

        return formatted_results

    async def delete_chunks(
        self, chunk_ids: List[str], collection_name: Optional[str] = None
    ) -> None:
        """
        Delete chunks by IDs.

        Args:
            chunk_ids: List of chunk UUIDs to delete
            collection_name: Optional collection name (defaults to youtube_chunks)

        Use Case: Clean up when transcript is deleted
        """
        # Use default collection if not specified
        target_collection = collection_name or self.COLLECTION_NAME

        await self.client.delete(
            collection_name=target_collection,
            points_selector=models.PointIdsList(points=chunk_ids),
        )

    async def health_check(self) -> bool:
        """
        Verify Qdrant connection.

        Returns:
            True if connected, False otherwise

        Used by health check endpoint.
        """
        try:
            collections = await self.client.get_collections()
            return True
        except Exception:
            return False
