"""
Channel Repository

Database operations for Channel model.
"""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel
from app.db.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    """Repository for Channel model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Channel, session)

    async def create(
        self,
        name: str,
        display_title: str,
        description: Optional[str],
        created_by: Optional[UUID],
        qdrant_collection_name: str
    ) -> Channel:
        """
        Create a new channel.

        Args:
            name: Unique channel name (URL slug, immutable)
            display_title: Display title for the channel
            description: Optional channel description
            created_by: Optional UUID of admin who created the channel
            qdrant_collection_name: Sanitized Qdrant collection name

        Returns:
            Created Channel instance
        """
        return await super().create(
            name=name,
            display_title=display_title,
            description=description,
            created_by=created_by,
            qdrant_collection_name=qdrant_collection_name
        )

    async def get_by_name(self, name: str) -> Optional[Channel]:
        """
        Retrieve channel by unique name.

        Args:
            name: Channel name to search for

        Returns:
            Channel instance or None if not found
        """
        result = await self.session.execute(
            select(Channel).where(Channel.name == name)
        )
        return result.scalar_one_or_none()

    async def list_active(self, limit: int = 50, offset: int = 0) -> Tuple[List[Channel], int]:
        """
        List all active channels with pagination.

        Args:
            limit: Maximum number of channels to return
            offset: Number of channels to skip

        Returns:
            Tuple of (list of Channel instances, total count)
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(Channel).where(Channel.is_active == True)
        )
        total = count_result.scalar_one()

        # Get paginated results
        result = await self.session.execute(
            select(Channel)
            .where(Channel.is_active == True)
            .order_by(Channel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        channels = list(result.scalars().all())

        return channels, total

    async def list_all(self, limit: int = 50, offset: int = 0) -> Tuple[List[Channel], int]:
        """
        List all channels (including inactive) with pagination.

        Args:
            limit: Maximum number of channels to return
            offset: Number of channels to skip

        Returns:
            Tuple of (list of Channel instances, total count)
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(Channel)
        )
        total = count_result.scalar_one()

        # Get paginated results
        result = await self.session.execute(
            select(Channel)
            .order_by(Channel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        channels = list(result.scalars().all())

        return channels, total

    async def update(
        self,
        channel_id: UUID,
        display_title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Channel:
        """
        Update channel fields (name is immutable).

        Note: Passing None explicitly will set the field to None (clear it).
        Only way to skip updating a field is to not pass it at all, but this
        method signature doesn't support that pattern. In practice, both fields
        should be provided when calling update.

        Args:
            channel_id: UUID of channel to update
            display_title: New display title (or None to clear)
            description: New description (or None to clear)

        Returns:
            Updated Channel instance

        Raises:
            ValueError: If channel not found
        """
        channel = await self.get_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel with id {channel_id} not found")

        # Always update fields (even to None if explicitly passed)
        channel.display_title = display_title
        channel.description = description

        await self.session.flush()
        await self.session.refresh(channel)
        return channel

    async def soft_delete(self, channel_id: UUID) -> bool:
        """
        Soft delete a channel by setting is_active to False.

        Args:
            channel_id: UUID of channel to soft delete

        Returns:
            True if deleted, False if not found
        """
        channel = await self.get_by_id(channel_id)
        if not channel:
            return False

        channel.is_active = False
        await self.session.flush()
        return True

    async def reactivate(self, channel_id: UUID) -> bool:
        """
        Reactivate a soft-deleted channel by setting is_active to True.

        Args:
            channel_id: UUID of channel to reactivate

        Returns:
            True if reactivated, False if not found
        """
        channel = await self.get_by_id(channel_id)
        if not channel:
            return False

        channel.is_active = True
        await self.session.flush()
        return True
