# PR #2: Admin API Endpoints - Implementation Plan

## Overview
Implement admin-only API endpoints for channel CRUD operations and video management, including full YouTube video ingestion to channel collections.

**Status:** 🔄 Planning
**Branch:** `feature/channels-pr2-admin-api`
**Target:** `channels`
**Dependencies:** PR #1 (Merged)
**Created:** 2025-11-03

---

## Objectives

1. **Service Layer** - Create ChannelService for business logic
2. **Admin Auth** - Implement admin-only dependency guard
3. **Pydantic Schemas** - Request/response models for channel APIs
4. **Admin Routes** - 10+ endpoints for channel management
5. **Video Ingestion** - Full YouTube → Channel pipeline (fetch, chunk, embed, store)
6. **Qdrant Integration** - Auto-create collections on channel creation
7. **Tests** - Unit + integration tests (80%+ coverage)

---

## Architecture Decisions

### ✅ Service Layer Pattern
- **ChannelService** orchestrates complex operations
- Coordinates multiple repositories and external services
- Similar to existing TranscriptService pattern

### ✅ Eager Collection Creation
- Create Qdrant collection immediately when channel is created
- Simpler error handling (fail fast on creation)
- Avoids race conditions with concurrent video additions

### ✅ Full Video Ingestion
- Admin can add videos directly from YouTube URLs
- Uses same pipeline as user transcript ingestion
- Stores chunks in channel-specific Qdrant collection
- Creates Transcript record owned by admin user

---

## Phase 2.1: Admin Dependency Guard

### File: `app/dependencies.py`

**Add new dependency:**
```python
async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Admin-only authentication dependency.

    Requires user to be authenticated AND have role='admin'.
    Use with Depends() in admin-protected endpoints.

    Args:
        user: Authenticated user from get_current_user

    Returns:
        User: Admin user object

    Raises:
        HTTPException: 403 Forbidden if user.role != 'admin'

    Example:
        @router.post("/admin/channels")
        async def create_channel(user: User = Depends(get_admin_user)):
            # Only admins can access this
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user
```

**Tests:**
- `test_get_admin_user_success` - Admin user passes
- `test_get_admin_user_forbidden` - Regular user gets 403
- `test_get_admin_user_unauthenticated` - No token gets 401

---

## Phase 2.2: Pydantic Schemas

### File: `app/schemas/channel.py`

**Schemas to implement:**

```python
# Request Models
class ChannelCreateRequest(BaseModel):
    """Request to create a new channel."""
    name: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9\-]+$')
    display_title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

class ChannelUpdateRequest(BaseModel):
    """Request to update channel metadata."""
    display_title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

class VideoToChannelRequest(BaseModel):
    """Request to add video to channel via YouTube URL."""
    youtube_url: str = Field(..., min_length=1, max_length=500)

# Response Models
class ChannelResponse(BaseModel):
    """Full channel details."""
    id: str
    name: str
    display_title: str
    description: Optional[str]
    qdrant_collection_name: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    video_count: int  # Computed from repository

class ChannelListItem(BaseModel):
    """Minimal channel info for list views."""
    id: str
    name: str
    display_title: str
    created_at: datetime
    video_count: int

class ChannelListResponse(BaseModel):
    """Paginated channel list."""
    channels: List[ChannelListItem]
    total: int
    limit: int
    offset: int

class ChannelVideoItem(BaseModel):
    """Video in a channel with metadata."""
    id: str  # ChannelVideo.id
    transcript_id: str
    youtube_video_id: str
    title: str
    channel_name: str  # YouTube channel
    duration: int
    added_by: Optional[str]
    added_at: datetime

class ChannelVideoListResponse(BaseModel):
    """Paginated channel video list."""
    videos: List[ChannelVideoItem]
    total: int
    limit: int
    offset: int
```

**Tests:**
- `test_channel_create_request_validation` - Valid/invalid names
- `test_channel_update_request_optional_fields`
- `test_video_to_channel_request_url_validation`
- `test_channel_response_serialization`

---

## Phase 2.3: Channel Service Layer

### File: `app/services/channel_service.py`

**Service class with methods:**

