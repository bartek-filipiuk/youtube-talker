# Channel Feature Implementation Plan

**Feature:** Admin-managed content channels for curated YouTube video collections

**Created:** 2025-11-03
**Status:** Planning Complete - Ready for Implementation
**Estimated Time:** 22-30 hours (updated with frontend + gap fixes)

---

## Requirements Summary

### Core Features
- ✅ Admins create channels with unique names (URL slugs) and descriptions
- ✅ Admins load YouTube videos to channels (no limit)
- ✅ All authenticated users can access and chat with any channel
- ✅ Each user has separate conversation history per channel
- ✅ Each channel has dedicated Qdrant collection for vector isolation
- ✅ Channels reuse same intents as personal chats (context-aware admin checks)
- ✅ Soft delete for channels (mark inactive, preserve data)
- ✅ REST API + simple HTML admin panel for management
- ✅ Channel metadata returns summary + 5 latest videos (full list in sidebar)

### Architectural Decisions
- **Access Model:** Public - all authenticated users can access all channels
- **Chat History:** Per-user conversations - each user has their own chat thread per channel
- **Vector Storage:** Separate Qdrant collection per channel (e.g., "channel_python_basics")
- **Admin Intents:** Reuse existing intents with context-aware checks
- **Metadata Detail:** Summary with video count + 5 latest videos
- **Admin Panel:** REST API + simple HTML admin page
- **Channel Naming:** Immutable - channel name is permanent identifier
- **Channel Deletion:** Soft delete - mark channel inactive but keep data

---

## ⚠️ Gap Analysis & Mitigations

### Critical Gaps Identified & Fixed

#### 1. **Message Model Relationship** ⚠️ CRITICAL
**Problem:** Messages currently only reference `conversations` table, but we're creating separate `channel_conversations` table.

**Solution:** Add `channel_conversation_id` (nullable) to messages table with constraint ensuring exactly one conversation type is set.

**Fix Location:** Phase 1.1 (Migration)

---

#### 2. **Frontend Not Addressed** ⚠️ MAJOR
**Problem:** No frontend components for channels.

**Solution:** Add Phase 8.5 for frontend implementation.

**Components Needed:**
- Channel list page
- Channel chat interface (with description at top)
- Video sidebar for channels
- WebSocket connection logic for channel mode
- Navigation updates

**Fix Location:** NEW Phase 8.5

---

#### 3. **Video Duplication Handling** ⚠️ MEDIUM
**Problem:** User uploads video personally, then admin adds same video to channel → duplicate transcripts/chunks/vectors.

**Solution:** Check if transcript exists by youtube_video_id before ingestion. Reuse transcript, create new chunks with channel_id.

**Fix Location:** Phase 7.1 (Ingestion Service)

---

#### 4. **Collection Name Sanitization** ⚠️ MEDIUM
**Problem:** Channel name "python-basics" needs conversion to valid Qdrant collection name.

**Solution:** Add `sanitize_collection_name()` function:
```python
def sanitize_collection_name(channel_name: str) -> str:
    # "python-basics" → "channel_python_basics"
    return f"channel_{channel_name.replace('-', '_')}"
```

**Fix Location:** Phase 2.1

---

#### 5. **Conversation History Context** ⚠️ MEDIUM
**Problem:** WebSocket handler gets last 10 messages but must use correct conversation type.

**Solution:** Explicitly check conversation type:
```python
if channel_context:
    history = await message_repo.get_last_n(channel_conversation_id, n=10)
else:
    history = await message_repo.get_last_n(conversation_id, n=10)
```

**Fix Location:** Phase 5.1

---

#### 6. **Chunk Cleanup on Video Removal** ⚠️ MEDIUM
**Problem:** Removing video from channel must delete both DB chunks (CASCADE) and Qdrant vectors (explicit).

**Solution:** Call `qdrant_service.delete_chunks(chunk_ids, collection_name)` in DELETE video endpoint.

**Fix Location:** Phase 3.3

---

#### 7. **Rollback Strategy** ⚠️ MEDIUM
**Problem:** Channel creation succeeds in DB but Qdrant collection creation fails → orphaned record.

**Solution:** Wrap in transaction with try/except:
```python
try:
    channel = await channel_repo.create(...)
    await qdrant_service.create_channel_collection(...)
    await db.commit()
except Exception:
    await db.rollback()
    # Clean up Qdrant if partially created
    raise
```

**Fix Location:** Phase 3.3

---

#### 8. **Custom Error Handling** ⚠️ LOW
**Problem:** Need consistent error format for channel-specific errors.

**Solution:** Add custom exceptions:
```python
class ChannelNotFoundError(HTTPException): status_code=404
class ChannelInactiveError(HTTPException): status_code=410
class InsufficientChannelPermissionError(HTTPException): status_code=403
```

**Fix Location:** Phase 3.1

---

#### 9. **WebSocket Connection Manager** ⚠️ LOW
**Problem:** ConnectionManager needs to differentiate channel vs personal chat connections.

**Solution:** Add optional channel_name grouping to ConnectionManager.

**Fix Location:** Phase 5.1

---

#### 10. **Rate Limiting** ⚠️ LOW
**Problem:** Should channels have different rate limits than personal chat?

**Solution:** Keep same rate limiting initially (can adjust post-MVP).

**Fix Location:** N/A (no change needed)

---

## Pull Request Strategy

### Strategy: By Architecture Layer (6 PRs)

**Why This Approach:**
- ✅ Clear dependencies - each PR builds on previous
- ✅ Easier review - related code grouped together
- ✅ Better testing - test each layer independently
- ✅ Safer rollback - revert specific layers if issues
- ✅ Parallel work possible on later PRs once foundation is merged

---

### PR #1: Foundation - Database Schema & Vector Storage
**Phases:** 1-2 (Database + Qdrant)

**Scope:**
- [ ] Alembic migrations (4 new tables, modify chunks + messages)
- [ ] SQLAlchemy models (Channel, ChannelVideo, ChannelConversation)
- [ ] Repositories (3 new: channel, channel_video, channel_conversation)
- [ ] Qdrant service extensions (collection management)
- [ ] Message model updates (add channel_conversation_id)

**Tests:**
- [ ] Unit tests for all repository methods
- [ ] Qdrant service tests (mock client)
- [ ] Migration up/down tests

**Depends On:** Nothing (first PR)

**Time Estimate:** 6-8 hours
**Files Changed:** ~18 files
**Risk Level:** LOW (isolated to data layer)

**Merge Criteria:**
- ✅ All migrations applied successfully
- ✅ All unit tests pass (80%+ coverage)
- ✅ Models properly related
- ✅ Qdrant collections can be created/deleted

---

### PR #2: Admin API - Channel Management
**Phase:** 3 (Admin REST endpoints)

**Scope:**
- [ ] Admin middleware (`require_admin()` dependency)
- [ ] Pydantic schemas (ChannelCreate, ChannelUpdate, ChannelResponse, etc.)
- [ ] Admin REST endpoints (11 endpoints total):
  - GET /api/admin/channels (list)
  - POST /api/admin/channels (create with transaction)
  - GET /api/admin/channels/{name} (detail)
  - PUT /api/admin/channels/{name} (update)
  - DELETE /api/admin/channels/{name} (soft delete)
  - POST /api/admin/channels/{name}/restore (reactivate)
  - POST /api/admin/channels/{name}/videos (add video)
  - DELETE /api/admin/channels/{name}/videos/{id} (remove video)
  - GET /api/admin/channels/{name}/videos (list videos)
- [ ] Custom exceptions (ChannelNotFoundError, etc.)
- [ ] Transaction handling + rollback logic

**Tests:**
- [ ] Integration tests for all admin endpoints
- [ ] Test permission enforcement (non-admin access denied)
- [ ] Test rollback scenarios
- [ ] Test duplicate video handling

**Depends On:** PR #1

**Time Estimate:** 4-5 hours
**Files Changed:** ~10 files
**Risk Level:** MEDIUM (admin-only, limited user impact)

