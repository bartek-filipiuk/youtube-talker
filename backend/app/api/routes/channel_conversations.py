"""
Channel Conversation API Routes

Authenticated endpoints for managing user's channel conversations.
All endpoints require authentication and enforce ownership.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.services.channel_service import ChannelService
from app.db.repositories.message_repo import MessageRepository
from app.core.errors import (
    ChannelNotFoundError,
    ConversationNotFoundError,
    ConversationAccessDeniedError,
)
from app.schemas.channel_public import (
    ChannelConversationResponse,
    ChannelConversationDetailResponse,
    ChannelConversationListResponse,
)
from app.schemas.conversation import MessageResponse

router = APIRouter(prefix="/api/channels", tags=["channel-conversations"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/{channel_id}/conversations", response_model=ChannelConversationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def get_or_create_conversation(
    request: Request,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationResponse:
    """
    Get or create user's conversation with a channel.

    **Authentication Required**

    Returns existing conversation if user already has one with this channel.
    Creates new conversation if first time chatting with channel.
    This endpoint is idempotent - always returns 201 Created.

    Rate Limit: 20 requests/minute

    Args:
        channel_id: UUID of the channel
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelConversationResponse with conversation details

    Raises:
        401: Not authenticated
        404: Channel not found or deleted

    Example:
        >>> POST /api/channels/550e8400-e29b-41d4-a716-446655440000/conversations
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "id": "750e8400-e29b-41d4-a716-446655440002",
        >>>   "channel_id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "user_id": "850e8400-e29b-41d4-a716-446655440003",
        >>>   "channel_name": "python-tutorials",
        >>>   "channel_display_title": "Python Tutorials",
        >>>   "created_at": "2025-01-15T10:30:00Z",
        >>>   "updated_at": "2025-01-15T10:30:00Z"
        >>> }
    """
    service = ChannelService(db)

    try:
        conversation = await service.get_or_create_channel_conversation(
            channel_id=channel_id,
            user_id=current_user.id,
        )
        await db.commit()
        await db.refresh(conversation)

        # Get channel details for response
        channel = await service.get_public_channel(channel_id)

        logger.info(
            f"User {current_user.id} got/created conversation {conversation.id} "
            f"with channel {channel_id}"
        )

        return ChannelConversationResponse(
            id=conversation.id,
            channel_id=conversation.channel_id,
            user_id=conversation.user_id,
            channel_name=channel.name,
            channel_display_title=channel.display_title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/conversations", response_model=ChannelConversationListResponse)
@limiter.limit("60/minute")
async def list_channel_conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Maximum conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationListResponse:
    """
    List all channel conversations for authenticated user.

    **Authentication Required**

    Returns conversations ordered by updated_at DESC (most recent first).
    Includes channel metadata (name, display_title).
    Supports pagination via limit/offset parameters.

    Rate Limit: 60 requests/minute

    Args:
        limit: Maximum number of conversations (1-100, default: 50)
        offset: Number of conversations to skip (default: 0)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelConversationListResponse with paginated conversation list

    Raises:
        401: Not authenticated

    Example:
        >>> GET /api/channels/conversations?limit=20&offset=0
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversations": [...],
        >>>   "total": 5,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """
    service = ChannelService(db)

    conversations, total = await service.list_user_channel_conversations(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    # Enrich with channel metadata
    conversation_responses: List[ChannelConversationResponse] = []
    for conv in conversations:
        # conv has channel relationship loaded
        conversation_responses.append(
            ChannelConversationResponse(
                id=conv.id,
                channel_id=conv.channel_id,
                user_id=conv.user_id,
                channel_name=conv.channel.name,
                channel_display_title=conv.channel.display_title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )

    logger.info(
        f"User {current_user.id} listed {len(conversation_responses)} channel conversations "
        f"(limit={limit}, offset={offset})"
    )

    return ChannelConversationListResponse(
        conversations=conversation_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/conversations/{conversation_id}", response_model=ChannelConversationDetailResponse)
@limiter.limit("60/minute")
async def get_conversation_detail(
    request: Request,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationDetailResponse:
    """
    Get channel conversation details with all messages.

    **Authentication Required**

    Returns conversation metadata + all messages in chronological order.
    Verifies user owns the conversation before returning data.

    Rate Limit: 60 requests/minute

    Args:
        conversation_id: UUID of the conversation
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelConversationDetailResponse with conversation + messages

    Raises:
        401: Not authenticated
        403: User doesn't own this conversation
        404: Conversation not found

    Example:
        >>> GET /api/channels/conversations/750e8400-e29b-41d4-a716-446655440002
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversation": {...},
        >>>   "messages": [
        >>>     {"role": "user", "content": "What is Python?", ...},
        >>>     {"role": "assistant", "content": "Python is...", ...}
        >>>   ]
        >>> }
    """
    service = ChannelService(db)
    message_repo = MessageRepository(db)

    try:
        # Get conversation with ownership verification
        conversation = await service.get_channel_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
        )

        # Get channel details
        channel = await service.get_public_channel(conversation.channel_id)

        # Get all messages
        messages = await message_repo.list_by_channel_conversation(conversation_id)

        logger.info(
            f"User {current_user.id} retrieved conversation {conversation_id} "
            f"with {len(messages)} messages"
        )

        return ChannelConversationDetailResponse(
            conversation=ChannelConversationResponse(
                id=conversation.id,
                channel_id=conversation.channel_id,
                user_id=conversation.user_id,
                channel_name=channel.name,
                channel_display_title=channel.display_title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            ),
            messages=[MessageResponse.model_validate(msg) for msg in messages],
        )
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConversationAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ChannelNotFoundError as e:
        # Channel might be deleted after conversation was created
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_conversation(
    request: Request,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete user's channel conversation and all messages.

    **Authentication Required**

    Verifies user owns the conversation before deletion.
    Cascade deletes all messages via database constraint.
    Returns 204 No Content on success.

    Rate Limit: 20 requests/minute

    Args:
        conversation_id: UUID of the conversation to delete
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        None (204 No Content)

    Raises:
        401: Not authenticated
        403: User doesn't own this conversation
        404: Conversation not found

    Example:
        >>> DELETE /api/channels/conversations/750e8400-e29b-41d4-a716-446655440002
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
    service = ChannelService(db)

    try:
        await service.delete_channel_conversation(
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        await db.commit()

        logger.info(f"User {current_user.id} deleted conversation {conversation_id}")
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConversationAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