```python
class ChannelService:
    """
    Business logic for channel management.

    Orchestrates repositories, Qdrant, and external services for
    channel CRUD operations and video ingestion.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.channel_video_repo = ChannelVideoRepository(db)
        self.transcript_repo = TranscriptRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.qdrant_service = QdrantService()

    async def create_channel(
        self,
        name: str,
        display_title: str,
        description: Optional[str],
        created_by: UUID,
    ) -> Channel:
        """
        Create new channel with Qdrant collection.

        Steps:
            1. Sanitize name for Qdrant collection
            2. Create Qdrant collection (with indexes)
            3. Create channel in PostgreSQL
            4. Commit transaction

        Raises:
            ValueError: Channel name already exists
            ExternalAPIError: Qdrant collection creation failed
        """
        # Sanitize collection name
        collection_name = QdrantService.sanitize_collection_name(f"channel_{name}")

        # Create Qdrant collection (eager)
        await self.qdrant_service.create_channel_collection(collection_name)

        # Create channel in DB
        channel = await self.channel_repo.create(
            name=name,
            display_title=display_title,
            description=description,
            created_by=created_by,
            qdrant_collection_name=collection_name,
        )

        await self.db.commit()
        return channel

    async def update_channel(
        self,
        channel_id: UUID,
        display_title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Channel:
        """Update channel metadata (name cannot be changed)."""
        updates = {}
        if display_title is not None:
            updates["display_title"] = display_title
        if description is not None:
            updates["description"] = description

        if not updates:
            raise ValueError("No fields to update")

        channel = await self.channel_repo.update(channel_id, **updates)
        await self.db.commit()
        return channel

    async def soft_delete_channel(self, channel_id: UUID) -> None:
        """Soft delete channel (preserve data, mark as deleted)."""
        await self.channel_repo.soft_delete(channel_id)
        await self.db.commit()

    async def reactivate_channel(self, channel_id: UUID) -> Channel:
        """Reactivate soft-deleted channel."""
        channel = await self.channel_repo.reactivate(channel_id)
        await self.db.commit()
        return channel

    async def get_channel(self, channel_id: UUID) -> Channel:
        """Get channel by ID."""
        channel = await self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")
        return channel

    async def get_channel_by_name(self, name: str) -> Channel:
        """Get channel by URL-safe name."""
        channel = await self.channel_repo.get_by_name(name)
        if not channel:
            raise ValueError(f"Channel '{name}' not found")
        return channel

    async def list_channels(
        self,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> Tuple[List[Channel], int]:
        """List channels with pagination."""
        if include_deleted:
            return await self.channel_repo.list_all(limit=limit, offset=offset)
        else:
            return await self.channel_repo.list_active(limit=limit, offset=offset)

    async def add_video_to_channel(
        self,
        channel_id: UUID,
        youtube_url: str,
        admin_user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Ingest YouTube video into channel collection.

        Full pipeline:
            1. Get channel and validate
            2. Extract video ID from URL
            3. Check if video already in channel
            4. Fetch transcript from SUPADATA API
            5. Create Transcript record (owned by admin)
            6. Chunk transcript text
            7. Generate embeddings
            8. Save chunks to PostgreSQL (with channel_id)
            9. Upsert vectors to channel's Qdrant collection
            10. Create ChannelVideo association
            11. Commit transaction

        Args:
            channel_id: Target channel UUID
            youtube_url: YouTube video URL
            admin_user_id: Admin user adding the video

        Returns:
            Dict with transcript_id, youtube_video_id, chunk_count, metadata

        Raises:
            ValueError: Channel not found, video already in channel
            ExternalAPIError: SUPADATA API error
            InvalidInputError: Invalid YouTube URL
        """
        # Get channel
        channel = await self.get_channel(channel_id)

        # Extract video ID (reuse from transcript_service)
        from app.services.transcript_service import TranscriptService
        transcript_service = TranscriptService()
        youtube_video_id = transcript_service._extract_video_id(youtube_url)

        # Check if video already in channel
        if await self.channel_video_repo.video_exists(channel_id, transcript_id=None):
            # Need to check by youtube_video_id
            # Get transcript by youtube_video_id first
            existing_transcript = await self.transcript_repo.get_by_youtube_video_id(
                youtube_video_id
            )
            if existing_transcript:
                video_exists = await self.channel_video_repo.video_exists(
                    channel_id, existing_transcript.id
                )
                if video_exists:
                    raise ValueError(
                        f"Video {youtube_video_id} already exists in channel"
                    )

        # Use TranscriptService to ingest (but save to channel collection)
        # This is complex - need to modify TranscriptService or duplicate logic

        # For now, let's implement the full pipeline here:

        # 1. Fetch transcript from SUPADATA
        transcript_data = await transcript_service._fetch_transcript(youtube_url)

        # 2. Create Transcript record
        transcript = await self.transcript_repo.create(
            user_id=admin_user_id,  # Owned by admin
            youtube_video_id=youtube_video_id,
            title=transcript_data["title"],
            channel_name=transcript_data["channel_name"],
            duration=transcript_data["duration"],
            transcript_text=transcript_data["transcript_text"],
        )

        # 3. Chunk the text
        chunks = await transcript_service._chunk_text(
            transcript_data["transcript_text"]
        )

        # 4. Generate embeddings
        embeddings = await transcript_service._generate_embeddings(
            [chunk["text"] for chunk in chunks]
        )

        # 5. Save chunks to PostgreSQL with channel_id
        chunk_ids = []
        for chunk_data, embedding in zip(chunks, embeddings):
            chunk = await self.chunk_repo.create(
                user_id=admin_user_id,
                transcript_id=transcript.id,
                chunk_index=chunk_data["index"],
                chunk_text=chunk_data["text"],
                embedding=embedding,
                channel_id=channel_id,  # IMPORTANT: Associate with channel
            )
            chunk_ids.append(str(chunk.id))

        # 6. Upsert to channel's Qdrant collection
        await self.qdrant_service.upsert_chunks(
            chunk_ids=chunk_ids,
            vectors=embeddings,
            user_id=str(admin_user_id),  # Not used for channel collections
            youtube_video_id=youtube_video_id,
            chunk_indices=[c["index"] for c in chunks],
            chunk_texts=[c["text"] for c in chunks],
            collection_name=channel.qdrant_collection_name,  # Channel collection
            channel_id=str(channel_id),  # Add channel_id to payload
        )

        # 7. Create ChannelVideo association
        await self.channel_video_repo.add_video(
            channel_id=channel_id,
            transcript_id=transcript.id,
            added_by=admin_user_id,
        )

        # 8. Commit
        await self.db.commit()

        return {
            "transcript_id": str(transcript.id),
            "youtube_video_id": youtube_video_id,
            "chunk_count": len(chunk_ids),
            "metadata": {
                "title": transcript_data["title"],
                "channel_name": transcript_data["channel_name"],
                "duration": transcript_data["duration"],
            },
        }

    async def remove_video_from_channel(
        self,
        channel_id: UUID,
        transcript_id: UUID,
    ) -> None:
        """
        Remove video from channel.

        Steps:
            1. Verify video is in channel
            2. Get all chunk IDs for this transcript + channel
            3. Delete chunks from Qdrant (channel collection)
            4. Delete chunks from PostgreSQL (where channel_id matches)
            5. Remove ChannelVideo association
            6. Optionally delete Transcript if not used elsewhere

        Note: Transcript and chunks remain if transcript is also in user's library
        """
        # Verify video exists in channel
        if not await self.channel_video_repo.video_exists(channel_id, transcript_id):
            raise ValueError(
                f"Video {transcript_id} not found in channel {channel_id}"
            )

        # Get channel for collection name
        channel = await self.get_channel(channel_id)

        # Get chunk IDs for this transcript + channel
        chunks = await self.chunk_repo.list_by_transcript_and_channel(
            transcript_id=transcript_id,
            channel_id=channel_id,
        )
        chunk_ids = [str(chunk.id) for chunk in chunks]

        # Delete from Qdrant
        if chunk_ids:
            await self.qdrant_service.delete_chunks(
                chunk_ids=chunk_ids,
                collection_name=channel.qdrant_collection_name,
            )

        # Delete chunks from PostgreSQL (only those with this channel_id)
        await self.chunk_repo.delete_by_channel(
            transcript_id=transcript_id,
            channel_id=channel_id,
        )

        # Remove ChannelVideo association
        await self.channel_video_repo.remove_video(channel_id, transcript_id)

        # TODO: Optionally delete Transcript if orphaned (no user owns it, no other channels)

        await self.db.commit()

    async def list_channel_videos(
        self,
        channel_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ChannelVideo], int]:
        """List videos in channel with pagination."""
        return await self.channel_video_repo.list_by_channel(
            channel_id=channel_id,
            limit=limit,
            offset=offset,
        )

    async def get_channel_video_count(self, channel_id: UUID) -> int:
        """Get total video count for channel."""
        return await self.channel_video_repo.count_by_channel(channel_id)
```