**Merge Criteria:**
- ✅ All admin endpoints working
- ✅ Proper error handling and validation
- ✅ Admin-only access enforced
- ✅ Transactions properly handled
- ✅ Integration tests pass

---

### PR #3: Public API - User Access
**Phase:** 4 (Public REST endpoints)

**Scope:**
- [ ] Public REST endpoints (4 endpoints):
  - GET /api/channels (list active channels)
  - GET /api/channels/{name} (channel info + summary)
  - GET /api/channels/{name}/videos (list all videos for sidebar)
  - GET /api/channels/{name}/conversation (get/create user conversation)
- [ ] Pydantic schemas for public responses
- [ ] Active channel filtering

**Tests:**
- [ ] Integration tests for all public endpoints
- [ ] Test inactive channels return 404
- [ ] Test authentication required
- [ ] Test conversation auto-creation

**Depends On:** PR #1, PR #2

**Time Estimate:** 2-3 hours
**Files Changed:** ~6 files
**Risk Level:** LOW (read-only for most users)

**Merge Criteria:**
- ✅ Public endpoints work for authenticated users
- ✅ Inactive channels properly hidden
- ✅ Tests pass

---

### PR #4: Core Chat - WebSocket & RAG
**Phases:** 5-7 (WebSocket, RAG modifications, Ingestion)

**Scope:**
- [ ] WebSocket handler modifications:
  - Accept `channel_name` query param
  - Verify channel exists and active
  - Get/create user's channel conversation
  - Build channel_context object
  - Correct message history retrieval
- [ ] GraphState updates (add channel_context)
- [ ] Router node updates (admin permission checks)
- [ ] Retriever node updates (use channel collection)
- [ ] Grader node (no changes needed)
- [ ] Generator node (no changes needed - context passed via prompts)
- [ ] Metadata node updates (channel video summary)
- [ ] Video search node updates (search channel collection)
- [ ] Video load node updates (admin checks)
- [ ] Ingestion service updates:
  - `ingest_for_channel()` method
  - Duplicate transcript detection
  - Chunk creation with channel_id
  - Qdrant upsert to channel collection
- [ ] ConnectionManager updates (channel grouping)

**Tests:**
- [ ] Integration tests for WebSocket with channel_name
- [ ] Unit tests for all modified RAG nodes
- [ ] Test admin can load videos in channel
- [ ] Test users cannot load videos in channel
- [ ] Test RAG retrieves from correct collection
- [ ] Test duplicate video handling

**Depends On:** PR #1, PR #3

**Time Estimate:** 7-9 hours
**Files Changed:** ~15 files
**Risk Level:** HIGH (core functionality, affects all users)

**Merge Criteria:**
- ✅ WebSocket works in both modes (personal + channel)
- ✅ RAG nodes context-aware
- ✅ Correct collection used for retrieval
- ✅ Message persistence correct
- ✅ Admin checks enforced
- ✅ All tests pass

---

### PR #5: Admin UI - Management Panel
**Phase:** 8 (HTML admin panel)

**Scope:**
- [ ] Template system setup (Jinja2)
- [ ] HTML templates:
  - `admin/base.html` (layout with Bootstrap 5)
  - `admin/dashboard.html` (list channels)
  - `admin/create_channel.html` (create form)
  - `admin/channel_detail.html` (manage channel + videos)
- [ ] Admin UI routes:
  - GET /admin (dashboard)
  - GET /admin/channels/new (create form)
  - GET /admin/channels/{name} (detail page)
- [ ] JavaScript for AJAX (fetch API)
- [ ] Static files (CSS if custom styles needed)

**Tests:**
- [ ] Manual testing of admin UI
- [ ] Test forms validate correctly
- [ ] Test API calls work from UI
- [ ] Test responsive design

**Depends On:** PR #2

**Time Estimate:** 3-4 hours
**Files Changed:** ~10 files
**Risk Level:** LOW (admin-only, no backend logic)

**Merge Criteria:**
- ✅ Admin can access dashboard
- ✅ Admin can create channels
- ✅ Admin can add/remove videos
- ✅ Admin can soft delete/restore channels
- ✅ UI functional and responsive

---

### PR #6: Frontend - User Interface
**Phase:** 8.5 (NEW - Astro components)

**Scope:**
- [ ] Channel list page component:
  - `frontend/src/pages/channels.astro` (NEW)
  - List all active channels
  - Link to each channel chat
- [ ] Channel chat page:
  - `frontend/src/pages/channel/[name].astro` (NEW)
  - Display channel description at top
  - Chat interface (reuse existing components)
  - Video sidebar (NEW component)
- [ ] Video sidebar component:
  - `frontend/src/components/ChannelVideoList.astro` (NEW)
  - List all videos in channel
  - Pagination (similar to VideoList)
- [ ] Store updates:
  - `frontend/src/stores/channels.ts` (NEW)
  - State for channels list, active channel
- [ ] API client updates:
  - `frontend/src/lib/api.ts`
  - Add channel API methods (getChannels, getChannel, etc.)
- [ ] WebSocket updates:
  - `frontend/src/lib/websocket.ts`
  - Support channel_name parameter
- [ ] Navigation updates:
  - Add "Channels" link to main nav
  - Show breadcrumbs for channel chat

**Tests:**
- [ ] Manual testing with Chrome DevTools MCP
- [ ] Test channel list renders
- [ ] Test channel chat loads
- [ ] Test WebSocket connection with channel_name
- [ ] Test video sidebar pagination
- [ ] Test chat works same as personal chat

**Depends On:** PR #4

**Time Estimate:** 4-5 hours
**Files Changed:** ~12 files
**Risk Level:** MEDIUM (user-facing, but isolated)

**Merge Criteria:**
- ✅ Channel list page works
- ✅ Channel chat interface functional
- ✅ Video sidebar shows all videos
- ✅ WebSocket connects with channel context
- ✅ RAG responses correct
- ✅ UI/UX matches existing app

---

### PR #7: Testing & Documentation
**Phases:** 9-10 (Comprehensive testing + docs)

**Scope:**
- [ ] E2E test (full channel flow)
- [ ] Additional integration tests (if gaps found)
- [ ] Load testing (optional, if scaling concerns)
- [ ] Documentation updates:
  - `CURRENT_SYSTEM.md` (add channels section)
  - `DATABASE_SCHEMA.md` (document new tables)
  - `CHANNELS_FEATURE.md` (NEW - complete feature docs)
- [ ] API documentation updates (OpenAPI examples)
- [ ] Admin user guide
- [ ] Update README

**Tests:**
- [ ] E2E test passes (admin creates → user chats → admin deletes)
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Coverage ≥ 80%

**Depends On:** PR #6

**Time Estimate:** 4-5 hours
**Files Changed:** ~20 files (tests + docs)
**Risk Level:** LOW (no production code changes)

**Merge Criteria:**
- ✅ All tests pass
- ✅ Test coverage meets standards
- ✅ Documentation complete and accurate
- ✅ No regressions in existing features

---

## PR Dependency Graph

```
PR #1 (Foundation)
   ↓
   ├→ PR #2 (Admin API)
   │     ↓
   │     └→ PR #5 (Admin UI)
   │
   └→ PR #3 (Public API)
         ↓
         └→ PR #4 (WebSocket + RAG)
               ↓
               └→ PR #6 (Frontend)
                     ↓
                     └→ PR #7 (Testing + Docs)
```

**Parallel Work Opportunities:**
- PR #2 and PR #3 can be developed in parallel (both depend only on PR #1)
- PR #5 can be developed while PR #3-4 are in progress (depends only on PR #2)
- PR #7 can start documentation while PR #6 is in progress

---

## Phase 1: Database Schema & Models ⏱️ 3-4 hours (UPDATED)

