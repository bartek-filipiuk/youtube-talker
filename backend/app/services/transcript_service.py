"""Transcript service for fetching YouTube transcripts via SUPADATA SDK."""

import asyncio
from loguru import logger
import re
import uuid
from typing import Dict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from supadata import Supadata, SupadataError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.chunk_repo import ChunkRepository
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.config_service import ConfigService



class TranscriptService:
    """SUPADATA SDK client for fetching YouTube transcripts and metadata."""

    def __init__(self):
        """Initialize with SUPADATA SDK client."""
        self.client = Supadata(api_key=settings.SUPADATA_API_KEY)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(SupadataError),
    )
    async def fetch_transcript(self, youtube_url: str) -> Dict:
        """
        Fetch transcript and metadata from SUPADATA SDK with retry logic.

        Makes 2 API calls:
            1. supadata.youtube.video() - Get video metadata
            2. supadata.youtube.transcript() - Get transcript text

        Args:
            youtube_url: YouTube URL (youtube.com/watch?v=ID or youtu.be/ID)

        Returns:
            {
                "youtube_video_id": str,
                "transcript_text": str,
                "metadata": {
                    "title": str,
                    "description": str,
                    "duration": int,
                    "channel_id": str,
                    "channel_name": str,
                    "tags": list[str],
                    "thumbnail": str,
                    "upload_date": str,
                    "view_count": int,
                    "like_count": int,
                    "language": str,
                    "available_languages": list[str]
                }
            }

        Raises:
            ValueError: If URL format is invalid
            SupadataError: If API request fails after retries

        Retry Strategy:
            - Max attempts: 3
            - Wait: Exponential backoff (2s, 4s, 8s)
            - Retry on: SupadataError
        """
        video_id = self._extract_video_id(youtube_url)

        # Call 1: Fetch video metadata (run in thread pool to avoid blocking event loop)
        video = await asyncio.to_thread(self.client.youtube.video, id=video_id)

        # Call 2: Fetch transcript (run in thread pool to avoid blocking event loop)
        transcript = await asyncio.to_thread(
            self.client.youtube.transcript, video_id=video_id, text=True
        )

        # Extract channel info (can be dict or object)
        channel = video.channel
        channel_id = channel["id"] if isinstance(channel, dict) else getattr(channel, "id", None)
        channel_name = channel["name"] if isinstance(channel, dict) else getattr(channel, "name", "Unknown")

        return {
            "youtube_video_id": getattr(video, "id", video_id),
            "transcript_text": getattr(transcript, "content", ""),
            "metadata": {
                "title": getattr(video, "title", ""),
                "description": getattr(video, "description", ""),
                "duration": getattr(video, "duration", 0),
                "channel_id": channel_id,
                "channel_name": channel_name,
                "tags": getattr(video, "tags", []),
                "thumbnail": getattr(video, "thumbnail", ""),
                "upload_date": getattr(video, "uploadDate", getattr(video, "upload_date", "")),
                "view_count": getattr(video, "viewCount", getattr(video, "view_count", 0)),
                "like_count": getattr(video, "likeCount", getattr(video, "like_count", 0)),
                "language": getattr(transcript, "lang", "en"),
                "available_languages": getattr(transcript, "availableLangs", getattr(transcript, "available_langs", [])),
            },
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

            # Step 4: Load chunking config from database (via ConfigService)
            logger.info("Step 4/7: Loading chunking configuration")
            config_service = ConfigService(db_session)
            chunk_size = await config_service.get_config("rag.chunk_size", default=settings.CHUNK_SIZE)
            overlap_percent = await config_service.get_config("rag.chunk_overlap_percent", default=settings.CHUNK_OVERLAP_PERCENT)

            # Step 4.5: Chunk the transcript
            logger.info(f"Chunking transcript text (chunk_size={chunk_size}, overlap={overlap_percent}%)")
            chunking_service = ChunkingService(
                chunk_size=chunk_size,
                overlap_percent=overlap_percent,
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
                logger.exception(
                    f"⚠ Qdrant upsert failed (data saved in PostgreSQL): {e}"
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
            logger.exception(f"✗ Ingestion failed, rolled back: {e}")
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
