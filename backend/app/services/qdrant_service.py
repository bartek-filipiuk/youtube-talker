"""Qdrant service for vector database operations."""

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
    ) -> None:
        """
        Batch upsert chunks to Qdrant with retry logic.

        Args:
            chunk_ids: List of chunk UUIDs (from PostgreSQL)
            vectors: List of 1536-dim embeddings
            user_id: User UUID (for filtering)
            youtube_video_id: YouTube video ID (for filtering)
            chunk_indices: Chunk sequence numbers (0, 1, 2, ...)
            chunk_texts: List of chunk text content (for RAG retrieval)

        Creates points with payload:
            {
                "chunk_id": str,
                "user_id": str,
                "youtube_video_id": str,
                "chunk_index": int,
                "chunk_text": str
            }

        Note: chunk_id is used as both point ID and in payload

        Raises:
            qdrant_exceptions.UnexpectedResponse: If upsert fails after retries
        """
        points = [
            models.PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "chunk_id": chunk_id,
                    "user_id": user_id,
                    "youtube_video_id": youtube_video_id,
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                },
            )
            for chunk_id, vector, chunk_index, chunk_text in zip(
                chunk_ids, vectors, chunk_indices, chunk_texts
            )
        ]

        await self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)

    async def search(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int = 12,
        youtube_video_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Semantic search with user ID filtering.

        Args:
            query_vector: 1536-dim query embedding
            user_id: Filter by user (REQUIRED for data isolation)
            top_k: Number of results (default: 12 from config)
            youtube_video_id: Optional filter by specific video

        Returns:
            List of dicts sorted by score (descending):
            [
                {
                    "chunk_id": "uuid-string",
                    "score": 0.95,
                    "payload": {
                        "chunk_id": "uuid-string",
                        "user_id": "user-uuid",
                        "youtube_video_id": "VIDEO_ID",
                        "chunk_index": 0
                    }
                },
                ...
            ]

        Filter Logic:
            - ALWAYS filter by user_id (data isolation)
            - Optionally filter by youtube_video_id (single video search)
        """
        # Build filter conditions
        must_conditions = [
            models.FieldCondition(
                key="user_id", match=models.MatchValue(value=user_id)
            )
        ]

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
            collection_name=self.COLLECTION_NAME,
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

    async def delete_chunks(self, chunk_ids: List[str]) -> None:
        """
        Delete chunks by IDs.

        Args:
            chunk_ids: List of chunk UUIDs to delete

        Use Case: Clean up when transcript is deleted
        """
        await self.client.delete(
            collection_name=self.COLLECTION_NAME,
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