### 1.1 Create Alembic Migration
- [ ] Create migration file: `add_channel_tables.py`
- [ ] Add `channels` table:
  - `id` (UUID, PK)
  - `name` (VARCHAR(100), UNIQUE, immutable slug)
  - `display_title` (VARCHAR(255))
  - `description` (TEXT, nullable)
  - `qdrant_collection_name` (VARCHAR(100))
  - `is_active` (BOOLEAN, default TRUE)
  - `created_by` (UUID, FK → users.id, nullable)
  - `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE)
  - Indexes: UNIQUE on `name`, INDEX on `is_active`, `qdrant_collection_name`
- [ ] Add `channel_videos` table:
  - `id` (UUID, PK)
  - `channel_id` (UUID, FK → channels.id, ON DELETE CASCADE)
  - `transcript_id` (UUID, FK → transcripts.id, ON DELETE CASCADE)
  - `added_by` (UUID, FK → users.id, nullable)
  - `added_at` (TIMESTAMP WITH TIME ZONE)
  - Constraint: UNIQUE on `(channel_id, transcript_id)`
- [ ] Add `channel_conversations` table:
  - `id` (UUID, PK)
  - `channel_id` (UUID, FK → channels.id, ON DELETE CASCADE)
  - `user_id` (UUID, FK → users.id, ON DELETE CASCADE)
  - `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE)
  - Constraint: UNIQUE on `(channel_id, user_id)`
  - Indexes: INDEX on `(channel_id, user_id)`, `updated_at DESC`
- [ ] **🔧 FIX GAP #1:** Modify `messages` table:
  - Add `channel_conversation_id` (UUID, FK → channel_conversations.id, nullable, ON DELETE CASCADE)
  - Add index on `channel_conversation_id`
  - Add constraint: `CHECK ((conversation_id IS NOT NULL AND channel_conversation_id IS NULL) OR (conversation_id IS NULL AND channel_conversation_id IS NOT NULL))`
  - Ensures message belongs to exactly one conversation type
- [ ] Modify `chunks` table:
  - Add `channel_id` (UUID, FK → channels.id, nullable, ON DELETE CASCADE)
  - Add index on `channel_id`
  - Add constraint: `CHECK ((user_id IS NOT NULL AND channel_id IS NULL) OR (user_id IS NULL AND channel_id IS NOT NULL))`
  - Ensures chunk belongs to either user OR channel (not both)
- [ ] Test migration up/down
- [ ] Run migration: `alembic upgrade head`

### 1.2 Create SQLAlchemy Models
- [ ] Add `Channel` model to `backend/app/db/models.py`
- [ ] Add `ChannelVideo` model to `backend/app/db/models.py`
- [ ] Add `ChannelConversation` model to `backend/app/db/models.py`
- [ ] **🔧 FIX GAP #1:** Update `Message` model with `channel_conversation_id` relationship
- [ ] Update `Chunk` model with `channel_id` relationship
- [ ] Add relationships: `Channel.videos`, `Channel.conversations`, `Channel.chunks`
- [ ] Test models with test database

### 1.3 Create Repositories
- [ ] Create `backend/app/db/repositories/channel_repo.py`
  - `create(name, display_title, description, created_by, qdrant_collection_name) -> Channel`
  - `get_by_id(channel_id) -> Optional[Channel]`
  - `get_by_name(name) -> Optional[Channel]`
  - `list_active(limit, offset) -> Tuple[List[Channel], int]`
  - `list_all(limit, offset) -> Tuple[List[Channel], int]`
  - `update(channel_id, display_title, description) -> Channel`
  - `soft_delete(channel_id) -> bool`
  - `reactivate(channel_id) -> bool`
- [ ] Create `backend/app/db/repositories/channel_video_repo.py`
  - `add_video(channel_id, transcript_id, added_by) -> ChannelVideo`
  - `remove_video(channel_id, transcript_id) -> bool`
  - `list_by_channel(channel_id, limit, offset) -> Tuple[List[ChannelVideo], int]`
  - `get_latest_n(channel_id, n) -> List[ChannelVideo]`
  - `count_by_channel(channel_id) -> int`
  - `video_exists(channel_id, transcript_id) -> bool`
- [ ] Create `backend/app/db/repositories/channel_conversation_repo.py`
  - `get_or_create(channel_id, user_id) -> ChannelConversation`
  - `get_by_id(conversation_id) -> Optional[ChannelConversation]`
  - `list_by_channel(channel_id, limit, offset) -> List[ChannelConversation]`
  - `list_by_user(user_id, limit, offset) -> List[ChannelConversation]`
- [ ] Write unit tests for all repository methods

**Completion Criteria:**
- ✅ All migrations applied successfully
- ✅ All models created with proper relationships
- ✅ Message model supports both conversation types
- ✅ All repositories implemented and tested
- ✅ Database schema matches design

---

## Phase 2: Qdrant Service Extensions ⏱️ 1-2 hours

### 2.1 Add Collection Management Methods
- [ ] **🔧 FIX GAP #4:** Add helper function to `backend/app/services/qdrant_service.py`:
  ```python
  def sanitize_collection_name(channel_name: str) -> str:
      """
      Convert channel name to valid Qdrant collection name.
      Example: "python-basics" → "channel_python_basics"
      """
      return f"channel_{channel_name.replace('-', '_')}"
  ```
- [ ] Add `create_channel_collection(collection_name: str) -> None`
  - Creates new collection with 1536-dim vectors
  - Same configuration as default collection
  - No user_id index (channel-wide search)
  - Use sanitized collection name
- [ ] Add `delete_channel_collection(collection_name: str) -> None`
  - Removes entire collection
  - Use for hard delete scenarios only
- [ ] Add `collection_exists(collection_name: str) -> bool`
  - Check if collection exists before operations
- [ ] Add `get_collection_info(collection_name: str) -> Dict`
  - Returns vector count, size, etc.

### 2.2 Update Existing Methods
- [ ] Modify `upsert_chunks()` to accept `collection_name: Optional[str]`
  - Default to "youtube_chunks" if None
  - Update docstring
- [ ] Modify `search()` to accept `collection_name: Optional[str]`
  - Default to "youtube_chunks" if None
  - Remove user_id filter requirement when using custom collection
  - Update docstring
- [ ] Modify `delete_chunks()` to accept `collection_name: Optional[str]`
- [ ] Add retry logic to all new methods (@retry decorator)
- [ ] Write unit tests for new methods (mock Qdrant client)

**Completion Criteria:**
- ✅ All collection management methods working
- ✅ Collection name sanitization working
- ✅ Existing methods support optional collection parameter
- ✅ Tests pass with 80%+ coverage
- ✅ Can create/delete collections programmatically

---

## Phase 3: REST API - Admin Endpoints ⏱️ 3-4 hours (UPDATED)

### 3.1 Create Admin Middleware & Error Handling
- [ ] Update `backend/app/core/auth.py`
- [ ] Add `require_admin()` dependency:
  ```python
  async def require_admin(current_user: User = Depends(get_current_user)):
      if current_user.role != "admin":
          raise HTTPException(status_code=403, detail="Admin access required")
      return current_user
  ```
- [ ] **🔧 FIX GAP #7:** Create `backend/app/core/exceptions.py` (NEW):
  ```python
  class ChannelNotFoundError(HTTPException):
      def __init__(self, channel_name: str):
          super().__init__(status_code=404, detail=f"Channel '{channel_name}' not found")

  class ChannelInactiveError(HTTPException):
      def __init__(self, channel_name: str):
          super().__init__(status_code=410, detail=f"Channel '{channel_name}' is inactive")

  class InsufficientChannelPermissionError(HTTPException):
      def __init__(self):
          super().__init__(status_code=403, detail="Admin access required for this operation")

  class DuplicateChannelError(HTTPException):
      def __init__(self, channel_name: str):
          super().__init__(status_code=409, detail=f"Channel '{channel_name}' already exists")
  ```
- [ ] Test admin check with admin and non-admin users

### 3.2 Create Pydantic Schemas
- [ ] Create `backend/app/schemas/channel.py`
- [ ] Add `ChannelCreate` schema:
  - Fields: `name` (slug validation: lowercase, hyphens, alphanumeric), `display_title`, `description`
  - Validators: name must match `^[a-z0-9-]+$`
