"""
Video Loading Module

Handles YouTube video loading confirmation flow and background ingestion.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from fastapi import WebSocket
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket.connection_manager import connection_manager
from app.api.websocket.messages import (
    LoadVideoConfirmationMessage,
    StatusMessage,
    VideoLoadStatusMessage,
)
from app.db.models import User
from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.user_repo import UserRepository
from app.db.session import AsyncSessionLocal
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


@dataclass
class VideoMetadata:
    """Cached video metadata from SUPADATA API."""

    video_id: str
    duration: int
    title: Optional[str]
    fetched_at: datetime


# In-memory store for pending confirmations (MVP: dict, can upgrade to Redis later)
pending_loads: Dict[str, PendingVideoLoad] = {}

# In-memory cache for video metadata (persists until server restart)
# Key: video_id, Value: VideoMetadata
video_metadata_cache: Dict[str, VideoMetadata] = {}

# Pending confirmation expiration timeout (5 minutes)
PENDING_LOAD_TTL_SECONDS = 300


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


async def check_duration_limit(user: User, duration_seconds: int) -> tuple[bool, str]:
    """
    Check if video duration is within user's role limits.

    Args:
        user: User model instance
        duration_seconds: Video duration in seconds

    Returns:
        (allowed: bool, error_message: str)
        - If allowed=True, error_message is empty
        - If allowed=False, error_message contains user-facing explanation

    Examples:
        >>> user = User(role="admin")
        >>> allowed, msg = await check_duration_limit(user, 100000)  # 27+ hours
        >>> allowed
        True

        >>> user = User(role="user")
        >>> allowed, msg = await check_duration_limit(user, 12000)  # 3.3 hours
        >>> allowed
        False
    """
    # Duration limits by role (seconds)
    # Design: Easy to extend for premium role in future
    DURATION_LIMITS = {
        "admin": None,  # Unlimited
        "user": 10800,  # 3 hours (3 * 60 * 60)
        # "premium": 36000,  # 10 hours (future)
    }

    limit = DURATION_LIMITS.get(user.role)

    if limit is None:  # Admin or unmapped role - unlimited
        return True, ""

    if duration_seconds > limit:
        # Format duration for user-friendly message
        video_hours = duration_seconds // 3600
        video_minutes = (duration_seconds % 3600) // 60
        limit_hours = limit // 3600

        return False, (
            f"This video is {video_hours}h {video_minutes}m long, "
            f"but your plan allows videos up to {limit_hours} hours. "
            f"Try a shorter video or contact support for an upgrade."
        )

    return True, ""


async def fetch_video_duration(youtube_url: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Fetch video duration and title via SUPADATA metadata API.

    Uses in-memory cache to avoid repeated API calls for the same video.
    Cache persists until server restart.

    Makes a lightweight API call to get only metadata (not full transcript).
    SUPADATA cost: 1 credit (same as transcript, but faster and lighter).

    Args:
        youtube_url: YouTube URL (youtube.com/watch?v=ID or youtu.be/ID)

    Returns:
        Tuple of (duration_seconds: int | None, video_title: str | None)

    Raises:
        ValueError: If YouTube URL is invalid
        Exception: If SUPADATA API call fails

    Examples:
        >>> duration, title = await fetch_video_duration("https://youtube.com/watch?v=abc123")
        >>> duration
        7200  # 2 hours in seconds
        >>> title
        "Example Video Title"
    """
    try:
        # Extract video ID from URL
        video_id = detect_youtube_url(youtube_url)
        if not video_id:
            raise ValueError(f"Invalid YouTube URL: {youtube_url}")

        # Check cache first
        if video_id in video_metadata_cache:
            cached = video_metadata_cache[video_id]
            logger.debug(
                f"Cache HIT: video_id={video_id}, duration={cached.duration}s, "
                f"cached_at={cached.fetched_at.isoformat()}"
            )
            return cached.duration, cached.title

        # Cache miss - fetch from SUPADATA API
        logger.debug(f"Cache MISS: video_id={video_id}, fetching from SUPADATA...")
        service = TranscriptService()
        video = await asyncio.to_thread(service.client.youtube.video, id=video_id)

        # Extract duration and title
        duration = getattr(video, "duration", 0)
        title = getattr(video, "title", None)

        # Only cache if duration is valid (> 0)
        # Zero duration indicates missing/invalid data and should not be cached
        # to allow retries in case of temporary API issues
        if duration > 0:
            video_metadata_cache[video_id] = VideoMetadata(
                video_id=video_id,
                duration=duration,
                title=title,
                fetched_at=datetime.now(timezone.utc),
            )
            logger.debug(f"Fetched and cached video metadata: video_id={video_id}, duration={duration}s, title={title}")
        else:
            logger.warning(
                f"Skipping cache for video_id={video_id} - invalid duration: {duration}s. "
                f"Will allow retry on next request."
            )

        return duration, title

    except ValueError:
        # Re-raise invalid URL errors
        raise
    except Exception as e:
        logger.error(f"Failed to fetch video duration for {youtube_url}: {e}")
        raise


