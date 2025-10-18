"""
Conversation Repository

Database operations for Conversation model.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
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
