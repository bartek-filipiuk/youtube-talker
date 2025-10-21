"""Transcript service for fetching YouTube transcripts via SUPADATA API."""

import logging
import re
import uuid
from typing import Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.chunk_repo import ChunkRepository
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


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

    async def ingest_transcript(
        self,
        youtube_url: str,
        user_id: str,
        db_session: AsyncSession,
    ) -> Dict:
        """
        Full ingestion pipeline orchestration.

        Steps:
            1. Fetch transcript from SUPADATA
            2. Check for duplicate (by youtube_video_id + user_id)
            3. Save transcript to PostgreSQL
            4. Chunk the transcript text
            5. Generate embeddings for chunks
            6. Save chunks to PostgreSQL
            7. Upsert vectors to Qdrant

        Args:
            youtube_url: YouTube URL to ingest
            user_id: User ID who owns this transcript
            db_session: Active database session

        Returns:
            {
                "transcript_id": str,
                "youtube_video_id": str,
                "chunk_count": int,
                "metadata": dict
            }

        Raises:
            ValueError: If video already ingested (duplicate)
            Exception: If pipeline fails (partial data kept in DB until rollback)

        Transaction Strategy (Option A - Simple):
            - Single try-except block
            - Rollback everything if failure occurs before Qdrant
            - Qdrant upsert is best-effort (log error, don't raise)
        """
        logger.info(f"Starting ingestion for user_id={user_id}, url={youtube_url}")

        try:
            # Step 1: Fetch transcript from SUPADATA
            logger.info("Step 1/7: Fetching transcript from SUPADATA")
            transcript_data = await self.fetch_transcript(youtube_url)
            youtube_video_id = transcript_data["youtube_video_id"]
            transcript_text = transcript_data["transcript_text"]
            metadata = transcript_data["metadata"]
            logger.info(
                f"✓ Fetched transcript for video_id={youtube_video_id} "
                f"({len(transcript_text)} chars)"
            )

            # Step 2: Check for duplicate
            logger.info("Step 2/7: Checking for duplicate transcript")
            transcript_repo = TranscriptRepository(db_session)
            existing = await transcript_repo.get_by_video_id(user_id, youtube_video_id)
            if existing:
                raise ValueError(
                    f"Transcript already exists for video_id={youtube_video_id}, "
                    f"user_id={user_id}"
                )
            logger.info("✓ No duplicate found")

            # Step 3: Save transcript to PostgreSQL
            logger.info("Step 3/7: Saving transcript to PostgreSQL")
            transcript = await transcript_repo.create(
                user_id=user_id,
                youtube_video_id=youtube_video_id,
                title=metadata.get("title"),
                channel_name=metadata.get("channel", metadata.get("channel_name")),
                duration=metadata.get("duration"),
                transcript_text=transcript_text,
                meta_data=metadata,
            )
            transcript_id = str(transcript.id)
            logger.info(f"✓ Saved transcript with id={transcript_id}")

            # Step 4: Chunk the transcript
            logger.info("Step 4/7: Chunking transcript text")
            chunking_service = ChunkingService(
                chunk_size=settings.CHUNK_SIZE,
                overlap_percent=settings.CHUNK_OVERLAP_PERCENT,
            )
            chunks = chunking_service.chunk_text(transcript_text)
            logger.info(f"✓ Created {len(chunks)} chunks")

            # Step 5: Generate embeddings
            logger.info("Step 5/7: Generating embeddings for chunks")
            embedding_service = EmbeddingService()
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await embedding_service.generate_embeddings(chunk_texts)
            logger.info(f"✓ Generated {len(embeddings)} embeddings")

            # Step 6: Save chunks to PostgreSQL
            logger.info("Step 6/7: Saving chunks to PostgreSQL")
            chunk_repo = ChunkRepository(db_session)
            chunks_data = [
                {
                    "id": str(uuid.uuid4()),
                    "transcript_id": transcript_id,
                    "user_id": user_id,
                    "chunk_index": chunk["index"],
                    "chunk_text": chunk["text"],
                    "token_count": chunk["token_count"],
                }
                for chunk in chunks
            ]
            saved_chunks = await chunk_repo.create_many(chunks_data)
            logger.info(f"✓ Saved {len(saved_chunks)} chunks to PostgreSQL")

            # Commit PostgreSQL transaction before Qdrant
            await db_session.commit()
            logger.info("✓ PostgreSQL transaction committed")

            # Step 7: Upsert vectors to Qdrant (best-effort)
            logger.info("Step 7/7: Upserting vectors to Qdrant")
            try:
                qdrant_service = QdrantService()
                chunk_ids = [chunk["id"] for chunk in chunks_data]
                chunk_indices = [chunk["chunk_index"] for chunk in chunks_data]

                await qdrant_service.upsert_chunks(
                    chunk_ids=chunk_ids,
                    vectors=embeddings,
                    user_id=user_id,
                    youtube_video_id=youtube_video_id,
                    chunk_indices=chunk_indices,
                    chunk_texts=chunk_texts,
                )
                logger.info(f"✓ Upserted {len(chunk_ids)} vectors to Qdrant")
            except Exception as e:
                # Qdrant is best-effort - log error but don't fail
                logger.error(
                    f"⚠ Qdrant upsert failed (data saved in PostgreSQL): {e}",
                    exc_info=True,
                )

            logger.info(
                f"✓✓✓ Ingestion complete for video_id={youtube_video_id} "
                f"({len(chunks)} chunks)"
            )

            return {
                "transcript_id": transcript_id,
                "youtube_video_id": youtube_video_id,
                "chunk_count": len(chunks),
                "metadata": metadata,
            }

        except ValueError as e:
            # Duplicate or validation error - don't rollback
            await db_session.rollback()
            logger.warning(f"Validation error during ingestion: {e}")
            raise
        except Exception as e:
            # Unexpected error - rollback everything
            await db_session.rollback()
            logger.error(f"✗ Ingestion failed, rolled back: {e}", exc_info=True)
            raise

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