**Notes:**
- Service needs additional methods in ChunkRepository:
  - `list_by_transcript_and_channel()`
  - `delete_by_channel()`
  - `get_by_youtube_video_id()` in TranscriptRepository

**Tests:**
- `test_create_channel_success` - Happy path
- `test_create_channel_duplicate_name` - ValueError
- `test_create_channel_qdrant_failure` - ExternalAPIError rollback
- `test_update_channel_metadata`
- `test_soft_delete_and_reactivate_channel`
- `test_list_channels_active_only`
- `test_list_channels_include_deleted`
- `test_add_video_to_channel_full_pipeline` - Mock SUPADATA
- `test_add_video_duplicate_in_channel` - ValueError
- `test_remove_video_from_channel`
- `test_remove_video_not_in_channel` - ValueError

---

## Phase 2.4: Admin API Routes

### File: `app/api/routes/admin/channels.py`

**Router setup:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.schemas.channel import (
    ChannelCreateRequest,
    ChannelUpdateRequest,
    ChannelResponse,
    ChannelListResponse,
    VideoToChannelRequest,
    ChannelVideoListResponse,
)
from app.services.channel_service import ChannelService

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/admin/channels", tags=["admin", "channels"])
```

**Endpoints:**

### 1. Create Channel
```python
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
    """
```

### 2. List Channels
```python
@router.get("/", response_model=ChannelListResponse)
@limiter.limit("30/minute")
async def list_channels(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelListResponse:
    """
    List all channels with pagination (admin only).

    By default excludes soft-deleted channels. Set include_deleted=true to see all.

    Rate limit: 30/minute
    """
```

### 3. Get Channel by ID
```python
@router.get("/{channel_id}", response_model=ChannelResponse)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """Get channel details by ID (admin only). Rate limit: 60/minute"""
```

### 4. Get Channel by Name
```python
@router.get("/by-name/{name}", response_model=ChannelResponse)
@limiter.limit("60/minute")
async def get_channel_by_name(
    request: Request,
    name: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelResponse:
    """Get channel details by URL-safe name (admin only). Rate limit: 60/minute"""
```

### 5. Update Channel
```python
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
    """
