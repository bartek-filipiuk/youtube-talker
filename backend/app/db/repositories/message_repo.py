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
        self,
        role: str,
        content: str,
        conversation_id: UUID = None,
        channel_conversation_id: UUID = None,
        meta_data: dict = None,
    ) -> Message:
        """
        Create a new message.

        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            conversation_id: Personal conversation's UUID (optional)
            channel_conversation_id: Channel conversation's UUID (optional)
            meta_data: Optional metadata dictionary

        Returns:
            Created Message instance

        Note:
            Exactly one of conversation_id or channel_conversation_id must be provided.
        """
        if not conversation_id and not channel_conversation_id:
            raise ValueError("Either conversation_id or channel_conversation_id must be provided")
        if conversation_id and channel_conversation_id:
            raise ValueError("Cannot specify both conversation_id and channel_conversation_id")

        return await super().create(
            conversation_id=conversation_id,
            channel_conversation_id=channel_conversation_id,
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

    async def get_last_n(
        self,
        n: int = 10,
        conversation_id: UUID = None,
        channel_conversation_id: UUID = None,
    ) -> List[dict]:
        """
        Get the last N messages from a conversation.

        Args:
            n: Number of recent messages to retrieve
            conversation_id: Personal conversation's UUID (optional)
            channel_conversation_id: Channel conversation's UUID (optional)

        Returns:
            List of message dicts with {role, content} (most recent last)

        Note:
            Exactly one of conversation_id or channel_conversation_id must be provided.
        """
        if not conversation_id and not channel_conversation_id:
            raise ValueError("Either conversation_id or channel_conversation_id must be provided")
        if conversation_id and channel_conversation_id:
            raise ValueError("Cannot specify both conversation_id and channel_conversation_id")

        query = select(Message).order_by(Message.created_at.desc()).limit(n)

        if conversation_id:
            query = query.where(Message.conversation_id == conversation_id)
        else:
            query = query.where(Message.channel_conversation_id == channel_conversation_id)

        result = await self.session.execute(query)
        messages = list(result.scalars().all())

        # Convert to dicts in async context to avoid greenlet issues
        # Reverse to get oldest first
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(messages)
        ]

    async def list_by_channel_conversation(
        self, channel_conversation_id: UUID
    ) -> List[Message]:
        """
        List all messages for a channel conversation in chronological order.

        Args:
            channel_conversation_id: UUID of channel conversation

        Returns:
            List of Message instances ordered by created_at ASC
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.channel_conversation_id == channel_conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