- [ ] Add `ChannelUpdate` schema (display_title, description only)
- [ ] Add `ChannelResponse` schema (all fields + video_count)
- [ ] Add `ChannelListResponse` schema (list + total count)
- [ ] Add `ChannelDetailResponse` schema (channel + latest 5 videos)
- [ ] Add `ChannelVideoAdd` schema (youtube_url)
- [ ] Add `ChannelVideoResponse` schema (video info + added_at, added_by)

### 3.3 Create Admin Routes
- [ ] Create `backend/app/api/routes/admin.py`
- [ ] Add `GET /api/admin/channels` - List all channels
  - Query params: limit, offset, active_only (default: False)
  - Returns: ChannelListResponse
  - Admin only
- [ ] **🔧 FIX GAP #7 + #8:** Add `POST /api/admin/channels` - Create channel with transaction:
  ```python
  async def create_channel(...):
      # Validate name (slug format)
      if not re.match(r'^[a-z0-9-]+$', channel_data.name):
          raise HTTPException(400, "Invalid channel name")

      # Check for duplicates
      existing = await channel_repo.get_by_name(channel_data.name)
      if existing:
          raise DuplicateChannelError(channel_data.name)

      # Sanitize collection name
      collection_name = sanitize_collection_name(channel_data.name)

      try:
          # Create channel record
          channel = await channel_repo.create(
              name=channel_data.name,
              display_title=channel_data.display_title,
              description=channel_data.description,
              created_by=current_user.id,
              qdrant_collection_name=collection_name
          )

          # Create Qdrant collection
          await qdrant_service.create_channel_collection(collection_name)

          # Commit transaction
          await db.commit()
          return channel
      except Exception as e:
          # Rollback DB changes
          await db.rollback()

          # Clean up Qdrant if created
          if await qdrant_service.collection_exists(collection_name):
              await qdrant_service.delete_channel_collection(collection_name)

          raise HTTPException(500, f"Failed to create channel: {str(e)}")
  ```
- [ ] Add `GET /api/admin/channels/{channel_name}` - Get channel details
  - Returns: ChannelDetailResponse (channel + all videos)
  - Admin only
- [ ] Add `PUT /api/admin/channels/{channel_name}` - Update channel
  - Body: ChannelUpdate (display_title, description)
  - Cannot change name (immutable)
  - Returns: ChannelResponse
  - Admin only
- [ ] Add `DELETE /api/admin/channels/{channel_name}` - Soft delete
  - Sets is_active=False
  - Does NOT delete Qdrant collection (preserve data)
  - Returns: success message
  - Admin only
- [ ] Add `POST /api/admin/channels/{channel_name}/restore` - Reactivate channel
  - Sets is_active=True
  - Returns: ChannelResponse
  - Admin only
- [ ] **🔧 FIX GAP #6:** Add `POST /api/admin/channels/{channel_name}/videos` - Add video:
  - Body: ChannelVideoAdd (youtube_url)
  - Call `transcription_service.ingest_for_channel()`
  - Returns: ChannelVideoResponse
  - Handle: duplicate video, invalid URL, ingestion errors
  - Admin only
- [ ] **🔧 FIX GAP #6:** Add `DELETE /api/admin/channels/{channel_name}/videos/{transcript_id}` - Remove video:
  ```python
  async def remove_video(...):
      # Get chunks for transcript in this channel
      chunks = await chunk_repo.list_by_transcript(transcript_id)
      chunk_ids = [str(chunk.id) for chunk in chunks if chunk.channel_id == channel_id]

      # Delete from Qdrant (explicit call)
      if chunk_ids:
          await qdrant_service.delete_chunks(
              chunk_ids,
              collection_name=channel.qdrant_collection_name
          )

      # Delete ChannelVideo association (CASCADE deletes chunks from DB)
      success = await channel_video_repo.remove_video(channel_id, transcript_id)

      return {"success": success}
  ```
- [ ] Add `GET /api/admin/channels/{channel_name}/videos` - List all videos
  - Query params: limit, offset
  - Returns: paginated video list
  - Admin only
- [ ] Register router in `backend/app/main.py`
- [ ] Write integration tests for all endpoints

**Completion Criteria:**
- ✅ All admin endpoints working
- ✅ Transaction handling prevents orphaned records
- ✅ Proper error handling and validation
- ✅ Custom exceptions used consistently
- ✅ Admin-only access enforced
- ✅ Qdrant cleanup on video removal
- ✅ Integration tests pass

---

## Phase 4: REST API - Public Channel Endpoints ⏱️ 1-2 hours

### 4.1 Create Public Channel Routes
- [ ] Create `backend/app/api/routes/channels.py`
- [ ] Add `GET /api/channels` - List active channels
  - Query params: limit, offset
  - Returns: ChannelListResponse (only active channels)
  - Auth required, no admin needed
- [ ] Add `GET /api/channels/{channel_name}` - Get channel info + summary
  - Returns: channel info, video count, 5 latest videos
  - Error if channel inactive (use ChannelInactiveError)
  - Auth required
- [ ] Add `GET /api/channels/{channel_name}/videos` - List all videos for sidebar
  - Query params: limit, offset
  - Returns: paginated video list with full metadata
  - Auth required
- [ ] Add `GET /api/channels/{channel_name}/conversation` - Get/create user's conversation
  - Returns: ChannelConversation ID
  - Auto-creates if doesn't exist
  - Auth required
- [ ] Register router in `backend/app/main.py`
- [ ] Write integration tests

**Completion Criteria:**
- ✅ Public endpoints working for authenticated users
- ✅ Inactive channels return 410 Gone
- ✅ Tests pass

---

## Phase 5: WebSocket Channel Chat ⏱️ 3-4 hours (UPDATED)

### 5.1 Modify WebSocket Handler
- [ ] Update `backend/app/api/websocket/chat_handler.py`
- [ ] Update `websocket_endpoint()` signature:
  - Add optional `channel_name` query param
  - Route: `WS /api/ws/chat?token=<>&channel_name=<optional>`
- [ ] Add channel mode detection:
  ```python
  channel_name = websocket.query_params.get("channel_name")

  if channel_name:
      # Channel mode
      channel = await channel_repo.get_by_name(channel_name)
      if not channel:
          raise ChannelNotFoundError(channel_name)
      if not channel.is_active:
          raise ChannelInactiveError(channel_name)

      # Get or create user's channel conversation
      channel_conversation = await channel_conversation_repo.get_or_create(
          channel_id=channel.id,
          user_id=current_user.id
      )
      conversation_id = channel_conversation.id
      is_channel_mode = True

      # Build channel context
      channel_context = {
          "type": "channel",
          "channel_id": str(channel.id),
          "channel_name": channel.name,
          "qdrant_collection": channel.qdrant_collection_name,
          "user_is_admin": current_user.role == "admin"
      }
  else:
      # Personal chat mode (existing behavior)
      # ... existing conversation logic
      is_channel_mode = False
      channel_context = None
  ```
- [ ] **🔧 FIX GAP #5:** Update message history retrieval:
  ```python
  # Get conversation history (last N messages)
  if is_channel_mode:
      history = await message_repo.get_last_n_channel(
          channel_conversation_id=conversation_id,
          n=config.get("max_context_messages", 10)
      )
  else:
      history = await message_repo.get_last_n(
          conversation_id=conversation_id,
          n=config.get("max_context_messages", 10)
      )
  ```
- [ ] Update `message_repo.py` to add `get_last_n_channel()` method (queries by channel_conversation_id)
- [ ] Pass `channel_context` to `run_graph()`:
  ```python
  result = await run_graph(
      user_query=message.content,
      user_id=str(current_user.id),
      conversation_history=history,
      config=rag_config,
      channel_context=channel_context  # NEW
  )
  ```
- [ ] Update message persistence to use correct conversation type:
  ```python
  if is_channel_mode:
      user_msg = await message_repo.create(
          channel_conversation_id=conversation_id,
          role="user",
          content=message.content
      )
      assistant_msg = await message_repo.create(
          channel_conversation_id=conversation_id,
          role="assistant",
          content=result["response"],
          meta_data=result["metadata"]
      )
  else:
      # Existing personal chat message creation
      ...
  ```
