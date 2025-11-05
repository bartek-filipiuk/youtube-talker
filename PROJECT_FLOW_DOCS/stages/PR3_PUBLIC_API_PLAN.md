# PR #3: Public API Endpoints - Implementation Plan

## Overview

**Objective:** Implement user-facing authenticated APIs for channel discovery and channel conversation management.

**Branch:** `feature/channels-pr3-public-api`
**Target:** `channels`
**Dependencies:** PR #1 (Foundation), PR #2 (Admin API)
**Status:** 📋 Planning
**Estimated LOC:** ~1,100 lines (code + tests)

### Scope

This PR adds **8 authenticated endpoints** enabling users to:
1. **Discover channels** - Browse available channels (authenticated users only)
2. **Manage channel conversations** - Create, read, and delete personal conversations with channels
3. **Prepare for chat** - Set up conversation context before WebSocket chat (PR #4)

### Key Features

- ✅ **All endpoints require authentication** - Consistent security model
- ✅ Channel discovery for authenticated users
- ✅ Channel conversation CRUD (authenticated users)
- ✅ Per-user channel conversations (isolated, private)
- ✅ Integration with existing conversation patterns
- ✅ Consistent with PR #2 admin APIs
- ✅ Rate limiting per endpoint
- ✅ Efficient testing strategy (80%+ coverage, reduced schema tests)
- ✅ Public-safe schemas (hide admin fields)

---

## Implementation Phases

### Phase 3.1: Public Channel Schemas

**Goal:** Define Pydantic schemas for public channel APIs (safe, user-facing).

**File:** `app/schemas/channel_public.py` (new)

**Schemas to Create:**

```python
# 1. ChannelPublicResponse
# - Public-safe channel metadata (no admin fields like created_by)
# - Fields: id, name, display_title, description, video_count, created_at
# - Used in: List channels, Get channel details

# 2. VideoInChannelResponse
# - Safe video metadata for public consumption
# - Fields: transcript_id, youtube_video_id, title, channel_name, duration, added_at
# - Used in: List videos in channel

# 3. ChannelVideoListResponse
# - Paginated list of videos in channel
# - Fields: videos, total, limit, offset
# - Used in: List videos endpoint

# 4. ChannelListResponse
# - Paginated list of channels
# - Fields: channels, total, limit, offset
# - Used in: List channels endpoint

# 5. ChannelConversationResponse
# - Channel conversation metadata
# - Fields: id, channel_id, user_id, channel_name, channel_display_title, created_at, updated_at
# - Used in: Get/create conversation, List conversations

# 6. ChannelConversationDetailResponse
# - Full conversation with messages
# - Fields: conversation (ChannelConversationResponse), messages (List[MessageResponse])
# - Used in: Get conversation detail

# 7. ChannelConversationListResponse
# - Paginated list of user's channel conversations
# - Fields: conversations, total, limit, offset
# - Used in: List conversations endpoint
```

**Testing:**
- Create `tests/unit/test_channel_public_schemas.py`
- **Reduced scope:** Test only critical validations (not exhaustive edge cases)
- Test serialization from ORM models (main path)
- Test key field constraints only
- Target: 100% coverage for schemas

**Success Criteria:**
- [ ] 7 schemas defined with proper validation
- [ ] All schemas have JSON schema examples
- [ ] Tests pass (estimated 6-8 tests) ✅ Reduced from 12-15
- [ ] Coverage: 100%

---

### Phase 3.2: Service Layer Extensions

**Goal:** Extend ChannelService with user-facing methods for channel discovery and conversation management.

**File:** `app/services/channel_service.py` (modify)

**New Methods to Add:**

```python
# Channel Discovery (Public)

async def list_public_channels(
    self,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Channel], int]:
    """
    List active channels for public discovery.

    - Only returns non-deleted channels
    - Includes video count for each channel
    - Paginated
    """
    return await self.channel_repo.list_active(limit=limit, offset=offset)


async def get_public_channel(self, channel_id: UUID) -> Channel:
    """
    Get channel by ID for public viewing.

    Raises:
        ChannelNotFoundError: Channel not found or deleted
    """
    channel = await self.channel_repo.get_by_id(channel_id)
    if not channel or channel.deleted_at is not None:
        raise ChannelNotFoundError(f"Channel {channel_id} not found")
    return channel


async def get_public_channel_by_name(self, name: str) -> Channel:
    """
    Get channel by URL-safe name for public viewing.

    Raises:
        ChannelNotFoundError: Channel not found or deleted
    """
    channel = await self.channel_repo.get_by_name(name)
    if not channel or channel.deleted_at is not None:
        raise ChannelNotFoundError(f"Channel '{name}' not found")
    return channel


# Channel Conversations (Authenticated)

async def get_or_create_channel_conversation(
    self,
    channel_id: UUID,
    user_id: UUID,
) -> ChannelConversation:
    """
    Get or create user's conversation with a channel.

    - Verifies channel exists and is active
    - Creates new conversation if user doesn't have one
    - Returns existing conversation if user already has one

    Raises:
        ChannelNotFoundError: Channel not found or deleted
    """
    # Verify channel exists and is active
    channel = await self.get_public_channel(channel_id)

    # Get or create conversation
    conversation = await self.channel_conversation_repo.get_or_create(
        channel_id=channel_id,
        user_id=user_id,
    )
    await self.db.flush()
    return conversation


async def list_user_channel_conversations(
    self,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[ChannelConversation], int]:
    """
    List user's channel conversations with pagination.

    - Ordered by updated_at DESC (most recent first)
    - Includes channel metadata
    """
    return await self.channel_conversation_repo.list_by_user(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


async def get_channel_conversation(
    self,
    conversation_id: UUID,
    user_id: UUID,
) -> ChannelConversation:
    """
    Get channel conversation by ID with ownership verification.

    Raises:
        ConversationNotFoundError: Conversation not found
        ConversationAccessDeniedError: User doesn't own conversation
    """
    conversation = await self.channel_conversation_repo.get_by_id(conversation_id)

    if not conversation:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found")

    if conversation.user_id != user_id:
        raise ConversationAccessDeniedError(
            f"User {user_id} does not own conversation {conversation_id}"
        )

    return conversation


async def delete_channel_conversation(
    self,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    """
    Delete channel conversation with ownership verification.

    - Verifies user owns the conversation
    - Cascade deletes all messages

    Raises:
        ConversationNotFoundError: Conversation not found
        ConversationAccessDeniedError: User doesn't own conversation
    """
    # Verify ownership
    await self.get_channel_conversation(conversation_id, user_id)

    # Delete conversation (messages cascade via DB constraint)
    await self.channel_conversation_repo.delete(conversation_id)
```

**Testing:**
- Extend `tests/unit/test_channel_service.py` (or create new test file)
- Mock repository methods
- Test each service method independently
- Test error cases (not found, access denied, deleted channels)
- Target: 80%+ coverage

**Success Criteria:**
- [ ] 7 new methods added to ChannelService
- [ ] All methods properly documented
- [ ] Error handling consistent with existing patterns
- [ ] Service tests pass (estimated 15-20 new tests)

---

### Phase 3.3: Repository Extensions

**Goal:** Add method to MessageRepository for channel conversation messages.

**File:** `app/db/repositories/message_repo.py` (modify)

**New Method:**

```python
async def list_by_channel_conversation(
    self,
    channel_conversation_id: UUID,
) -> List[Message]:
    """
    Get all messages for a channel conversation in chronological order.

    Args:
        channel_conversation_id: UUID of channel conversation

    Returns:
        List[Message]: Messages ordered by created_at ASC
    """
    result = await self.session.execute(
        select(Message)
        .where(Message.channel_conversation_id == channel_conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
```

**Testing:**
- Extend `tests/unit/test_message_repo.py`
- Test message retrieval for channel conversations
- Test ordering (chronological)
- Test empty conversations

**Success Criteria:**
- [ ] Method added to MessageRepository
- [ ] Tests pass (estimated 2-3 new tests)
- [ ] Coverage maintained

---

### Phase 3.4: Channel Discovery API Routes (Authenticated)

**Goal:** Implement 4 authenticated channel discovery endpoints.

**File:** `app/api/routes/channels.py` (new)

**Endpoints:**

```python
router = APIRouter(prefix="/api/channels", tags=["channels"])

# 1. List Active Channels (Authenticated)
@router.get("", response_model=ChannelListResponse)
@limiter.limit("60/minute")
async def list_channels(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: AsyncSession = Depends(get_db),
) -> ChannelListResponse:
    """
    List all active channels for discovery.

    - **Requires authentication**
    - Only returns non-deleted channels
    - Ordered by name (ascending) for now
    - Includes video count per channel
    - Supports pagination

    Rate Limit: 60 requests/minute

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


# 2. Get Channel by ID (Authenticated)
@router.get("/{channel_id}", response_model=ChannelPublicResponse)
@limiter.limit("60/minute")
async def get_channel(
    request: Request,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: AsyncSession = Depends(get_db),
) -> ChannelPublicResponse:
    """
    Get channel details by ID.

    - **Requires authentication**
    - Returns 404 if channel deleted or not found
    - Includes video count

    Rate Limit: 60 requests/minute

    Raises:
        401: Not authenticated
        404: Channel not found or deleted
    """


# 3. Get Channel by Name (Authenticated)
@router.get("/by-name/{name}", response_model=ChannelPublicResponse)
@limiter.limit("60/minute")
async def get_channel_by_name(
    request: Request,
    name: str,
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: AsyncSession = Depends(get_db),
) -> ChannelPublicResponse:
    """
    Get channel details by URL-safe name.

    - **Requires authentication**
    - Returns 404 if channel deleted or not found
    - Useful for friendly URLs like /channels/python-tutorials

    Rate Limit: 60 requests/minute

    Raises:
        401: Not authenticated
        404: Channel not found or deleted
    """


# 4. List Videos in Channel (Authenticated)
@router.get("/{channel_id}/videos", response_model=ChannelVideoListResponse)
@limiter.limit("60/minute")
async def list_channel_videos(
    request: Request,
    channel_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),  # ✅ AUTH REQUIRED
    db: AsyncSession = Depends(get_db),
) -> ChannelVideoListResponse:
    """
    List videos in a channel.

    - **Requires authentication**
    - Returns 404 if channel deleted or not found
    - Videos ordered by added_at DESC (newest first)
    - Supports pagination

    Rate Limit: 60 requests/minute

    Raises:
        401: Not authenticated
        404: Channel not found or deleted
    """
```

**Rate Limiting Strategy:**
- All read operations: 60/min (consistent for authenticated users)
- Simpler than admin API (no heavy mutations)
- Track usage per authenticated user

**Testing:**
- Create `tests/integration/test_channel_api.py`
- Test each endpoint with valid/invalid inputs
- Test authentication (401 without token)
- Test pagination
- Test 404 responses for deleted/missing channels
- Test rate limiting

**Success Criteria:**
- [ ] 4 endpoints implemented
- [ ] All endpoints properly documented
- [ ] Authentication enforced on all endpoints
- [ ] Rate limiting configured
- [ ] Integration tests pass (estimated 8-10 tests) ✅ Reduced from 10-12

---

### Phase 3.5: Channel Conversation API Routes

**Goal:** Implement 4 authenticated endpoints for channel conversation management.

**File:** `app/api/routes/channel_conversations.py` (new)

**Endpoints:**

```python
router = APIRouter(prefix="/api/channels", tags=["channel-conversations"])

# 1. Get or Create Channel Conversation
@router.post("/{channel_id}/conversations", response_model=ChannelConversationResponse, status_code=201)
@limiter.limit("20/minute")
async def get_or_create_conversation(
    request: Request,
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationResponse:
    """
    Get or create user's conversation with a channel.

    - Requires authentication
    - Returns existing conversation if user already has one with this channel
    - Creates new conversation if first time chatting with channel
    - Returns 404 if channel deleted or not found

    Rate Limit: 20 requests/minute

    Raises:
        401: Not authenticated
        404: Channel not found or deleted

    Example:
        >>> POST /api/channels/550e8400-e29b-41d4-a716-446655440000/conversations
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "id": "...",
        >>>   "channel_id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "user_id": "...",
        >>>   "channel_name": "python-tutorials",
        >>>   "channel_display_title": "Python Tutorials",
        >>>   "created_at": "2025-01-15T10:30:00Z",
        >>>   "updated_at": "2025-01-15T10:30:00Z"
        >>> }
    """


# 2. List User's Channel Conversations
@router.get("/conversations", response_model=ChannelConversationListResponse)
@limiter.limit("60/minute")
async def list_channel_conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationListResponse:
    """
    List all channel conversations for authenticated user.

    - Requires authentication
    - Returns conversations ordered by updated_at DESC (most recent first)
    - Includes channel metadata (name, display_title)
    - Supports pagination

    Rate Limit: 60 requests/minute

    Example:
        >>> GET /api/channels/conversations?limit=20&offset=0
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversations": [...],
        >>>   "total": 20,
        >>>   "limit": 20,
        >>>   "offset": 0
        >>> }
    """


# 3. Get Channel Conversation Detail with Messages
@router.get("/conversations/{conversation_id}", response_model=ChannelConversationDetailResponse)
@limiter.limit("120/minute")
async def get_conversation_detail(
    request: Request,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelConversationDetailResponse:
    """
    Get channel conversation details with all messages.

    - Requires authentication
    - Verifies user owns the conversation
    - Returns conversation metadata + all messages in chronological order

    Rate Limit: 120 requests/minute

    Raises:
        401: Not authenticated
        403: User doesn't own this conversation
        404: Conversation not found

    Example:
        >>> GET /api/channels/conversations/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: {
        >>>   "conversation": {...},
        >>>   "messages": [...]
        >>> }
    """


# 4. Delete Channel Conversation
@router.delete("/conversations/{conversation_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_conversation(
    request: Request,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete user's channel conversation and all messages.

    - Requires authentication
    - Verifies user owns the conversation
    - Cascade deletes all messages via DB constraint
    - Returns 204 No Content on success

    Rate Limit: 20 requests/minute

    Raises:
        401: Not authenticated
        403: User doesn't own this conversation
        404: Conversation not found

    Example:
        >>> DELETE /api/channels/conversations/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
```

**Route Prefix Note:**
- All channel conversation routes use `/api/channels` prefix
- This creates logical grouping:
  - `/api/channels` - Channel discovery
  - `/api/channels/{id}/conversations` - Start chatting with channel
  - `/api/channels/conversations` - Manage user's channel conversations

**Testing:**
- Create `tests/integration/test_channel_conversation_api.py`
- Test each endpoint with valid/invalid inputs
- Test authentication (401 without token)
- Test ownership verification (403 for other user's conversations)
- Test 404 responses
- Test pagination for list endpoint

**Success Criteria:**
- [ ] 4 endpoints implemented
- [ ] All endpoints properly documented
- [ ] Rate limiting configured
- [ ] Authentication enforced
- [ ] Ownership verification working
- [ ] Integration tests pass (estimated 12-15 tests)

---

### Phase 3.6: Register Routes in Main App

**Goal:** Register new routers in FastAPI application.

**File:** `app/main.py` (modify)

**Changes:**

```python
# Add imports
from app.api.routes import (
    auth,
    transcripts,
    health,
    conversations,
    channels,  # NEW
    channel_conversations,  # NEW
)

# Register routers
app.include_router(auth.router)
app.include_router(transcripts.router)
app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(channels_router)  # Admin routes (already exists from PR #2)
app.include_router(channels.router)  # NEW: Public routes
app.include_router(channel_conversations.router)  # NEW: Conversation routes
```

**Testing:**
- Run full test suite to ensure no regressions
- Test all endpoints are accessible
- Verify OpenAPI docs show new endpoints

**Success Criteria:**
- [ ] Both routers registered
- [ ] No import conflicts
- [ ] OpenAPI docs updated automatically
- [ ] All tests pass

---

## Testing Strategy

### Unit Tests (Estimated 25-30 tests)

**Schemas** (`test_channel_public_schemas.py`):
- ✅ **REDUCED:** Test critical validations only (not exhaustive)
- Main path serialization from ORM models
- Key field constraints only
- Target: 6-8 tests (down from 12-15), 100% coverage

**Service Layer** (`test_channel_service.py` extension):
- Test each new service method
- Mock repository methods
- Test error cases (not found, access denied)
- Target: 15-20 tests, 80%+ coverage

**Repository** (`test_message_repo.py` extension):
- Test channel conversation message retrieval
- Target: 2-3 tests

### Integration Tests (Estimated 20-25 tests)

**Channel Discovery API** (`test_channel_api.py`):
- Test all 4 authenticated endpoints
- Test authentication (401 without token)
- Test pagination
- Test 404 responses for deleted/missing channels
- Test rate limiting
- Target: 8-10 tests (down from 10-12)

**Channel Conversation API** (`test_channel_conversation_api.py`):
- Test all 4 authenticated endpoints
- Test authentication (401)
- Test ownership verification (403)
- Test 404 responses
- Test pagination
- Test cascade deletion of messages
- Target: 10-12 tests (down from 12-15)

**End-to-End Flows** (`test_channel_e2e.py` - optional):
- Full user journey: Discover channel → Create conversation → Get conversation → Delete
- Test conversation isolation between users
- Target: 2-3 tests (down from 3-5)

### Coverage Goals

- **Overall Target:** 80%+
- **Schemas:** 100% (fully testable)
- **Service Layer:** 85%+
- **API Routes:** 90%+ (integration tests)

### Total Tests: ~48-57 (reduced from 55-65)

**Breakdown:**
- Unit: 25-30 tests (6-8 schemas + 15-20 service + 2-3 repo)
- Integration: 20-25 tests (8-10 channel API + 10-12 conversation API + 2-3 E2E)

---

## Security Considerations

### Authentication & Authorization

1. **All Endpoints Require Authentication:**
   - ✅ **Consistent security model** - All 8 endpoints use `Depends(get_current_user)`
   - Users must be logged in to discover or interact with channels
   - `get_current_user` dependency enforces authentication (401 if missing/invalid token)
   - Benefits: Track usage, analytics, simpler permissions model

2. **Ownership Verification (Conversation Endpoints):**
   - Service layer verifies user owns channel conversation
   - Raises `ConversationAccessDeniedError` (403) if access denied
   - Prevents users from accessing other users' conversations

3. **No Admin Access:**
   - These endpoints are user-facing only (not admin)
   - Admin endpoints remain separate (`/api/admin/channels`)
   - Clear separation of concerns

### Data Privacy

1. **Channel Data:**
   - User-safe schemas exclude admin fields (`created_by`, `qdrant_collection_name`)
   - Only active (non-deleted) channels visible to users
   - Soft-deleted channels return 404

2. **Conversation Isolation:**
   - Each user has separate conversation with each channel
   - Users cannot see other users' channel conversations
   - Messages tied to channel_conversation_id (per-user, private)

3. **Soft Delete Handling:**
   - Deleted channels return 404 (not visible to authenticated users)
   - Existing conversations with deleted channels remain accessible (for now)
   - Future: Consider hiding conversations with deleted channels

### Input Validation

1. **Pydantic Validation:**
   - All request bodies validated via schemas
   - Query parameters validated via FastAPI Query()
   - UUID validation for all IDs

2. **Rate Limiting:**
   - All endpoints: 20-60 req/min (tracked per authenticated user)
   - Discovery endpoints: 60/min (read-heavy)
   - Conversation mutations: 20/min (write-heavy)
   - Prevents abuse and DoS

---

## API Documentation

### OpenAPI (Swagger) Integration

All endpoints will automatically appear in:
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI

### Endpoint Summary Table

| Endpoint | Method | Auth | Rate Limit | Description |
|----------|--------|------|------------|-------------|
| `/api/channels` | GET | **Yes** | 60/min | List active channels |
| `/api/channels/{id}` | GET | **Yes** | 60/min | Get channel by ID |
| `/api/channels/by-name/{name}` | GET | **Yes** | 60/min | Get channel by name |
| `/api/channels/{id}/videos` | GET | **Yes** | 60/min | List videos in channel |
| `/api/channels/{id}/conversations` | POST | **Yes** | 20/min | Get/create conversation |
| `/api/channels/conversations` | GET | **Yes** | 60/min | List user's conversations |
| `/api/channels/conversations/{id}` | GET | **Yes** | 60/min | Get conversation detail |
| `/api/channels/conversations/{id}` | DELETE | **Yes** | 20/min | Delete conversation |

**Note:** All endpoints require authentication (`get_current_user` dependency)

---

## Error Handling

### HTTP Status Codes

- `200 OK` - Successful GET request
- `201 Created` - Successful POST (conversation created)
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Invalid input (Pydantic validation)
- `401 Unauthorized` - Missing or invalid auth token
- `403 Forbidden` - Valid auth but no access (ownership)
- `404 Not Found` - Channel or conversation not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Unexpected server error

### Custom Exceptions

Reuse existing exceptions from `app/core/errors.py`:
- `ChannelNotFoundError` → 404
- `ConversationNotFoundError` → 404
- `ConversationAccessDeniedError` → 403
- `AuthenticationError` → 401

No new exceptions needed for this PR.

---

## File Checklist

### New Files (7)

- [ ] `app/schemas/channel_public.py` - Public channel schemas (7 schemas)
- [ ] `app/api/routes/channels.py` - Public channel routes (4 endpoints)
- [ ] `app/api/routes/channel_conversations.py` - Conversation routes (4 endpoints)
- [ ] `tests/unit/test_channel_public_schemas.py` - Schema tests (12-15 tests)
- [ ] `tests/integration/test_channel_public_api.py` - Public API tests (10-12 tests)
- [ ] `tests/integration/test_channel_conversation_api.py` - Conversation API tests (12-15 tests)
- [ ] `PROJECT_FLOW_DOCS/stages/PR3_PUBLIC_API_PLAN.md` - This document

### Modified Files (3)

- [ ] `app/services/channel_service.py` - Add 7 user-facing methods
- [ ] `app/db/repositories/message_repo.py` - Add 1 method for channel conversation messages
- [ ] `app/main.py` - Register 2 new routers

### Documentation Files (1)

- [ ] `PROJECT_FLOW_DOCS/stages/CHANNELS_FEATURE_PLAN.md` - Update PR #2 status, add PR #3 details

---

## Dependencies

### Required Packages (Already Installed)

- `fastapi` - API framework
- `pydantic` - Schema validation
- `sqlalchemy[asyncio]` - Database ORM
- `slowapi` - Rate limiting
- `loguru` - Logging

### Database

- PostgreSQL 14+
- No new migrations needed (schema already in place from PR #1)

---

## Implementation Order

**Recommended sequence for TDD:**

1. **Phase 3.1:** Schemas first (easy to test, no dependencies)
2. **Phase 3.3:** Repository extension (simple, needed by service)
3. **Phase 3.2:** Service layer (depends on repos, needed by routes)
4. **Phase 3.4:** Public channel routes (simpler, no auth)
5. **Phase 3.5:** Channel conversation routes (more complex, auth + ownership)
6. **Phase 3.6:** Register routes in main app (final integration)

---

## Success Criteria

### Functional Requirements

- [ ] All 8 endpoints implemented and accessible
- [ ] Public channel discovery works without authentication
- [ ] Channel conversations require authentication
- [ ] Ownership verification prevents unauthorized access
- [ ] Pagination works correctly for all list endpoints
- [ ] Rate limiting enforced on all endpoints
- [ ] 404 responses for deleted/missing channels
- [ ] Cascade deletion works for conversations → messages

### Code Quality

- [ ] All tests pass (unit + integration)
- [ ] 80%+ overall test coverage
- [ ] 100% schema coverage
- [ ] Code follows existing patterns (consistent with PR #2)
- [ ] All functions have docstrings
- [ ] Type hints used throughout
- [ ] No linting errors (`ruff check app/`)
- [ ] Code formatted (`black app/`)

### Documentation

- [ ] All endpoints documented with examples
- [ ] OpenAPI docs auto-generated and accurate
- [ ] Schemas have JSON schema examples
- [ ] PR description comprehensive
- [ ] CHANNELS_FEATURE_PLAN.md updated

---

## Known Limitations & Future Improvements

### Current Limitations

1. **No Search/Filter:**
   - List channels endpoint has no search or filtering
   - Future: Add query parameters for search by name, tags, etc.

2. **No Channel Ordering Options:**
   - Channels listed by name (ascending) only
   - Future: Allow sorting by video_count, created_at, popularity

3. **No Channel Statistics:**
   - No usage stats (total users, total chats, etc.)
   - Future: Add analytics endpoints

4. **No Conversation Context Limits:**
   - No limit on message history per conversation
   - Future: Add pagination for messages within conversation

5. **Deleted Channel Handling:**
   - Conversations with deleted channels remain accessible
   - Future: Consider hiding or archiving these conversations

### Future Improvements (Not in This PR)

1. **Search & Discovery:**
   - Full-text search for channels
   - Filter by tags, categories, popularity
   - Recommended channels for users

2. **Channel Analytics:**
   - Track channel usage (views, chats, active users)
   - Popular videos within channel
   - Engagement metrics

3. **Conversation Features:**
   - Rename conversation (custom titles)
   - Archive conversations (soft delete)
   - Export conversation history

4. **Performance:**
   - Caching for channel list (Redis)
   - Pagination for large message histories
   - Eager loading for channel metadata

5. **Notifications:**
   - Notify users when new videos added to channels they follow
   - Email summaries of channel activity

---

## Post-Merge Checklist

### Before Merging

- [ ] All tests passing locally
- [ ] Coverage report shows 80%+
- [ ] Manual testing via Swagger UI
- [ ] Test with real channel data
- [ ] Review OpenAPI docs
- [ ] Check rate limiting works
- [ ] Verify error responses

### After Merging to `channels` Branch

- [ ] Update CHANNELS_FEATURE_PLAN.md (mark PR #3 as merged)
- [ ] Document any issues discovered
- [ ] Plan PR #4 (WebSocket + RAG modifications)

---

## Estimated Timeline

**Total Effort:** 5-7 hours (reduced from 6-8 hours)

- Phase 3.1 (Schemas): 1 hour (reduced - fewer tests)
- Phase 3.2 (Service): 2 hours
- Phase 3.3 (Repo): 0.5 hours
- Phase 3.4 (Channel API): 1.5 hours (simpler - consistent auth)
- Phase 3.5 (Conversation API): 1.5 hours (reduced tests)
- Phase 3.6 (Integration): 0.5 hours
- Testing & Fixes: 1 hour

**Savings:**
- Simpler auth model (no public/private split) = -30 min
- Reduced schema tests (50% fewer) = -30 min
- Reduced integration tests = -30 min

---

## Architecture Decisions (Confirmed)

✅ **All endpoints require authentication** - Decided by user
- Users must log in to discover channels
- Simpler security model, better tracking

✅ **Conversation creation is idempotent**
- POST /api/channels/{id}/conversations uses get_or_create pattern
- Always returns 201 Created (even if conversation already exists)

✅ **Deleted channel handling**
- Soft-deleted channels return 404 to users
- Existing conversations with deleted channels remain accessible (for now)
- Future: Consider hiding/archiving conversations with deleted channels

✅ **Channel ordering**
- List endpoint orders by name (ascending) for now
- Future: Add sorting options (video_count, created_at, popularity)

---

**Plan Created:** 2025-11-03
**Plan Updated:** 2025-11-03 (auth-required clarification)
**Author:** Claude Code
**Status:** ✅ Approved and Ready for Implementation