async def handle_video_load_intent(
    youtube_url: str,
    user: User,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket,
) -> None:
    """
    Handle video_load intent: check duplicates, duration, quota, ask confirmation.

    Flow:
        1. Extract video ID from URL
        2. Check for duplicates in user's transcripts
        2.5. Fetch duration and check per-video duration limit
        3. Check user quota and role (video count limit)
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
        await connection_manager.send_json(
            websocket,
            VideoLoadStatusMessage(
                status="failed",
                message="Could not extract video ID from URL. Please check the link and try again.",
                error="INVALID_URL",
            ).model_dump()
        )
        return

    logger.info(f"Video load request: user={user.id}, video_id={video_id}")

    # Send status message to show we're checking the video
    await connection_manager.send_json(
        websocket,
        StatusMessage(
            message="Checking video...",
            step="checking"
        ).model_dump()
    )

    # Step 2: Check for duplicates
    transcript_repo = TranscriptRepository(db)
    existing = await transcript_repo.get_by_video_id(user.id, video_id)

    if existing:
        await connection_manager.send_json(
            websocket,
            VideoLoadStatusMessage(
                status="failed",
                message=f"You already have this video in your knowledge base (added {existing.created_at.strftime('%Y-%m-%d')}).",
                video_title=existing.title,
                error="DUPLICATE_VIDEO",
            ).model_dump()
        )
        logger.info(f"Duplicate video detected: user={user.id}, video_id={video_id}")
        return

    # Step 2.5: Check video duration limit (per-video limit)
    try:
        logger.info(f"Step 2.5/6: Checking video duration limit for video_id={video_id}")
        duration_seconds, video_title = await fetch_video_duration(youtube_url)

        # Validate duration is available
        if duration_seconds == 0:
            await connection_manager.send_json(
                websocket,
                VideoLoadStatusMessage(
                    status="failed",
                    message="Could not determine video duration. Please try again later.",
                    error="DURATION_UNAVAILABLE",
                ).model_dump()
            )
            logger.warning(f"Duration unavailable for video_id={video_id}")
            return

        # Check duration limit based on user role
        allowed, duration_message = await check_duration_limit(user, duration_seconds)

        if not allowed:
            await connection_manager.send_json(
                websocket,
                VideoLoadStatusMessage(
                    status="failed",
                    message=duration_message,
                    video_title=video_title,
                    error="DURATION_EXCEEDED",
                ).model_dump()
            )
            logger.warning(
                f"Duration limit exceeded: user={user.id}, role={user.role}, "
                f"duration={duration_seconds}s ({duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m)"
            )
            return

        logger.info(f"✓ Duration check passed: {duration_seconds}s ({duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m)")

    except ValueError as e:
        # Invalid URL - already handled in Step 1, but catch anyway
        await connection_manager.send_json(
            websocket,
            VideoLoadStatusMessage(
                status="failed",
                message="Invalid YouTube URL. Please check the link and try again.",
                error="INVALID_URL",
            ).model_dump()
        )
        logger.error(f"Invalid URL during duration check: {e}")
        return
    except Exception as e:
        # SUPADATA API error or network issue
        await connection_manager.send_json(
            websocket,
            VideoLoadStatusMessage(
                status="failed",
                message="Could not verify video duration. Please try again later.",
                error="DURATION_CHECK_FAILED",
            ).model_dump()
        )
        logger.exception(f"Duration check failed for video_id={video_id}: {e}")
        return

    # Step 3: Check user quota
    allowed, quota_message = await check_user_quota(user, db)

    if not allowed:
        await connection_manager.send_json(
            websocket,
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
        created_at=datetime.now(timezone.utc),
    )

    pending_loads[conversation_id] = pending_load
    logger.info(f"Pending load created: conversation={conversation_id}, video={video_id}")

    # Step 5: Send confirmation request
    await connection_manager.send_json(
        websocket,
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

    # Check if pending confirmation has expired (5 minutes)
    elapsed_seconds = (datetime.now(timezone.utc) - pending.created_at).total_seconds()
    if elapsed_seconds > PENDING_LOAD_TTL_SECONDS:
        # Expired - remove and return False
        del pending_loads[conversation_id]
        logger.info(
            f"Expired pending load removed: conversation={conversation_id}, "
            f"elapsed={elapsed_seconds:.0f}s"
        )
        return False

    # Verify user ownership (security check)
    if pending.user_id != user_id:
        logger.warning(
            f"Confirmation attempt by wrong user: "
            f"pending_user={pending.user_id}, actual_user={user_id}"
        )
        return False

    # Normalize response
    response_lower = response.strip().lower()

    # Match yes/no patterns with word boundaries to avoid false positives
    # (e.g., "yesterday" should NOT match "yes", "I'm not sure" should NOT match "sure")
    yes_pattern = r'\b(yes|y|yeah|sure|ok(ay)?|yep|yup|load\s+it)\b'
    no_pattern = r'\b(no|n|nope|cancel|don\'?t|stop)\b'

    if re.search(yes_pattern, response_lower):
        # User confirmed - trigger background load
        await trigger_background_load(
            youtube_url=pending.youtube_url,
            user_id=user_id,
            conversation_id=conversation_id,
            websocket=websocket,
        )

        # Clear pending load
        del pending_loads[conversation_id]
        logger.info(f"Confirmation accepted: conversation={conversation_id}")
        return True

    elif re.search(no_pattern, response_lower):
        # User declined - cancel load
        await connection_manager.send_json(
            websocket,
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
    websocket: WebSocket,
) -> None:
    """
    Trigger transcript ingestion in background.

    Sends immediate "started" status and creates background task for actual loading.

    Args:
        youtube_url: YouTube URL to load
        user_id: User UUID
        conversation_id: Conversation UUID
        websocket: WebSocket connection
    """
    # Send immediate status
    await connection_manager.send_json(
        websocket,
        VideoLoadStatusMessage(
            status="started",
            message="Loading video in background. You can continue chatting...",
        ).model_dump()
    )

    # Create background task (don't await - runs in background)
    # NOTE: Background task creates its own database session to avoid
    # reusing the request-scoped session which will be closed
    asyncio.create_task(
        load_video_background(
            youtube_url=youtube_url,
            user_id=user_id,
            conversation_id=conversation_id,
            websocket=websocket,
        )
    )


async def load_video_background(
    youtube_url: str,
    user_id: UUID,
    conversation_id: str,
    websocket: WebSocket,
) -> None:
    """
    Background task for video loading.

    Performs actual transcript ingestion, increments quota, and sends status updates.
    Creates its own database session to avoid reusing the request-scoped session.

    Args:
        youtube_url: YouTube URL to load
        user_id: User UUID
        conversation_id: Conversation UUID
        websocket: WebSocket connection
    """
    # Create a new database session for this background task
    async with AsyncSessionLocal() as db:
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

            # Commit the transaction
            await db.commit()

            # Extract video title from result
            video_title = result.get("metadata", {}).get("title", "Unknown")

            # Send success message
            await connection_manager.send_json(
                websocket,
                VideoLoadStatusMessage(
                    status="completed",
                    message="Video loaded successfully! You can now ask questions about it.",
                    video_title=video_title,
                ).model_dump()
            )

            logger.info(
                f"Background load completed: user={user_id}, "
                f"video_id={result['youtube_video_id']}, title={video_title}"
            )

        except Exception as e:
            logger.exception(f"Background video load failed: user={user_id}, error={e}")

            # Rollback on error
            await db.rollback()

            # Send failure message
            await connection_manager.send_json(
                websocket,
                VideoLoadStatusMessage(
                    status="failed",
                    message=f"Failed to load video: {str(e)}",
                    error=str(e),
                ).model_dump()
            )
