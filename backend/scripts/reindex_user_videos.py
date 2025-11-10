"""
Re-index user videos to Qdrant.

This script re-generates embeddings and indexes chunks for a specific user.
Useful when Qdrant embeddings are missing or need to be refreshed.
"""

import asyncio
import sys
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.db.models import Chunk, Transcript
from app.db.session import AsyncSessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService


async def reindex_user_videos(user_id: str):
    """
    Re-index all videos for a user.

    Args:
        user_id: User UUID string
    """
    user_uuid = UUID(user_id)
    logger.info(f"Starting re-indexing for user: {user_id}")

    # Initialize services
    embedding_service = EmbeddingService()
    qdrant_service = QdrantService()

    # Get all transcripts for user
    async with AsyncSessionLocal() as session:
        query = select(Transcript).where(Transcript.user_id == user_uuid)
        result = await session.execute(query)
        transcripts = list(result.scalars().all())

        logger.info(f"Found {len(transcripts)} videos for user")

        for idx, transcript in enumerate(transcripts, 1):
            logger.info(
                f"[{idx}/{len(transcripts)}] Processing video: {transcript.title} "
                f"(ID: {transcript.youtube_video_id})"
            )

            # Get all chunks for this transcript
            chunk_query = select(Chunk).where(
                Chunk.transcript_id == transcript.id
            ).order_by(Chunk.chunk_index)
            chunk_result = await session.execute(chunk_query)
            chunks = list(chunk_result.scalars().all())

            if not chunks:
                logger.warning(f"  No chunks found for video {transcript.youtube_video_id}")
                continue

            logger.info(f"  Found {len(chunks)} chunks")

            # Extract chunk data
            chunk_ids = [str(chunk.id) for chunk in chunks]
            chunk_texts = [chunk.chunk_text for chunk in chunks]
            chunk_indices = [chunk.chunk_index for chunk in chunks]

            # Generate embeddings
            logger.info(f"  Generating embeddings for {len(chunk_texts)} chunks...")
            embeddings = await embedding_service.generate_embeddings(
                chunk_texts,
                user_id=user_id
            )

            logger.info(f"  Generated {len(embeddings)} embeddings")

            # Upsert to Qdrant
            logger.info(f"  Upserting to Qdrant...")
            await qdrant_service.upsert_chunks(
                chunk_ids=chunk_ids,
                vectors=embeddings,
                user_id=user_id,
                youtube_video_id=transcript.youtube_video_id,
                chunk_indices=chunk_indices,
                chunk_texts=chunk_texts
            )

            logger.success(
                f"  ✓ Indexed {len(chunks)} chunks for video: {transcript.title}"
            )

    logger.success(f"✅ Re-indexing complete! Processed {len(transcripts)} videos")


async def verify_indexing(user_id: str):
    """Verify chunks were indexed in Qdrant."""
    import aiohttp

    logger.info(f"Verifying indexing for user: {user_id}")

    url = "http://localhost:6333/collections/youtube_chunks/points/scroll"
    payload = {
        "filter": {
            "must": [
                {"key": "user_id", "match": {"value": user_id}}
            ]
        },
        "limit": 10
    }

    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(url, json=payload) as response:
            data = await response.json()
            points = data.get("result", {}).get("points", [])

            if points:
                logger.success(f"✅ Found {len(points)} indexed chunks in Qdrant")
                logger.info(f"Sample point: {points[0]['payload']}")
                return True
            else:
                logger.error("❌ No chunks found in Qdrant!")
                return False


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/reindex_user_videos.py <user_id>")
        print("Example: python scripts/reindex_user_videos.py 20f6ef9f-fca5-423a-9b0d-df2e379d1706")
        sys.exit(1)

    user_id = sys.argv[1]

    try:
        UUID(user_id)  # Validate UUID format
    except ValueError:
        print(f"Error: Invalid UUID format: {user_id}")
        sys.exit(1)

    await reindex_user_videos(user_id)
    await verify_indexing(user_id)


if __name__ == "__main__":
    asyncio.run(main())