```

### 6. Soft Delete Channel
```python
@router.delete("/{channel_id}", status_code=204)
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
    """
```

### 7. Reactivate Channel
```python
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
    """
```

### 8. Add Video to Channel
```python
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
    """
```

### 9. Remove Video from Channel
```python
@router.delete("/{channel_id}/videos/{transcript_id}", status_code=204)
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
    """
```

### 10. List Channel Videos
```python
@router.get("/{channel_id}/videos", response_model=ChannelVideoListResponse)
@limiter.limit("30/minute")
async def list_channel_videos(
    request: Request,
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> ChannelVideoListResponse:
    """
    List videos in channel with pagination (admin only).

    Returns video metadata with added_at timestamp.
    Ordered by added_at descending (newest first).

    Rate limit: 30/minute
    """
```

**Integration with main app:**
- Add to `app/api/routes/__init__.py`
- Mount router in `app/main.py`

**Tests (Integration):**
- `test_create_channel_admin_only` - 201 for admin, 403 for user
- `test_create_channel_duplicate_name` - 409 Conflict
- `test_list_channels_pagination`
- `test_get_channel_by_id_not_found` - 404
- `test_update_channel_metadata` - 200 with updated fields
- `test_soft_delete_and_reactivate_flow`
- `test_add_video_to_channel_success` - Mock SUPADATA
- `test_add_video_duplicate` - 409 Conflict
- `test_remove_video_from_channel` - 204
- `test_list_channel_videos_pagination`

---

## Phase 2.5: Repository Extensions

Need to add methods to existing repositories:

### ChunkRepository (app/db/repositories/chunk_repo.py)

```python
async def list_by_transcript_and_channel(
    self,
    transcript_id: UUID,
    channel_id: UUID,
) -> List[Chunk]:
    """Get all chunks for a transcript in a specific channel."""
    result = await self.session.execute(
        select(Chunk)
        .where(
            Chunk.transcript_id == transcript_id,
            Chunk.channel_id == channel_id,
        )
        .order_by(Chunk.chunk_index)
    )
    return list(result.scalars().all())

async def delete_by_channel(
    self,
    transcript_id: UUID,
    channel_id: UUID,
) -> int:
    """Delete chunks for a transcript in a specific channel. Returns count."""
    result = await self.session.execute(
        delete(Chunk)
        .where(
            Chunk.transcript_id == transcript_id,
            Chunk.channel_id == channel_id,
        )
    )
    return result.rowcount
```

### TranscriptRepository (app/db/repositories/transcript_repo.py)

```python
async def get_by_youtube_video_id(
    self,
    youtube_video_id: str,
) -> Optional[Transcript]:
    """Get transcript by YouTube video ID (first match)."""
    result = await self.session.execute(
        select(Transcript)
        .where(Transcript.youtube_video_id == youtube_video_id)
        .limit(1)
    )
    return result.scalar_one_or_none()
```

**Tests:**
- `test_list_by_transcript_and_channel`
- `test_delete_by_channel_returns_count`
- `test_get_by_youtube_video_id`

---

## Phase 2.6: Error Handling

**Custom exceptions to add (if not exist):**
- `ChannelAlreadyExistsError` - Duplicate channel name
- `ChannelNotFoundError` - Channel ID/name not found
- `VideoAlreadyInChannelError` - Video already added
- `VideoNotInChannelError` - Video not in channel

**Global error handler mapping:**
- `ChannelAlreadyExistsError` → 409 Conflict
- `ChannelNotFoundError` → 404 Not Found
- `VideoAlreadyInChannelError` → 409 Conflict
- `VideoNotInChannelError` → 404 Not Found

---

## Testing Strategy

### Unit Tests (Service Layer)
- Mock repositories and Qdrant service
- Test business logic in isolation
- Cover all error paths
- Target: 15-20 tests, 80%+ coverage

### Integration Tests (API Endpoints)
- Use test database + test Qdrant collection
- Full request/response cycle
- Authentication/authorization checks
- Rate limiting validation
- Target: 25-30 tests, 80%+ coverage

### E2E Tests (Future)
- Complete admin workflows
- Multi-channel scenarios
- Video management flows

---

## File Checklist

**New Files:**
- [ ] `app/dependencies.py` (add `get_admin_user`)
- [ ] `app/schemas/channel.py`
- [ ] `app/services/channel_service.py`
- [ ] `app/api/routes/admin/__init__.py`
- [ ] `app/api/routes/admin/channels.py`
- [ ] `tests/unit/test_channel_service.py`
- [ ] `tests/integration/test_admin_channels_api.py`

**Modified Files:**
- [ ] `app/db/repositories/chunk_repo.py` (add 2 methods)
- [ ] `app/db/repositories/transcript_repo.py` (add 1 method)
- [ ] `app/api/routes/__init__.py` (import admin router)
- [ ] `app/main.py` (mount admin router)

---

## Success Criteria

- [ ] All 10 admin endpoints implemented and documented
- [ ] Admin authentication enforced (403 for non-admins)
- [ ] Full video ingestion pipeline working
- [ ] Qdrant collection created on channel creation
- [ ] Pagination implemented for all list endpoints
- [ ] Rate limiting configured for all endpoints
- [ ] Unit tests: 15-20 tests, 80%+ coverage
- [ ] Integration tests: 25-30 tests, 80%+ coverage
- [ ] All tests passing
- [ ] Code review completed
- [ ] PR merged to `channels` branch

---

## Dependencies

**External:**
- SUPADATA API (for video transcript fetching)
- OpenAI API (for embeddings)
- Qdrant (for vector storage)

**Internal (from PR #1):**
- ChannelRepository
- ChannelVideoRepository
- ChannelConversationRepository
- QdrantService (with channel collection support)
- Database schema (channels, channel_videos, channel_conversations)

---

## Known Limitations & Future Improvements

### Limitations
1. **No bulk operations** - Videos added one at a time
2. **No video metadata update** - Transcript metadata immutable after creation
3. **No channel search** - No full-text search on channel names/descriptions
4. **No usage analytics** - No tracking of channel popularity or video views

### Future Improvements
1. **Bulk Video Import** - CSV/JSON upload with multiple YouTube URLs
2. **Channel Search API** - Full-text search with filters
3. **Video Metadata Refresh** - Re-fetch metadata from YouTube
4. **Channel Templates** - Pre-configured channel types with settings
5. **Channel Categories** - Organize channels by topic/category
6. **Usage Analytics** - Track views, messages, popular videos
7. **Channel Permissions** - Fine-grained access control per channel

---

## Review Checklist

- [ ] Service layer implements all business logic
- [ ] Admin dependency enforces role='admin'
- [ ] All endpoints have proper authentication
- [ ] All endpoints have rate limiting
- [ ] Pydantic schemas validate all inputs
- [ ] Error handling covers all edge cases
- [ ] Repository extensions tested
- [ ] Integration tests use test DB + Qdrant
- [ ] Code follows existing patterns (TranscriptService style)
- [ ] Documentation includes examples
- [ ] All tests passing (80%+ coverage)
- [ ] PR description comprehensive
- [ ] Code review completed
- [ ] PR merged to channels branch

---

**Status:** 🔄 Ready to implement
**Estimated Effort:** 6-8 hours (TDD approach)
**Next Step:** Create feature branch and start Phase 2.1 (Admin Dependency)

**Author:** Claude Code
**Date:** 2025-11-03
