"""
Message Repository

Database operations for Message model.
"""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message
from app.db.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for Message model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def create(
        self, conversation_id: UUID, role: str, content: str, meta_data: dict = None
    ) -> Message:
        """
        Create a new message.

        Args:
            conversation_id: Conversation's UUID
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            meta_data: Optional metadata dictionary

        Returns:
            Created Message instance
        """
        return await super().create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            meta_data=meta_data or {},
        )

    async def list_by_conversation(
        self, conversation_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[Message]:
        """
        List messages for a conversation, ordered by creation time.

        Args:
            conversation_id: Conversation's UUID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of Message instances
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_last_n(self, conversation_id: UUID, n: int = 10) -> List[Message]:
        """
        Get the last N messages from a conversation.

        Args:
            conversation_id: Conversation's UUID
            n: Number of recent messages to retrieve

        Returns:
            List of Message instances (most recent last)
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(n)
        )
        # Reverse to get oldest first
        return list(reversed(list(result.scalars().all())))
