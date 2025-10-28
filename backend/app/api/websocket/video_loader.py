"""
Video Loading Module

Handles YouTube video loading confirmation flow and background ingestion.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from fastapi import WebSocket
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket.messages import (
    LoadVideoConfirmationMessage,
    VideoLoadStatusMessage,
)
from app.db.models import User
from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.user_repo import UserRepository
from app.services.transcript_service import TranscriptService
from app.utils.url_detector import detect_youtube_url


@dataclass
class PendingVideoLoad:
    """Track pending video load confirmations."""

    conversation_id: str
    youtube_url: str
    video_id: str
    video_title: Optional[str]
    user_id: UUID
    created_at: datetime


# In-memory store for pending confirmations (MVP: dict, can upgrade to Redis later)
pending_loads: Dict[str, PendingVideoLoad] = {}


async def check_user_quota(user: User, db: AsyncSession) -> tuple[bool, str]:
    """
    Check if user can load another video.

    Args:
        user: User model instance
        db: Database session

    Returns:
        (allowed: bool, error_message: str)
        - If allowed=True, error_message is empty
        - If allowed=False, error_message contains user-facing explanation

    Examples:
        >>> user = User(role="admin", transcript_count=100)
        >>> allowed, msg = await check_user_quota(user, db)
        >>> allowed
        True

        >>> user = User(role="user", transcript_count=10)
        >>> allowed, msg = await check_user_quota(user, db)
        >>> allowed
        False
    """
    if user.role == "admin":
        return True, ""

    if user.transcript_count >= 10:
        return False, (
            "You've reached your video limit (10 videos). "
            "Delete some videos to add more, or contact support for an upgrade."
        )

    return True, ""


async def handle_video_load_intent(
    youtube_url: str,
    user: User,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket,
) -> None:
    """
    Handle video_load intent: check duplicates, quota, ask confirmation.

    Flow:
        1. Extract video ID from URL
        2. Check for duplicates in user's transcripts
        3. Check user quota and role
        4. Store pending load
        5. Send confirmation request via WebSocket

    Args:
        youtube_url: YouTube URL extracted from user query
        user: Current user
        conversation_id: Current conversation UUID
        db: Database session
        websocket: WebSocket connection

    Raises:
        ValueError: If video ID cannot be extracted from URL
    """
    # Step 1: Extract video ID
    video_id = detect_youtube_url(youtube_url)

    if not video_id:
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="failed",
                message="Could not extract video ID from URL. Please check the link and try again.",
                error="INVALID_URL",
            ).model_dump()
        )
        return

    logger.info(f"Video load request: user={user.id}, video_id={video_id}")

    # Step 2: Check for duplicates
    transcript_repo = TranscriptRepository(db)
    existing = await transcript_repo.get_by_video_id(user.id, video_id)

    if existing:
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="failed",
                message=f"You already have this video in your knowledge base (added {existing.created_at.strftime('%Y-%m-%d')}).",
                video_title=existing.title,
                error="DUPLICATE_VIDEO",
            ).model_dump()
        )
        logger.info(f"Duplicate video detected: user={user.id}, video_id={video_id}")
        return

    # Step 3: Check user quota
    allowed, quota_message = await check_user_quota(user, db)

    if not allowed:
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="failed",
                message=quota_message,
                error="QUOTA_EXCEEDED",
            ).model_dump()
        )
        logger.warning(f"Quota exceeded: user={user.id}, count={user.transcript_count}")
        return

    # Step 4: Store pending load
    pending_load = PendingVideoLoad(
        conversation_id=conversation_id,
        youtube_url=youtube_url,
        video_id=video_id,
        video_title=None,  # Will be fetched during ingestion
        user_id=user.id,
        created_at=datetime.utcnow(),
    )

    pending_loads[conversation_id] = pending_load
    logger.info(f"Pending load created: conversation={conversation_id}, video={video_id}")

    # Step 5: Send confirmation request
    await websocket.send_json(
        LoadVideoConfirmationMessage(
            youtube_url=youtube_url,
            video_id=video_id,
            video_title=None,  # No preview in MVP
            message=f"Load this video ({video_id}) to your knowledge base? Reply 'yes' or 'no'.",
        ).model_dump()
    )


async def handle_confirmation_response(
    response: str,
    conversation_id: str,
    user_id: UUID,
    db: AsyncSession,
    websocket: WebSocket,
) -> bool:
    """
    Handle yes/no response to confirmation.

    Args:
        response: User's text response (checked for yes/no patterns)
        conversation_id: Current conversation UUID
        user_id: Current user UUID
        db: Database session
        websocket: WebSocket connection

    Returns:
        True if message was handled as a confirmation response, False otherwise

    Examples:
        >>> # User says "yes" -> trigger load
        >>> handled = await handle_confirmation_response("yes", conv_id, user_id, db, ws)
        >>> handled
        True

        >>> # User says "what?" -> not a confirmation
        >>> handled = await handle_confirmation_response("what?", conv_id, user_id, db, ws)
        >>> handled
        False
    """
    # Check if pending load exists for this conversation
    pending = pending_loads.get(conversation_id)

    if not pending:
        return False  # No pending confirmation

    # Verify user ownership (security check)
    if pending.user_id != user_id:
        logger.warning(
            f"Confirmation attempt by wrong user: "
            f"pending_user={pending.user_id}, actual_user={user_id}"
        )
        return False

    # Normalize response
    response_lower = response.strip().lower()

    # Match yes/no patterns
    yes_patterns = ["yes", "y", "yeah", "sure", "ok", "okay", "yep", "yup", "load it"]
    no_patterns = ["no", "n", "nope", "cancel", "don't", "stop"]

    if any(pattern in response_lower for pattern in yes_patterns):
        # User confirmed - trigger background load
        await trigger_background_load(
            youtube_url=pending.youtube_url,
            user_id=user_id,
            conversation_id=conversation_id,
            db=db,
            websocket=websocket,
        )

        # Clear pending load
        del pending_loads[conversation_id]
        logger.info(f"Confirmation accepted: conversation={conversation_id}")
        return True

    elif any(pattern in response_lower for pattern in no_patterns):
        # User declined - cancel load
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="failed",
                message="Video loading cancelled.",
                error="USER_CANCELLED",
            ).model_dump()
        )

        # Clear pending load
        del pending_loads[conversation_id]
        logger.info(f"Confirmation declined: conversation={conversation_id}")
        return True

    # Response doesn't match yes/no patterns - not handled
    return False


async def trigger_background_load(
    youtube_url: str,
    user_id: UUID,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket,
) -> None:
    """
    Trigger transcript ingestion in background.

    Sends immediate "started" status and creates background task for actual loading.

    Args:
        youtube_url: YouTube URL to load
        user_id: User UUID
        conversation_id: Conversation UUID
        db: Database session
        websocket: WebSocket connection
    """
    # Send immediate status
    await websocket.send_json(
        VideoLoadStatusMessage(
            status="started",
            message="Loading video in background. You can continue chatting...",
        ).model_dump()
    )

    # Create background task (don't await - runs in background)
    asyncio.create_task(
        load_video_background(
            youtube_url=youtube_url,
            user_id=user_id,
            conversation_id=conversation_id,
            db=db,
            websocket=websocket,
        )
    )


async def load_video_background(
    youtube_url: str,
    user_id: UUID,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket,
) -> None:
    """
    Background task for video loading.

    Performs actual transcript ingestion, increments quota, and sends status updates.

    Args:
        youtube_url: YouTube URL to load
        user_id: User UUID
        conversation_id: Conversation UUID
        db: Database session
        websocket: WebSocket connection
    """
    try:
        logger.info(f"Background load started: user={user_id}, url={youtube_url}")

        # Ingest transcript
        service = TranscriptService()
        result = await service.ingest_transcript(
            youtube_url=youtube_url,
            user_id=user_id,
            db_session=db,
        )

        # Increment user transcript count
        user_repo = UserRepository(db)
        await user_repo.increment_transcript_count(user_id)

        # Extract video title from result
        video_title = result.get("metadata", {}).get("title", "Unknown")

        # Send success message
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="completed",
                message=f"Video loaded successfully! You can now ask questions about it.",
                video_title=video_title,
            ).model_dump()
        )

        logger.info(
            f"Background load completed: user={user_id}, "
            f"video_id={result['youtube_video_id']}, title={video_title}"
        )

    except Exception as e:
        logger.exception(f"Background video load failed: user={user_id}, error={e}")

        # Send failure message
        await websocket.send_json(
            VideoLoadStatusMessage(
                status="failed",
                message=f"Failed to load video: {str(e)}",
                error=str(e),
            ).model_dump()
        )
