"""
Conversation Repository

Database operations for Conversation model.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation
from app.db.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for Conversation model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Conversation, session)

    async def create(self, user_id: UUID, title: Optional[str] = None) -> Conversation:
        """
        Create a new conversation.

        Args:
            user_id: User's UUID
            title: Optional conversation title

        Returns:
            Created Conversation instance
        """
        return await super().create(user_id=user_id, title=title)

    async def list_by_user(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        """
        List all conversations for a user, ordered by most recent.

        Args:
            user_id: User's UUID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip

        Returns:
            List of Conversation instances
        """
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """
        Count total conversations for a user.

        Args:
            user_id: User's UUID

        Returns:
            Total count of conversations
        """
        result = await self.session.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
        )
        return result.scalar() or 0

    async def get_latest_by_user(self, user_id: UUID) -> Optional[Conversation]:
        """
        Get the most recent conversation for a user (by updated_at).

        Args:
            user_id: User's UUID

        Returns:
            Most recent Conversation instance or None if user has no conversations
        """
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_title(self, conversation_id: UUID, title: str) -> Conversation:
        """
        Update conversation title.

        Args:
            conversation_id: Conversation UUID
            title: New title

        Returns:
            Updated Conversation instance

        Raises:
            ValueError: If conversation not found
        """
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.title = title
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation
