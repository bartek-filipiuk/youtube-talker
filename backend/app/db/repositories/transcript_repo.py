"""
Transcript Repository

Database operations for Transcript model.
"""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Transcript
from app.db.repositories.base import BaseRepository


class TranscriptRepository(BaseRepository[Transcript]):
    """Repository for Transcript model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Transcript, session)

    async def create(
        self,
        user_id: UUID,
        youtube_video_id: str,
        title: Optional[str],
        channel_name: Optional[str],
        duration: Optional[int],
        transcript_text: str,
        meta_data: dict = None,
    ) -> Transcript:
        """
        Create a new transcript.

        Args:
            user_id: User's UUID
            youtube_video_id: YouTube video ID
            title: Video title
            channel_name: Channel name
            duration: Video duration in seconds
            transcript_text: Full transcript text
            meta_data: Optional metadata dictionary

        Returns:
            Created Transcript instance
        """
        return await super().create(
            user_id=user_id,
            youtube_video_id=youtube_video_id,
            title=title,
            channel_name=channel_name,
            duration=duration,
            transcript_text=transcript_text,
            meta_data=meta_data or {},
        )

    async def get_by_video_id(
        self, user_id: UUID, youtube_video_id: str
    ) -> Optional[Transcript]:
        """
        Get transcript by YouTube video ID for a specific user.

        Args:
            user_id: User's UUID
            youtube_video_id: YouTube video ID

        Returns:
            Transcript instance or None if not found
        """
        result = await self.session.execute(
            select(Transcript).where(
                Transcript.user_id == user_id,
                Transcript.youtube_video_id == youtube_video_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> Tuple[List[Transcript], int]:
        """
        List transcripts for a user with optional pagination.

        Args:
            user_id: User's UUID
            limit: Maximum number of results to return (optional)
            offset: Number of results to skip (optional)

        Returns:
            Tuple of (list of Transcript instances, total count)
        """
        # Query for transcripts with pagination
        query = (
            select(Transcript)
            .where(Transcript.user_id == user_id)
            .order_by(Transcript.created_at.desc())
        )

        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)

        result = await self.session.execute(query)
        transcripts = list(result.scalars().all())

        # Query for total count
        count_query = select(func.count(Transcript.id)).where(
            Transcript.user_id == user_id
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        return transcripts, total

    async def delete_by_user(self, transcript_id: UUID, user_id: UUID) -> bool:
        """
        Delete a transcript if it belongs to the user.

        Args:
            transcript_id: Transcript's UUID
            user_id: User's UUID

        Returns:
            True if deleted, False if not found or not owned by user
        """
        # Get transcript and verify ownership
        transcript = await self.get_by_id(transcript_id)
        if not transcript or transcript.user_id != user_id:
            return False

        # Delete transcript (chunks will cascade due to relationship config)
        await self.session.delete(transcript)
        await self.session.flush()
        return True

    async def get_by_youtube_video_id(
        self,
        youtube_video_id: str,
    ) -> Optional[Transcript]:
        """
        Get transcript by YouTube video ID (first match, any user).

        Used for channel video management to check if a transcript
        already exists in the system.

        Args:
            youtube_video_id: YouTube video ID

        Returns:
            Transcript instance or None if not found
        """
        result = await self.session.execute(
            select(Transcript)
            .where(Transcript.youtube_video_id == youtube_video_id)
            .limit(1)
        )
        return result.scalar_one_or_none()
