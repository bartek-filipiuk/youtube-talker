"""
Conversation API Endpoints

Provides REST endpoints for conversation management (CRUD).
All endpoints require authentication.
"""

from loguru import logger
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConversationNotFoundError, ConversationAccessDeniedError
from app.db.session import get_db
from app.db.models import User, Conversation
from app.dependencies import get_current_user
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.message_repo import MessageRepository
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    MessageResponse,
)


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationListResponse:
    """
    List all conversations for the authenticated user.

    Returns conversations ordered by most recent first (updated_at DESC).
    Supports pagination via limit/offset query parameters.

    Args:
        limit: Maximum number of conversations (1-100, default: 50)
        offset: Number of conversations to skip (default: 0)
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        ConversationListResponse with paginated conversation list

    Example:
        >>> GET /api/conversations?limit=20&offset=0
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversations": [...],
        >>>   "total": 20,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """
    repo = ConversationRepository(db)

    # Get both conversations and total count
    conversations = await repo.list_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
    total = await repo.count_by_user(user_id=current_user.id)

    logger.info(
        f"Listed {len(conversations)} conversations for user {current_user.id} "
        f"(limit={limit}, offset={offset}, total={total})"
    )

    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/latest", response_model=ConversationResponse)
async def get_latest_conversation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """
    Get the most recent conversation for the authenticated user.

    Returns the conversation with the latest updated_at timestamp.
    Useful for loading the last active conversation when user navigates to /chat.

    Args:
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        ConversationResponse with latest conversation data

    Raises:
        ConversationNotFoundError: No conversations found for this user

    Example:
        >>> GET /api/conversations/latest
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "user_id": "...",
        >>>   "title": "My Latest Chat",
        >>>   "created_at": "2025-01-15T10:30:00Z",
        >>>   "updated_at": "2025-01-15T14:45:00Z"
        >>> }
    """
    repo = ConversationRepository(db)

    # Get latest conversation
    latest = await repo.get_latest_by_user(user_id=current_user.id)

    if not latest:
        raise ConversationNotFoundError()

    logger.info(f"Retrieved latest conversation {latest.id} for user {current_user.id}")

    return ConversationResponse.model_validate(latest)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_detail(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationDetailResponse:
    """
    Get conversation detail with all messages.

    Returns conversation metadata plus all associated messages in chronological order.
    Verifies ownership before returning data.

    Args:
        conversation_id: UUID of the conversation to retrieve
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        ConversationDetailResponse with conversation + messages

    Raises:
        ConversationNotFoundError: Conversation not found
        ConversationAccessDeniedError: User doesn't own this conversation

    Example:
        >>> GET /api/conversations/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversation": {...},
        >>>   "messages": [...]
        >>> }
    """
    conversation_repo = ConversationRepository(db)
    message_repo = MessageRepository(db)

    # Fetch conversation
    conversation = await conversation_repo.get_by_id(conversation_id)

    if not conversation:
        raise ConversationNotFoundError()

    # Verify ownership
    if conversation.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempted to access conversation {conversation_id} "
            f"owned by user {conversation.user_id}"
        )
        raise ConversationAccessDeniedError()

    # Fetch messages
    messages = await message_repo.list_by_conversation(conversation_id)

    logger.info(
        f"Retrieved conversation {conversation_id} with {len(messages)} messages "
        f"for user {current_user.id}"
    )

    return ConversationDetailResponse(
        conversation=ConversationResponse.model_validate(conversation),
        messages=[MessageResponse.model_validate(m) for m in messages]
    )


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """
    Create a new conversation.

    Creates an empty conversation with the specified title.
    If no title provided, auto-generates one with timestamp.

    Note: WebSocket chat auto-creates conversations when needed.
    This endpoint provides explicit control for testing or advanced use cases.

    Args:
        body: Conversation creation request (optional title)
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        ConversationResponse with new conversation data

    Example:
        >>> POST /api/conversations
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Body: {"title": "My Custom Conversation"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "user_id": "...",
        >>>   "title": "My Custom Conversation",
        >>>   "created_at": "2025-01-15T10:30:00Z",
        >>>   "updated_at": "2025-01-15T10:30:00Z"
        >>> }
    """
    repo = ConversationRepository(db)

    # Auto-generate title if not provided
    title = body.title or f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    conversation = await repo.create(
        user_id=current_user.id,
        title=title
    )

    await db.commit()
    await db.refresh(conversation)

    logger.info(f"Created conversation {conversation.id} for user {current_user.id}")

    return ConversationResponse.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    """
    Update conversation title.

    Allows user to rename their conversation. Validates ownership before update.

    Args:
        conversation_id: UUID of the conversation to update
        body: Update request with new title (1-100 chars)
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        ConversationResponse with updated conversation data

    Raises:
        ConversationNotFoundError: Conversation not found
        ConversationAccessDeniedError: User doesn't own this conversation

    Example:
        >>> PATCH /api/conversations/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Body: {"title": "My Updated Title"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "user_id": "...",
        >>>   "title": "My Updated Title",
        >>>   "created_at": "2025-01-15T10:30:00Z",
        >>>   "updated_at": "2025-01-15T14:45:00Z"
        >>> }
    """
    repo = ConversationRepository(db)

    # Fetch conversation
    conversation = await repo.get_by_id(conversation_id)

    if not conversation:
        raise ConversationNotFoundError()

    # Verify ownership
    if conversation.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempted to update conversation {conversation_id} "
            f"owned by user {conversation.user_id}"
        )
        raise ConversationAccessDeniedError()

    # Update title
    updated_conversation = await repo.update_title(conversation_id, body.title)
    await db.commit()
    await db.refresh(updated_conversation)

    logger.info(
        f"Updated conversation {conversation_id} title to '{body.title}' "
        f"for user {current_user.id}"
    )

    return ConversationResponse.model_validate(updated_conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a conversation and all its messages.

    Permanently deletes the conversation and cascades to all messages.
    Verifies ownership before deletion.

    Args:
        conversation_id: UUID of the conversation to delete
        current_user: Authenticated user (injected via Depends)
        db: Database session (injected via Depends)

    Returns:
        204 No Content on success

    Raises:
        ConversationNotFoundError: Conversation not found
        ConversationAccessDeniedError: User doesn't own this conversation

    Example:
        >>> DELETE /api/conversations/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
    repo = ConversationRepository(db)

    # Fetch conversation
    conversation = await repo.get_by_id(conversation_id)

    if not conversation:
        raise ConversationNotFoundError()

    # Verify ownership
    if conversation.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempted to delete conversation {conversation_id} "
            f"owned by user {conversation.user_id}"
        )
        raise ConversationAccessDeniedError()

    # Delete conversation (cascade deletes messages)
    await repo.delete(conversation_id)
    await db.commit()

    logger.info(f"Deleted conversation {conversation_id} for user {current_user.id}")