- [ ] **🔧 FIX GAP #9:** Update ConnectionManager to support channel grouping:
  ```python
  # Register connection with optional channel_name
  await connection_manager.connect(websocket, user_id, channel_name=channel_name)

  # Broadcast to channel or user
  if channel_name:
      await connection_manager.broadcast_to_channel(message, channel_name)
  else:
      await connection_manager.send_personal_message(message, user_id)
  ```
- [ ] Test WebSocket with and without channel_name parameter

### 5.2 Update GraphState
- [ ] Update `backend/app/rag/utils/state.py`
- [ ] Add to GraphState TypedDict:
  ```python
  channel_context: Optional[Dict[str, Any]]
  # Contains: type, channel_id, channel_name, qdrant_collection, user_is_admin
  ```
- [ ] Update docstring with channel_context description

**Completion Criteria:**
- ✅ WebSocket works in both modes (personal + channel)
- ✅ Correct conversation persistence
- ✅ Message history retrieved correctly per mode
- ✅ channel_context properly passed to RAG
- ✅ ConnectionManager handles channel grouping

---

## Phase 6: RAG Flow Modifications ⏱️ 2-3 hours

### 6.1 Update Router Entry Point
- [ ] Update `backend/app/rag/graphs/router.py`
- [ ] Add `channel_context` parameter to `run_graph()`:
  ```python
  async def run_graph(
      user_query: str,
      user_id: str,
      conversation_history: list,
      config: Dict[str, Any] = None,
      channel_context: Optional[Dict[str, Any]] = None  # NEW
  ) -> Dict[str, Any]:
  ```
- [ ] Pass `channel_context` to GraphState initialization
- [ ] Update docstring

### 6.2 Update Router Node (Intent Classification)
- [ ] Update `backend/app/rag/nodes/router_node.py`
- [ ] Modify `classify_intent()` to check channel_context after classification:
  ```python
  # After LLM classifies intent
  intent = classification.intent

  # Check admin permissions for video_load in channels
  if intent == "video_load" and state.get("channel_context"):
      if not state["channel_context"]["user_is_admin"]:
          # Return error instead of proceeding
          return {
              "intent": "error",
              "response": "Only administrators can load videos to channels.",
              "metadata": {"error_type": "permission_denied"}
          }

  return {"intent": intent, "metadata": {"intent_confidence": classification.confidence}}
  ```
- [ ] Test with admin and non-admin users

### 6.3 Update Retriever Node
- [ ] Update `backend/app/rag/nodes/retriever.py`
- [ ] Modify `retrieve_chunks()`:
  ```python
  async def retrieve_chunks(state: GraphState) -> GraphState:
      channel_context = state.get("channel_context")
      top_k = state.get("config", {}).get("rag_top_k", 12)

      # Generate query embedding
      query_embedding = await embedding_service.generate_embeddings([state["user_query"]])

      if channel_context:
          # Channel mode - use channel collection, no user filter
          collection_name = channel_context["qdrant_collection"]
          chunks = await qdrant_service.search(
              query_vector=query_embedding[0],
              collection_name=collection_name,
              top_k=top_k
          )
      else:
          # Personal mode - use default collection with user filter
          chunks = await qdrant_service.search(
              query_vector=query_embedding[0],
              user_id=state["user_id"],
              top_k=top_k
          )

      state["retrieved_chunks"] = chunks
      return state
  ```
- [ ] Test retrieval in both modes
- [ ] Ensure chunks from correct collection

### 6.4 Update Metadata Node
- [ ] Update `backend/app/rag/nodes/metadata_node.py`
- [ ] Modify `get_user_videos()`:
  ```python
  async def get_user_videos(state: GraphState) -> Dict[str, Any]:
      channel_context = state.get("channel_context")

      if channel_context:
          # Channel mode - show channel videos summary
          channel_id = UUID(channel_context["channel_id"])
          video_count = await channel_video_repo.count_by_channel(channel_id)
          latest_videos = await channel_video_repo.get_latest_n(channel_id, 5)

          response = f"<h3>Channel Video Library</h3>"
          response += f"<p>Total videos: {video_count}</p>"
          response += f"<h4>Latest 5 videos:</h4><ul>"
          for cv in latest_videos:
              transcript = cv.transcript
              response += f"<li><b>{transcript.title}</b> by {transcript.channel_name}</li>"
          response += "</ul>"
          response += "<p><i>Full video list available in the sidebar.</i></p>"
      else:
          # Personal mode - existing behavior
          # ... keep current implementation

      state["response"] = response
      return state
  ```
- [ ] Test metadata display in both modes

### 6.5 Update Video Search Node
- [ ] Update `backend/app/rag/nodes/video_search_node.py`
- [ ] Modify `search_videos_by_subject()`:
  ```python
  async def search_videos_by_subject(state: GraphState) -> Dict[str, Any]:
      channel_context = state.get("channel_context")
      subject = state["subject"]

      # Generate subject embedding
      subject_embedding = await embedding_service.generate_embeddings([subject])

      if channel_context:
          # Search within channel's collection
          collection_name = channel_context["qdrant_collection"]
          results = await qdrant_service.search(
              query_vector=subject_embedding[0],
              collection_name=collection_name,
              top_k=100
          )
      else:
          # Personal mode - existing behavior
          results = await qdrant_service.search(
              query_vector=subject_embedding[0],
              user_id=state["user_id"],
              top_k=100
          )

      # Rest of logic remains same (group by video, sort, format)
      ...
  ```
- [ ] Test subject search in both modes

### 6.6 Update Video Load Flow
- [ ] Update `backend/app/rag/graphs/flows/video_load_flow.py`
- [ ] Modify `handle_video_load_node()`:
  ```python
  async def handle_video_load_node(state: GraphState) -> GraphState:
      channel_context = state.get("channel_context")
      video_id = extract_video_id(state["user_query"])

      if channel_context:
          if channel_context["user_is_admin"]:
              # Admin in channel - allow load
              response = f"VIDEO_LOAD_REQUEST:{video_id}:CHANNEL:{channel_context['channel_id']}"
          else:
              # Non-admin in channel - deny (this should be caught by router, but double-check)
              response = "Only administrators can load videos to channels."
      else:
          # Personal mode - existing behavior
          response = f"VIDEO_LOAD_REQUEST:{video_id}"

      state["response"] = response
      return state
  ```
- [ ] Update WebSocket handler to parse CHANNEL mode in response and call appropriate ingestion
- [ ] Test video load in all scenarios

**Completion Criteria:**
- ✅ All RAG nodes context-aware
- ✅ Retrieval works from correct Qdrant collection
- ✅ Admin checks enforced for video loading
- ✅ Metadata shows appropriate info per mode
- ✅ No changes to grader/generator (context passed via prompts)

---

## Phase 7: Video Ingestion Service ⏱️ 1-2 hours (UPDATED)

