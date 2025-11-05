"""
Channel Video Repository

Database operations for ChannelVideo model (video-channel associations).
"""

from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ChannelVideo, Transcript
from app.db.repositories.base import BaseRepository


class ChannelVideoRepository(BaseRepository[ChannelVideo]):
    """Repository for ChannelVideo model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ChannelVideo, session)

    async def add_video(
        self,
        channel_id: UUID,
        transcript_id: UUID,
        added_by: Optional[UUID]
    ) -> ChannelVideo:
        """
        Add a video to a channel.

        Args:
            channel_id: UUID of the channel
            transcript_id: UUID of the transcript/video
            added_by: Optional UUID of user who added the video

        Returns:
            Created ChannelVideo instance

        Raises:
            IntegrityError: If video already exists in channel (unique constraint)
        """
        return await super().create(
            channel_id=channel_id,
            transcript_id=transcript_id,
            added_by=added_by
        )

    async def remove_video(
        self,
        channel_id: UUID,
        transcript_id: UUID
    ) -> bool:
        """
        Remove a video from a channel.

        Args:
            channel_id: UUID of the channel
            transcript_id: UUID of the transcript/video

        Returns:
            True if video was removed, False if not found
        """
        result = await self.session.execute(
            delete(ChannelVideo)
            .where(
                ChannelVideo.channel_id == channel_id,
                ChannelVideo.transcript_id == transcript_id
            )
        )
        return result.rowcount > 0

    async def list_by_channel(
        self,
        channel_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ChannelVideo], int]:
        """
        List all videos in a channel with pagination.

        Args:
            channel_id: UUID of the channel
            limit: Maximum number of videos to return
            offset: Number of videos to skip

        Returns:
            Tuple of (list of ChannelVideo instances, total count)
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(ChannelVideo)
            .where(ChannelVideo.channel_id == channel_id)
        )
        total = count_result.scalar_one()

        # Get paginated results with transcript relationship loaded
        result = await self.session.execute(
            select(ChannelVideo)
            .options(selectinload(ChannelVideo.transcript))
            .where(ChannelVideo.channel_id == channel_id)
            .order_by(ChannelVideo.added_at.desc())
            .limit(limit)
            .offset(offset)
        )
        videos = list(result.scalars().all())

        return videos, total

    async def get_latest_n(
        self,
        channel_id: UUID,
        n: int
    ) -> List[ChannelVideo]:
        """
        Get the N most recently added videos in a channel.

        Args:
            channel_id: UUID of the channel
            n: Number of videos to retrieve

        Returns:
            List of ChannelVideo instances (most recent first)
        """
        result = await self.session.execute(
            select(ChannelVideo)
            .options(selectinload(ChannelVideo.transcript))
            .where(ChannelVideo.channel_id == channel_id)
            .order_by(ChannelVideo.added_at.desc(), ChannelVideo.id.desc())
            .limit(n)
        )
        return list(result.scalars().all())

    async def count_by_channel(self, channel_id: UUID) -> int:
        """
        Count videos in a channel.

        Args:
            channel_id: UUID of the channel

        Returns:
            Total number of videos in the channel
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(ChannelVideo)
            .where(ChannelVideo.channel_id == channel_id)
        )
        return result.scalar_one()

    async def count_by_channels_batch(self, channel_ids: List[UUID]) -> Dict[UUID, int]:
        """
        Count videos for multiple channels in a single query (performance optimization).

        Args:
            channel_ids: List of channel UUIDs

        Returns:
            Dictionary mapping channel_id to video count (channels with 0 videos not included)

        Example:
            >>> counts = await repo.count_by_channels_batch([uuid1, uuid2, uuid3])
            >>> # {uuid1: 5, uuid2: 0, uuid3: 12}
        """
        if not channel_ids:
            return {}

        result = await self.session.execute(
            select(
                ChannelVideo.channel_id,
                func.count(ChannelVideo.id).label("count")
            )
            .where(ChannelVideo.channel_id.in_(channel_ids))
            .group_by(ChannelVideo.channel_id)
        )

        # Convert to dict, defaulting to 0 for channels not in result
        counts = {row.channel_id: row.count for row in result}

        # Ensure all requested channels are in the result (even if 0 videos)
        return {channel_id: counts.get(channel_id, 0) for channel_id in channel_ids}

    async def video_exists(
        self,
        channel_id: UUID,
        transcript_id: UUID
    ) -> bool:
        """
        Check if a video exists in a channel.

        Args:
            channel_id: UUID of the channel
            transcript_id: UUID of the transcript/video

        Returns:
            True if video exists in channel, False otherwise
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(ChannelVideo)
            .where(
                ChannelVideo.channel_id == channel_id,
                ChannelVideo.transcript_id == transcript_id
            )
        )
        return result.scalar_one() > 0
