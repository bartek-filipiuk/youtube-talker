"""
Channel Conversation Repository

Database operations for ChannelConversation model (per-user channel conversations).
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChannelConversation
from app.db.repositories.base import BaseRepository


class ChannelConversationRepository(BaseRepository[ChannelConversation]):
    """Repository for ChannelConversation model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ChannelConversation, session)

    async def get_or_create(
        self,
        channel_id: UUID,
        user_id: UUID
    ) -> ChannelConversation:
        """
        Get existing conversation or create new one for channel and user.

        Args:
            channel_id: UUID of the channel
            user_id: UUID of the user

        Returns:
            ChannelConversation instance (existing or newly created)
        """
        # Try to get existing conversation
        result = await self.session.execute(
            select(ChannelConversation)
            .where(
                ChannelConversation.channel_id == channel_id,
                ChannelConversation.user_id == user_id
            )
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            return conversation

        # Create new conversation if none exists
        return await super().create(
            channel_id=channel_id,
            user_id=user_id
        )

    async def get_by_id(self, conversation_id: UUID) -> Optional[ChannelConversation]:
        """
        Retrieve conversation by ID.

        Args:
            conversation_id: UUID of the conversation

        Returns:
            ChannelConversation instance or None if not found
        """
        result = await self.session.execute(
            select(ChannelConversation)
            .where(ChannelConversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ChannelConversation], int]:
        """
        List all conversations for a user with pagination.

        Conversations are ordered by updated_at DESC (most recent first).

        Args:
            user_id: UUID of the user
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            Tuple of (list of ChannelConversation instances, total count)
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(ChannelConversation)
            .where(ChannelConversation.user_id == user_id)
        )
        total = count_result.scalar_one()

        # Get paginated results ordered by updated_at DESC
        result = await self.session.execute(
            select(ChannelConversation)
            .where(ChannelConversation.user_id == user_id)
            .order_by(ChannelConversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        conversations = list(result.scalars().all())

        return conversations, total

    async def update_timestamp(self, conversation_id: UUID) -> None:
        """
        Update the updated_at timestamp for a conversation.

        This is called when a new message is added to the conversation
        to keep it at the top of the user's conversation list.

        Args:
            conversation_id: UUID of the conversation to update
        """
        conversation = await self.get_by_id(conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