### 7.1 Update Transcription Service
- [ ] Update `backend/app/services/transcription_service.py`
- [ ] **🔧 FIX GAP #3:** Add `ingest_for_channel()` method with duplicate detection:
  ```python
  async def ingest_for_channel(
      channel_id: UUID,
      youtube_url: str,
      added_by_user_id: UUID,
      db: AsyncSession
  ) -> ChannelVideo:
      # 1. Extract video_id from URL
      video_id = extract_video_id(youtube_url)

      # 2. Check if transcript already exists (any user or channel)
      existing_transcript = await transcript_repo.get_by_youtube_video_id(video_id)

      if existing_transcript:
          # Transcript exists - check if already in this channel
          channel_video_exists = await channel_video_repo.video_exists(
              channel_id, existing_transcript.id
          )
          if channel_video_exists:
              raise DuplicateVideoError(f"Video already in channel")

          # Reuse transcript, create new chunks for channel
          transcript = existing_transcript
      else:
          # New transcript - fetch from SUPADATA
          transcript_data = await fetch_transcript(youtube_url)

          # 3. Create Transcript record (no user_id for channel transcripts)
          transcript = await transcript_repo.create(
              user_id=None,  # No user ownership
              youtube_video_id=video_id,
              title=transcript_data["title"],
              channel_name=transcript_data["channel_name"],
              duration=transcript_data["duration"],
              transcript_text=transcript_data["transcript_text"],
              meta_data=transcript_data.get("metadata", {})
          )

      # 4. Get channel info
      channel = await channel_repo.get_by_id(channel_id)

      # 5. Chunk transcript
      chunks_data = await chunking_service.chunk_transcript(
          transcript.transcript_text,
          chunk_size=700,
          overlap_percent=20
      )

      # 6. Create Chunk records with channel_id (no user_id)
      chunks = []
      for idx, chunk_data in enumerate(chunks_data):
          chunk = await chunk_repo.create(
              transcript_id=transcript.id,
              channel_id=channel_id,  # Channel ownership
              user_id=None,  # No user ownership
              chunk_text=chunk_data["chunk_text"],
              chunk_index=idx,
              token_count=chunk_data["token_count"],
              meta_data={"youtube_video_id": video_id}
          )
          chunks.append(chunk)

      # 7. Generate embeddings
      chunk_texts = [c.chunk_text for c in chunks]
      embeddings = await embedding_service.generate_embeddings(chunk_texts)

      # 8. Upsert to channel's Qdrant collection
      chunk_ids = [str(c.id) for c in chunks]
      await qdrant_service.upsert_chunks(
          chunk_ids=chunk_ids,
          vectors=embeddings,
          collection_name=channel.qdrant_collection_name,  # Use channel collection
          metadata={
              "channel_id": str(channel_id),
              "youtube_video_id": video_id,
              "chunk_indices": list(range(len(chunks))),
              "chunk_texts": chunk_texts
          }
      )

      # 9. Create ChannelVideo association
      channel_video = await channel_video_repo.add_video(
          channel_id=channel_id,
          transcript_id=transcript.id,
          added_by=added_by_user_id
      )

      return channel_video
  ```
- [ ] Add error handling: duplicate video, SUPADATA errors, Qdrant errors
- [ ] Write unit tests (mock external services)

**Completion Criteria:**
- ✅ Can ingest videos to channels
- ✅ Duplicate transcripts detected and reused
- ✅ Chunks created with channel_id
- ✅ Vectors stored in correct Qdrant collection
- ✅ ChannelVideo association created
- ✅ Error handling comprehensive

---

## Phase 8: Admin Panel UI ⏱️ 2-3 hours

### 8.1 Setup Template System
- [ ] Create directory: `backend/app/templates/`
- [ ] Create subdirectory: `backend/app/templates/admin/`
- [ ] Update `backend/app/main.py`:
  ```python
  from fastapi.templating import Jinja2Templates
  templates = Jinja2Templates(directory="app/templates")
  ```
- [ ] Add static files serving (if needed for CSS/JS):
  ```python
  from fastapi.staticfiles import StaticFiles
  app.mount("/static", StaticFiles(directory="app/static"), name="static")
  ```

### 8.2 Create HTML Templates
- [ ] Create `backend/app/templates/admin/base.html`:
  - Base layout with Bootstrap 5 CDN
  - Navigation bar (Dashboard, Create Channel, Logout)
  - Footer with app info
  - Block for page content
- [ ] Create `backend/app/templates/admin/dashboard.html`:
  - Extends base.html
  - Table of channels (Name, Title, Videos, Status, Actions)
  - Columns: name (slug), display_title, video_count, is_active, actions
  - Actions: View, Edit, Delete/Restore buttons
  - "Create New Channel" button
  - Uses AJAX fetch to call `/api/admin/channels`
  - JavaScript for table population
- [ ] Create `backend/app/templates/admin/create_channel.html`:
  - Extends base.html
  - Form fields:
    - Name (slug): input with pattern validation `^[a-z0-9-]+$`
    - Display Title: text input
    - Description: textarea
  - Submit button
  - Client-side validation
  - AJAX POST to `/api/admin/channels`
  - Redirect to channel detail on success
- [ ] Create `backend/app/templates/admin/channel_detail.html`:
  - Extends base.html
  - Channel info section (editable via inline forms or modal)
  - Video list section:
    - Table of videos (Title, Author, Duration, Added At, Actions)
    - Delete video button (with confirmation)
  - "Add Video" form:
    - YouTube URL input
    - Submit button
    - AJAX POST to `/api/admin/channels/{name}/videos`
  - JavaScript for AJAX operations

### 8.3 Create Admin UI Routes
- [ ] Create `backend/app/api/routes/admin_ui.py`
- [ ] Add `GET /admin` - Render dashboard template
  - No need to fetch channels (done client-side via AJAX)
  - Just render template
- [ ] Add `GET /admin/channels/new` - Render create form
- [ ] Add `GET /admin/channels/{channel_name}` - Render channel detail
  - Pass channel_name to template
  - Template fetches data via AJAX
- [ ] Register router in `backend/app/main.py`
- [ ] Add admin UI link to main app nav (if exists)

### 8.4 Add JavaScript for AJAX
- [ ] Create `backend/app/static/js/admin.js` (or inline in templates):
  - Form submission handlers (preventDefault, fetch, error handling)
  - API call functions (createChannel, deleteChannel, addVideo, etc.)
  - Success/error toast notifications (using Bootstrap toasts or alerts)
  - Table update functions (refresh after actions)
- [ ] Use native fetch API (no jQuery dependency)
- [ ] Handle loading states (disable buttons during API calls)

**Completion Criteria:**
- ✅ Admin can access dashboard at /admin
- ✅ Admin can view list of all channels
- ✅ Admin can create channels via form
- ✅ Admin can view channel details
- ✅ Admin can edit channel (title, description)
- ✅ Admin can add/remove videos from channels
- ✅ Admin can soft delete/restore channels
- ✅ UI is responsive (Bootstrap grid)
- ✅ Error messages displayed appropriately

---

## Phase 8.5: Frontend - User Interface ⏱️ 4-5 hours (NEW)

### 8.5.1 Create Channel List Page
- [ ] Create `frontend/src/pages/channels.astro` (NEW)
  - Layout with header "Available Channels"
  - Fetch channels via API on page load
  - Display as cards or list:
    - Channel name
    - Display title
    - Description (truncated)
    - Video count
    - Link to channel chat
  - Empty state if no channels
  - Loading state
- [ ] Add to navigation menu (link to /channels)

### 8.5.2 Create Channel Chat Page
- [ ] Create `frontend/src/pages/channel/[name].astro` (NEW - dynamic route)
  - Use Astro dynamic routing: `[name].astro`
  - Get channel_name from URL params: `Astro.params.name`
  - Fetch channel details via API
  - Display channel description at top (sticky/fixed)
  - Reuse existing chat components (ChatInput, ChatMessage)
  - Video sidebar (NEW component, see below)
  - Layout similar to personal chat but with channel context

