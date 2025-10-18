"""
Chunk Repository

Database operations for Chunk model.
"""

from typing import List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.db.repositories.base import BaseRepository


class ChunkRepository(BaseRepository[Chunk]):
    """Repository for Chunk model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Chunk, session)

    async def create_many(self, chunks_data: List[dict]) -> List[Chunk]:
        """
        Create multiple chunks at once.

        Args:
            chunks_data: List of dictionaries with chunk data

        Returns:
            List of created Chunk instances
        """
        chunks = [Chunk(**data) for data in chunks_data]
        self.session.add_all(chunks)
        await self.session.flush()
        for chunk in chunks:
            await self.session.refresh(chunk)
        return chunks

    async def get_by_ids(self, chunk_ids: List[UUID]) -> List[Chunk]:
        """
        Get multiple chunks by their IDs.

        Args:
            chunk_ids: List of chunk UUIDs

        Returns:
            List of Chunk instances
        """
        result = await self.session.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        )
        return list(result.scalars().all())

    async def list_by_transcript(self, transcript_id: UUID) -> List[Chunk]:
        """
        List all chunks for a transcript, ordered by chunk_index.

        Args:
            transcript_id: Transcript's UUID

        Returns:
            List of Chunk instances
        """
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.transcript_id == transcript_id)
            .order_by(Chunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def delete_by_transcript(self, transcript_id: UUID) -> int:
        """
        Delete all chunks for a transcript.

        Args:
            transcript_id: Transcript's UUID

        Returns:
            Number of chunks deleted
        """
        result = await self.session.execute(
            delete(Chunk).where(Chunk.transcript_id == transcript_id)
        )
        await self.session.flush()
        return result.rowcount
