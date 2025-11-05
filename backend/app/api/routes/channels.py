"""
Channel Discovery API Routes

Public-facing authenticated endpoints for browsing channels and videos.
All endpoints require authentication.
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
from app.core.errors import ChannelNotFoundError
from app.schemas.channel_public import (
    ChannelListResponse,
    ChannelPublicResponse,
    ChannelVideoListResponse,
    VideoInChannelResponse,
)

router = APIRouter(prefix="/api/channels", tags=["channels"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=ChannelListResponse)
@limiter.limit("60/minute")
async def list_channels(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Maximum channels to return"),
    offset: int = Query(0, ge=0, description="Number of channels to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelListResponse:
    """
    List all active channels for discovery.

    **Authentication Required**

    Returns only non-deleted channels ordered by name (ascending).
    Supports pagination via limit/offset parameters.

    Rate Limit: 60 requests/minute

    Args:
        limit: Maximum number of channels (1-100, default: 50)
        offset: Number of channels to skip (default: 0)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelListResponse with paginated channel list

    Raises:
        401: Not authenticated

    Example:
        >>> GET /api/channels?limit=20&offset=0
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "channels": [...],
        >>>   "total": 20,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """
    service = ChannelService(db)
    channels, total = await service.list_public_channels(limit=limit, offset=offset)

    # Enrich with video counts (batch query for performance)
    channel_ids = [channel.id for channel in channels]
    video_counts = await service.get_channel_video_counts_batch(channel_ids)

    channel_responses: List[ChannelPublicResponse] = []
    for channel in channels:
        channel_responses.append(
            ChannelPublicResponse(
                id=channel.id,
                name=channel.name,
                display_title=channel.display_title,
                description=channel.description,
                video_count=video_counts.get(channel.id, 0),
                created_at=channel.created_at,
            )
        )

    logger.info(
        f"User {current_user.id} listed {len(channels)} channels "
        f"(limit={limit}, offset={offset})"
    )

    return ChannelListResponse(
        channels=channel_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{channel_id}", response_model=ChannelPublicResponse)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelPublicResponse:
    """
    Get channel details by ID.

    **Authentication Required**

    Returns channel metadata including video count.
    Returns 404 if channel deleted or not found.

    Rate Limit: 60 requests/minute

    Args:
        channel_id: UUID of the channel
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelPublicResponse with channel details

    Raises:
        401: Not authenticated
        404: Channel not found or deleted

    Example:
        >>> GET /api/channels/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "name": "python-tutorials",
        >>>   "display_title": "Python Tutorials",
        >>>   ...
        >>> }
    """
    service = ChannelService(db)

    try:
        channel = await service.get_public_channel(channel_id)
        video_count = await service.get_channel_video_count(channel.id)

        logger.info(f"User {current_user.id} viewed channel {channel_id}")

        return ChannelPublicResponse(
            id=channel.id,
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            video_count=video_count,
            created_at=channel.created_at,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/by-name/{name}", response_model=ChannelPublicResponse)
@limiter.limit("60/minute")
async def get_channel_by_name(
    request: Request,
    name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelPublicResponse:
    """
    Get channel details by URL-safe name.

    **Authentication Required**

    Returns channel metadata including video count.
    Returns 404 if channel deleted or not found.
    Useful for friendly URLs like /channels/python-tutorials.

    Rate Limit: 60 requests/minute

    Args:
        name: URL-safe channel name (lowercase, hyphens)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelPublicResponse with channel details

    Raises:
        401: Not authenticated
        404: Channel not found or deleted

    Example:
        >>> GET /api/channels/by-name/python-tutorials
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "name": "python-tutorials",
        >>>   ...
        >>> }
    """
    service = ChannelService(db)

    try:
        channel = await service.get_public_channel_by_name(name)
        video_count = await service.get_channel_video_count(channel.id)

        logger.info(f"User {current_user.id} viewed channel '{name}'")

        return ChannelPublicResponse(
            id=channel.id,
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            video_count=video_count,
            created_at=channel.created_at,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{channel_id}/videos", response_model=ChannelVideoListResponse)
@limiter.limit("60/minute")
async def list_channel_videos(
    request: Request,
    channel_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="Maximum videos to return"),
    offset: int = Query(0, ge=0, description="Number of videos to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelVideoListResponse:
    """
    List videos in a channel.

    **Authentication Required**

    Returns videos ordered by added_at DESC (newest first).
    Returns 404 if channel deleted or not found.
    Supports pagination via limit/offset parameters.

    Rate Limit: 60 requests/minute

    Args:
        channel_id: UUID of the channel
        limit: Maximum number of videos (1-100, default: 50)
        offset: Number of videos to skip (default: 0)
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        ChannelVideoListResponse with paginated video list

    Raises:
        401: Not authenticated
        404: Channel not found or deleted

    Example:
        >>> GET /api/channels/550e8400-e29b-41d4-a716-446655440000/videos?limit=20
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "videos": [...],
        >>>   "total": 42,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """
    service = ChannelService(db)

    try:
        # Verify channel exists and is active
        await service.get_public_channel(channel_id)

        # List videos
        channel_videos, total = await service.list_channel_videos(
            channel_id=channel_id,
            limit=limit,
            offset=offset,
        )

        # Convert to response schema
        video_responses: List[VideoInChannelResponse] = []
        for cv in channel_videos:
            # cv is ChannelVideo model with transcript relationship
            video_responses.append(
                VideoInChannelResponse(
                    transcript_id=cv.transcript_id,
                    youtube_video_id=cv.transcript.youtube_video_id,
                    title=cv.transcript.title or "Untitled",
                    channel_name=cv.transcript.channel_name or "Unknown",
                    duration=cv.transcript.duration,
                    added_at=cv.added_at,
                )
            )

        logger.info(
            f"User {current_user.id} listed {len(video_responses)} videos "
            f"in channel {channel_id} (limit={limit}, offset={offset})"
        )

        return ChannelVideoListResponse(
            videos=video_responses,
            total=total,
            limit=limit,
            offset=offset,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