### 8.5.3 Create Video Sidebar Component
- [ ] Create `frontend/src/components/ChannelVideoList.astro` (NEW)
  - Similar to VideoList component (from VIDEO_LIST_SIDEBAR_PLAN.md)
  - Display all videos in channel (paginated)
  - No delete button (users can't delete from channels)
  - Show: title, author, duration
  - Pagination: Prev/Next buttons
  - Empty state: "No videos in this channel yet"
- [ ] Integrate into channel chat page sidebar

### 8.5.4 Create Channel Store
- [ ] Create `frontend/src/stores/channels.ts` (NEW)
  ```typescript
  import { atom } from 'nanostores';

  export interface Channel {
    id: string;
    name: string;
    display_title: string;
    description: string;
    video_count: number;
    is_active: boolean;
  }

  export interface ChannelState {
    channels: Channel[];
    activeChannel: Channel | null;
    loading: boolean;
    error: string | null;
  }

  export const $channelState = atom<ChannelState>({
    channels: [],
    activeChannel: null,
    loading: false,
    error: null
  });

  // Actions
  export function setChannels(channels: Channel[]) { ... }
  export function setActiveChannel(channel: Channel) { ... }
  export function setLoading(loading: boolean) { ... }
  export function setError(error: string) { ... }
  ```

### 8.5.5 Update API Client
- [ ] Update `frontend/src/lib/api.ts`
  - Add `getChannels(token, limit, offset)` - GET /api/channels
  - Add `getChannel(token, channelName)` - GET /api/channels/{name}
  - Add `getChannelVideos(token, channelName, limit, offset)` - GET /api/channels/{name}/videos
  - Add `getChannelConversation(token, channelName)` - GET /api/channels/{name}/conversation

### 8.5.6 Update WebSocket Client
- [ ] Update `frontend/src/lib/websocket.ts`
  - Add optional `channelName` parameter to `connectWebSocket()`
  - Build WebSocket URL with channel_name query param:
    ```typescript
    function connectWebSocket(token: string, channelName?: string): WebSocket {
      const baseUrl = WS_URL;
      const params = new URLSearchParams({ token });
      if (channelName) {
        params.append('channel_name', channelName);
      }
      const url = `${baseUrl}?${params}`;
      return new WebSocket(url);
    }
    ```

### 8.5.7 Update Navigation
- [ ] Update main navigation component
  - Add "Channels" link (to /channels)
  - Add breadcrumb navigation for channel chat pages:
    - Home > Channels > {channel_display_title}

### 8.5.8 Test Frontend with Chrome DevTools MCP
- [ ] Navigate to /channels page
- [ ] Take snapshot, verify channels list
- [ ] Click channel link
- [ ] Navigate to channel chat page
- [ ] Take snapshot, verify:
  - Channel description visible at top
  - Chat interface loaded
  - Video sidebar shows videos
- [ ] Test chat functionality:
  - Send message
  - Verify WebSocket connection (check network tab)
  - Verify RAG response
- [ ] Test video sidebar pagination
- [ ] Test responsive design (resize viewport)

**Completion Criteria:**
- ✅ Channel list page displays all active channels
- ✅ Channel chat page loads with correct channel context
- ✅ Channel description displayed at top
- ✅ Video sidebar shows all channel videos
- ✅ WebSocket connects with channel_name parameter
- ✅ Chat works same as personal chat (RAG responses correct)
- ✅ Navigation intuitive (breadcrumbs, links)
- ✅ Responsive design works on mobile/tablet/desktop
- ✅ No console errors
- ✅ Manual testing confirms all functionality

---

## Phase 9: Testing ⏱️ 3-4 hours

### 9.1 Unit Tests - Repositories
- [ ] Create `tests/unit/repositories/test_channel_repo.py`
  - Test all ChannelRepository methods
  - Mock database session
- [ ] Create `tests/unit/repositories/test_channel_video_repo.py`
  - Test all ChannelVideoRepository methods
  - Test duplicate video detection
- [ ] Create `tests/unit/repositories/test_channel_conversation_repo.py`
  - Test get_or_create, list methods
- [ ] Update `tests/unit/repositories/test_message_repo.py`
  - Test new get_last_n_channel method
- [ ] Ensure 80%+ coverage

### 9.2 Unit Tests - Services
- [ ] Create `tests/unit/services/test_qdrant_service_channels.py`
  - Test create_channel_collection
  - Test collection_exists
  - Test sanitize_collection_name
  - Test search with collection_name parameter
  - Mock Qdrant client
- [ ] Update `tests/unit/services/test_transcription_service.py`
  - Test ingest_for_channel method
  - Test duplicate transcript handling
  - Mock SUPADATA API

### 9.3 Unit Tests - RAG Nodes
- [ ] Update `tests/unit/nodes/test_retriever.py`
  - Add test_retrieve_chunks_channel_mode
  - Add test_retrieve_chunks_personal_mode
  - Verify correct collection used
- [ ] Update `tests/unit/nodes/test_metadata_node.py`
  - Add test_metadata_channel_mode
  - Add test_metadata_personal_mode
  - Verify correct response format
- [ ] Update `tests/unit/nodes/test_video_search_node.py`
  - Add channel mode tests
  - Verify searches correct collection
- [ ] Update `tests/unit/nodes/test_router_node.py`
  - Add test_video_load_admin_channel (should pass)
  - Add test_video_load_user_channel (should return error)
  - Test permission checks

### 9.4 Integration Tests - Admin API
- [ ] Create `tests/integration/test_admin_channels_api.py`
  - Test POST /api/admin/channels (create)
    - Success case
    - Duplicate name error
    - Invalid slug format error
    - Rollback on Qdrant failure
  - Test GET /api/admin/channels (list)
  - Test GET /api/admin/channels/{name} (detail)
  - Test PUT /api/admin/channels/{name} (update)
  - Test DELETE /api/admin/channels/{name} (soft delete)
  - Test POST /api/admin/channels/{name}/restore (reactivate)
  - Test POST /api/admin/channels/{name}/videos (add video)
    - Success case
    - Duplicate video error
    - Reuse existing transcript
  - Test DELETE /api/admin/channels/{name}/videos/{id} (remove video)
    - Verify Qdrant cleanup
  - Test GET /api/admin/channels/{name}/videos (list)
  - Test permission denied for non-admin users (all endpoints)
  - Use test database + test Qdrant

### 9.5 Integration Tests - Public API
- [ ] Create `tests/integration/test_public_channels_api.py`
  - Test GET /api/channels (list active only)
    - Verify inactive channels not returned
  - Test GET /api/channels/{name} (detail)
    - Success for active channel
    - 410 error for inactive channel
  - Test GET /api/channels/{name}/videos (list)
  - Test GET /api/channels/{name}/conversation (get/create)
    - Verify auto-creation
    - Verify same conversation returned on subsequent calls

### 9.6 Integration Tests - WebSocket
- [ ] Create `tests/integration/test_channel_websocket.py`
  - Test connect with channel_name parameter
    - Success for active channel
    - Error for inactive channel
    - Error for non-existent channel
  - Test user query in channel mode (RAG retrieval)
    - Verify uses channel collection
    - Verify response includes RAG context
  - Test metadata intent in channel mode
    - Verify returns channel video summary
  - Test video_load intent as admin in channel
    - Should succeed
  - Test video_load intent as user in channel
    - Should return permission error
  - Test message persistence to ChannelConversation
    - Verify messages saved with channel_conversation_id
  - Test conversation history retrieval
    - Verify last 10 messages from channel conversation

### 9.7 E2E Test
- [ ] Create `tests/e2e/test_channel_flow.py`
  - Test complete user journey:
    1. Admin logs in
    2. Admin creates channel "python-basics"
       - Verify channel created in DB
       - Verify Qdrant collection created
    3. Admin adds 3 videos to channel
       - Verify videos ingested
       - Verify chunks created
       - Verify vectors in Qdrant
    4. Regular user logs in
    5. User views channel list
       - Verify "python-basics" visible
    6. User opens channel chat
       - Verify channel description shown
       - Verify video sidebar shows 3 videos
    7. User asks "what videos are here?"
       - Verify receives summary (count + 5 latest)
    8. User asks "what is FastAPI?"
       - Verify RAG retrieves from channel
       - Verify response based on channel content
    9. User tries to load video
       - Verify permission denied
    10. Admin soft deletes channel
        - Verify is_active=False
    11. User tries to connect to channel
        - Verify 410 Gone error
    12. Admin restores channel
        - Verify is_active=True
    13. User reconnects successfully
        - Verify chat works again

**Completion Criteria:**
- ✅ All tests pass
- ✅ Overall test coverage ≥ 80%
- ✅ No regressions in existing functionality
- ✅ E2E test covers full flow

---

## Phase 10: Documentation ⏱️ 1-2 hours

### 10.1 Update Existing Documentation
- [ ] Update `PROJECT_FLOW_DOCS/CURRENT_SYSTEM.md`
  - Add "Channels Feature" section after "Chat Endpoints"
  - Document channel architecture
  - Update entity relationship diagram (add 3 new tables)
  - Add channel WebSocket flow example
  - Update intent types (show context-aware behavior)
- [ ] Update `PROJECT_FLOW_DOCS/DATABASE_SCHEMA.md`
  - Document new tables: channels, channel_videos, channel_conversations
  - Update chunks table (add channel_id)
  - Update messages table (add channel_conversation_id)
  - Add relationship diagrams showing channel connections
- [ ] Update `backend/README.md` (if exists)
  - Add channels to features list
  - Update API endpoints section

### 10.2 Create Feature Documentation
- [ ] Create `PROJECT_FLOW_DOCS/CHANNELS_FEATURE.md` (NEW)
  - **Feature Overview**
    - What are channels?
    - Use cases
    - Architecture diagram
  - **User Guide**
    - How to find channels
    - How to chat with channels
    - How videos are organized
  - **Admin Guide**
    - How to create a channel
    - How to add videos
    - How to manage channels
    - Best practices (naming, descriptions)
  - **API Reference**
    - All admin endpoints with examples
    - All public endpoints with examples
    - WebSocket protocol (channel mode)
  - **Architecture Details**
    - Database schema
    - Qdrant collections
    - RAG flow modifications
    - Message persistence
  - **Future Enhancements**
    - Permission-based access
    - Channel categories
    - Channel search
    - Analytics

### 10.3 Update API Documentation
- [ ] Add comprehensive docstrings to all new endpoints
  - Use FastAPI docstring format
  - Include parameter descriptions
  - Include response examples
- [ ] Add OpenAPI examples for request/response bodies
  - ChannelCreate example
  - ChannelVideoAdd example
  - Error response examples
- [ ] Add tags to organize endpoints
  - "Admin - Channels" tag
  - "Channels" tag for public endpoints
- [ ] Test FastAPI auto-generated docs at /docs
  - Verify all endpoints visible
  - Verify examples render correctly

### 10.4 Create Admin User Guide
- [ ] Create `PROJECT_FLOW_DOCS/ADMIN_GUIDE_CHANNELS.md` (NEW)
  - **Creating a Channel**
    - Naming conventions
    - Choosing good display titles
    - Writing helpful descriptions
  - **Adding Videos**
    - How to find good YouTube videos
    - Handling ingestion errors
    - What happens to duplicate videos
  - **Managing Channels**
    - Editing channel info
    - Removing videos
    - Soft delete vs hard delete
    - Restoring channels
  - **Best Practices**
    - Curate content by theme
    - Keep descriptions up-to-date
    - Monitor video count
  - **Troubleshooting**
    - "Qdrant collection creation failed" → what to do
    - "Video already exists" → how to handle
    - Channel not showing to users → check is_active

**Completion Criteria:**
- ✅ All existing docs updated
- ✅ Feature fully documented
- ✅ API docs complete and accurate
- ✅ Admin guide clear and helpful
- ✅ No outdated information

---

## Implementation Order Summary

### Week 1: Foundation (Days 1-3)
**Target:** PR #1, PR #2 ready for review
- [ ] Day 1: Phase 1 (Database + Models) ✅
- [ ] Day 2: Phase 2 (Qdrant) + Phase 3 (Admin API) ✅
- [ ] Day 3: Finish Phase 3, testing ✅

### Week 2: Core & UI (Days 4-6)
**Target:** PR #3, PR #4, PR #5 ready for review
- [ ] Day 4: Phase 4 (Public API) + Start Phase 5 (WebSocket) ✅
- [ ] Day 5: Finish Phase 5 + Phase 6 (RAG) ✅
- [ ] Day 6: Phase 7 (Ingestion) + Phase 8 (Admin UI) ✅

### Week 3: Frontend & Polish (Days 7-10)
**Target:** PR #6, PR #7 merged, feature complete
- [ ] Day 7: Phase 8.5 (Frontend) - Channel list + chat pages ✅
- [ ] Day 8: Phase 8.5 (Frontend) - Video sidebar + testing ✅
- [ ] Day 9: Phase 9 (Testing) - All tests written and passing ✅
- [ ] Day 10: Phase 10 (Documentation) + Final review ✅

---

## Pre-Implementation Checklist

Before starting implementation:
- [ ] Review CURRENT_SYSTEM.md to understand existing architecture
- [ ] Backup database before running migrations
- [ ] Create feature branch: `git checkout -b feature/channels`
- [ ] Set up test environment (test DB, test Qdrant)
- [ ] Ensure all dependencies installed
- [ ] Review this plan with team/stakeholders
- [ ] Confirm all gaps addressed in plan

---

## Post-Implementation Checklist

After completing all phases:
- [ ] All tests passing (unit + integration + e2e)
- [ ] Code coverage ≥ 80%
- [ ] Admin panel functional and tested manually
- [ ] Frontend fully functional (tested with DevTools MCP)
- [ ] WebSocket works in both modes
- [ ] RAG retrieves from correct collections
- [ ] Documentation complete and accurate
- [ ] No regressions in existing features
- [ ] Create PRs following strategy (6 PRs)
- [ ] Code reviews completed for all PRs
- [ ] All PRs merged to main
- [ ] Deploy to staging/production
- [ ] Monitor for issues

---

## Key Design Principles

✅ **Simple:** Reuse existing patterns (repositories, intents, WebSocket)
✅ **Extensible:** Can add permissions layer later if needed
✅ **Isolated:** Separate Qdrant collections prevent cross-channel contamination
✅ **Consistent:** Same intent system, just context-aware
✅ **Safe:** Soft delete preserves data, admin-only video management
✅ **Testable:** All components have clear interfaces for testing
✅ **Robust:** Transaction handling, rollback logic, error handling
✅ **User-Friendly:** Clear error messages, intuitive UI

---

## Dependencies & Tools

### Required (Already Available)
- FastAPI
- SQLAlchemy 2.0
- Qdrant Python client
- LangGraph/LangChain
- OpenRouter API
- Astro (frontend)
- Nanostores (state management)
- Bootstrap 5 CDN (for admin UI)

### No New Libraries Needed
All functionality can be implemented with existing dependencies.

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| Qdrant collection proliferation | Medium | High | Monitor collection count, document limits |
| Channel name conflicts | Low | Low | Unique constraint + validation |
| Admin permission bypass | High | Low | Require admin role on all admin endpoints |
| Qdrant collection not created | Medium | Medium | Check existence before operations, rollback on failure |
| Large video ingestion timeout | Medium | Medium | Keep existing retry/timeout logic, add progress indicator |
| User confusion (personal vs channel) | Low | Medium | Clear UI distinction, breadcrumbs, channel description |
| Message model complexity | Medium | Low | Constraint ensures exactly one conversation type |
| Frontend/backend sync issues | Medium | Low | Test WebSocket thoroughly, clear channel_context |
| Duplicate transcript handling | Low | Medium | Detection logic, reuse existing transcripts |

---

## Future Enhancements (Post-MVP)

- [ ] Channel permissions (restrict access to specific users)
- [ ] Channel categories/tags for organization
- [ ] Channel search (find channels by topic/keyword)
- [ ] Channel analytics (most active, most videos, popular channels)
- [ ] Hybrid Qdrant strategy (single collection for small channels)
- [ ] Channel templates (pre-configured channel types)
- [ ] Bulk video upload (CSV of YouTube URLs)
- [ ] Channel subscription notifications (new videos added)
- [ ] Public vs private channels (toggle visibility)
- [ ] Channel moderation tools (flag inappropriate content)
- [ ] Video recommendations within channels
- [ ] Channel export (all content as JSON/ZIP)
- [ ] Multi-language channel support
- [ ] Channel collaboration (multiple admins)

---

**Status:** Ready for implementation with all gaps addressed
**Next Step:** Create feature branch and begin PR #1 (Foundation)
**Estimated Total Time:** 22-30 hours (with frontend + gap fixes)
**PR Count:** 6 PRs (can work on some in parallel)
