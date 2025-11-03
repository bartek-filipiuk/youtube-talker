"""
Admin Channel API Endpoints

Admin-only endpoints for channel CRUD operations and video management.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    VideoAlreadyInChannelError,
    VideoNotInChannelError,
)
from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.schemas.channel import (
    ChannelCreateRequest,
    ChannelUpdateRequest,
    ChannelResponse,
    ChannelListResponse,
    ChannelListItem,
    VideoToChannelRequest,
    ChannelVideoListResponse,
    ChannelVideoItem,
)
from app.schemas.transcript import TranscriptResponse
from app.services.channel_service import ChannelService

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/admin/channels", tags=["admin", "channels"])


@router.post("/", response_model=ChannelResponse, status_code=201)
@limiter.limit("10/minute")
async def create_channel(
    request: Request,
    body: ChannelCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """
    Create new channel (admin only).

    Automatically creates Qdrant collection with sanitized name.
    Channel name must be unique and URL-safe (lowercase, numbers, hyphens).

    Rate limit: 10/minute

    Args:
        request: FastAPI request (for rate limiting)
        body: Channel creation request
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelResponse: Created channel with metadata

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 409: Channel name already exists
        HTTPException 500: Qdrant collection creation failed
    """
    service = ChannelService(db)

    try:
        channel = await service.create_channel(
            name=body.name,
            display_title=body.display_title,
            description=body.description,
            created_by=admin.id,
        )

        # Get video count for response
        video_count = await service.get_channel_video_count(channel.id)

        return ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            qdrant_collection_name=channel.qdrant_collection_name,
            created_by=str(channel.created_by) if channel.created_by else None,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
            deleted_at=channel.deleted_at,
            video_count=video_count,
        )
    except ChannelAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create channel: {str(e)}",
        ) from e


@router.get("/", response_model=ChannelListResponse)
@limiter.limit("30/minute")
async def list_channels(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted channels"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelListResponse:
    """
    List all channels with pagination (admin only).

    By default excludes soft-deleted channels. Set include_deleted=true to see all.

    Rate limit: 30/minute

    Args:
        request: FastAPI request (for rate limiting)
        limit: Maximum channels to return (1-100, default 50)
        offset: Number of channels to skip (default 0)
        include_deleted: Include soft-deleted channels (default False)
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelListResponse: Paginated list of channels

    Raises:
        HTTPException 403: Non-admin access
    """
    service = ChannelService(db)

    channels, total = await service.list_channels(
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
    )

    # Build response with video counts
    channel_items = []
    for channel in channels:
        video_count = await service.get_channel_video_count(channel.id)
        channel_items.append(
            ChannelListItem(
                id=str(channel.id),
                name=channel.name,
                display_title=channel.display_title,
                created_at=channel.created_at,
                video_count=video_count,
            )
        )

    return ChannelListResponse(
        channels=channel_items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{channel_id}", response_model=ChannelResponse)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """
    Get channel details by ID (admin only).

    Rate limit: 60/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelResponse: Channel details with metadata

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
    """
    service = ChannelService(db)

    try:
        channel = await service.get_channel(channel_id)
        video_count = await service.get_channel_video_count(channel.id)

        return ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            qdrant_collection_name=channel.qdrant_collection_name,
            created_by=str(channel.created_by) if channel.created_by else None,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
            deleted_at=channel.deleted_at,
            video_count=video_count,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/by-name/{name}", response_model=ChannelResponse)
@limiter.limit("60/minute")
async def get_channel_by_name(
    request: Request,
    name: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """
    Get channel details by URL-safe name (admin only).

    Rate limit: 60/minute

    Args:
        request: FastAPI request (for rate limiting)
        name: URL-safe channel name
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelResponse: Channel details with metadata

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
    """
    service = ChannelService(db)

    try:
        channel = await service.get_channel_by_name(name)
        video_count = await service.get_channel_video_count(channel.id)

        return ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            qdrant_collection_name=channel.qdrant_collection_name,
            created_by=str(channel.created_by) if channel.created_by else None,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
            deleted_at=channel.deleted_at,
            video_count=video_count,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch("/{channel_id}", response_model=ChannelResponse)
@limiter.limit("20/minute")
async def update_channel(
    request: Request,
    channel_id: UUID,
    body: ChannelUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """
    Update channel metadata (admin only).

    Name cannot be changed (immutable for Qdrant collection consistency).
    Only display_title and description can be updated.

    Rate limit: 20/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        body: Channel update request
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelResponse: Updated channel

    Raises:
        HTTPException 400: No fields to update
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
    """
    service = ChannelService(db)

    try:
        channel = await service.update_channel(
            channel_id=channel_id,
            display_title=body.display_title,
            description=body.description,
        )
        video_count = await service.get_channel_video_count(channel.id)

        return ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            qdrant_collection_name=channel.qdrant_collection_name,
            created_by=str(channel.created_by) if channel.created_by else None,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
            deleted_at=channel.deleted_at,
            video_count=video_count,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_channel(
    request: Request,
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> None:
    """
    Soft delete channel (admin only).

    Preserves all data (conversations, videos, chunks). Channel is hidden
    from public lists but data remains intact. Use reactivate endpoint to restore.

    Rate limit: 10/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        db: Database session
        admin: Authenticated admin user

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
    """
    service = ChannelService(db)

    try:
        await service.soft_delete_channel(channel_id)
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post("/{channel_id}/reactivate", response_model=ChannelResponse)
@limiter.limit("10/minute")
async def reactivate_channel(
    request: Request,
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """
    Reactivate soft-deleted channel (admin only).

    Clears deleted_at timestamp and makes channel visible again.

    Rate limit: 10/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelResponse: Reactivated channel

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found or not deleted
    """
    service = ChannelService(db)

    try:
        channel = await service.reactivate_channel(channel_id)
        video_count = await service.get_channel_video_count(channel.id)

        return ChannelResponse(
            id=str(channel.id),
            name=channel.name,
            display_title=channel.display_title,
            description=channel.description,
            qdrant_collection_name=channel.qdrant_collection_name,
            created_by=str(channel.created_by) if channel.created_by else None,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
            deleted_at=channel.deleted_at,
            video_count=video_count,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{channel_id}/videos", response_model=TranscriptResponse, status_code=201)
@limiter.limit("5/minute")
async def add_video_to_channel(
    request: Request,
    channel_id: UUID,
    body: VideoToChannelRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> TranscriptResponse:
    """
    Add video to channel via YouTube URL (admin only).

    Full ingestion pipeline:
        1. Fetch transcript from SUPADATA API
        2. Create Transcript record (owned by admin)
        3. Chunk text (700 tokens, 20% overlap)
        4. Generate embeddings (OpenAI)
        5. Save chunks with channel_id
        6. Upsert to channel's Qdrant collection
        7. Create ChannelVideo association

    Rate limit: 5/minute (expensive operation)

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        body: Video ingestion request with YouTube URL
        db: Database session
        admin: Authenticated admin user

    Returns:
        TranscriptResponse: Ingestion results

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
        HTTPException 409: Video already in channel
        HTTPException 400: Invalid YouTube URL
        HTTPException 503: SUPADATA API error
    """
    service = ChannelService(db)

    try:
        result = await service.add_video_to_channel(
            channel_id=channel_id,
            youtube_url=body.youtube_url,
            admin_user_id=admin.id,
        )

        return TranscriptResponse(
            id=result["transcript_id"],
            youtube_video_id=result["youtube_video_id"],
            chunk_count=result["chunk_count"],
            metadata=result["metadata"],
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except VideoAlreadyInChannelError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        # Invalid YouTube URL
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        # SUPADATA API or other errors
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to add video: {str(e)}",
        ) from e


@router.delete("/{channel_id}/videos/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def remove_video_from_channel(
    request: Request,
    channel_id: UUID,
    transcript_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> None:
    """
    Remove video from channel (admin only).

    Deletes:
        - ChannelVideo association
        - Chunks from PostgreSQL (where channel_id matches)
        - Vectors from channel's Qdrant collection

    Note: Transcript record remains if used elsewhere.

    Rate limit: 20/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        transcript_id: Transcript UUID to remove
        db: Database session
        admin: Authenticated admin user

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel or video not found
    """
    service = ChannelService(db)

    try:
        await service.remove_video_from_channel(
            channel_id=channel_id,
            transcript_id=transcript_id,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except VideoNotInChannelError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get("/{channel_id}/videos", response_model=ChannelVideoListResponse)
@limiter.limit("30/minute")
async def list_channel_videos(
    request: Request,
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items to skip"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelVideoListResponse:
    """
    List videos in channel with pagination (admin only).

    Returns video metadata with added_at timestamp.
    Ordered by added_at descending (newest first).

    Rate limit: 30/minute

    Args:
        request: FastAPI request (for rate limiting)
        channel_id: Channel UUID
        limit: Maximum videos to return (1-100, default 50)
        offset: Number of videos to skip (default 0)
        db: Database session
        admin: Authenticated admin user

    Returns:
        ChannelVideoListResponse: Paginated list of videos

    Raises:
        HTTPException 403: Non-admin access
        HTTPException 404: Channel not found
    """
    service = ChannelService(db)

    try:
        # Verify channel exists
        await service.get_channel(channel_id)

        # Get videos
        videos, total = await service.list_channel_videos(
            channel_id=channel_id,
            limit=limit,
            offset=offset,
        )

        # Build response
        video_items = [
            ChannelVideoItem(
                id=str(video.id),
                transcript_id=str(video.transcript_id),
                youtube_video_id=video.transcript.youtube_video_id,
                title=video.transcript.title or "Untitled Video",
                channel_name=video.transcript.channel_name or "Unknown Channel",
                duration=video.transcript.duration or 0,
                added_by=str(video.added_by) if video.added_by else None,
                added_at=video.added_at,
            )
            for video in videos
        ]

        return ChannelVideoListResponse(
            videos=video_items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except ChannelNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
