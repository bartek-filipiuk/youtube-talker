"""
Transcript Repository

Database operations for Transcript model.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
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

    async def list_by_user(self, user_id: UUID) -> List[Transcript]:
        """
        List all transcripts for a user.

        Args:
            user_id: User's UUID

        Returns:
            List of Transcript instances
        """
        result = await self.session.execute(
            select(Transcript)
            .where(Transcript.user_id == user_id)
            .order_by(Transcript.created_at.desc())
        )
        return list(result.scalars().all())
