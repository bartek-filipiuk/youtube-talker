
# Stage: Chat-Based Video Loading (Priority 2.2)

**Feature**: Load YouTube videos to knowledge base directly from chat interface

**Status**: Planning Complete → Ready for Implementation

**Priority**: 2.2 (Performance & Core UX)

**Estimated Effort**: 3-4 days

---

## 📋 Feature Requirements (from User Responses)

| Aspect | Decision |
|--------|----------|
| **Confirmation** | Ask for confirmation before loading |
| **Architecture** | Hybrid (WebSocket triggers background API, streams progress) |
| **Processing** | Async (background job, non-blocking) |
| **Duplicates** | Skip with message: "You already have this video" |
| **Metadata** | Always use YouTube (auto-fetch title, channel, duration) |
| **Error Handling** | Show clear error messages for all scenarios |
| **Limits** | Role-based: **admin = unlimited**, **user = max 10 videos** |
| **Progress** | Silent background (start + completion messages only) |
| **UI Pattern** | Simple text response (AI asks "Load this video? Reply yes/no") |
| **Playlists** | Single videos only (MVP scope) |

---

## 🏗️ Architecture Overview

```
User pastes YouTube URL in chat
         ↓
Router Node detects URL → intent: "video_load"
         ↓
Confirmation Handler:
  - Extract video ID
  - Check duplicates (TranscriptRepository)
  - Check quota (UserRepository)
  - Fetch video metadata (YouTube API preview)
  - Send confirmation message
         ↓
User replies "yes" or "no"
         ↓
If YES:
  - Create background async task
  - Call TranscriptService.ingest_transcript()
  - Send "Loading video in background..."
  - Continue chat (non-blocking)
         ↓
On completion (30-60s later):
  - Send "Video loaded: [title]" or error message
```

---

## 📦 Implementation Plan

### Phase 1: Database & Schema Updates

#### 1.1 Add User Role System

**Migration**: `alembic revision --autogenerate -m "add_user_role_and_quota"`

```sql
-- Add role enum type
CREATE TYPE user_role AS ENUM ('user', 'admin');

-- Add role column to users table
ALTER TABLE users
ADD COLUMN role user_role NOT NULL DEFAULT 'user';

-- Add transcript_count for quota tracking
ALTER TABLE users
ADD COLUMN transcript_count INTEGER NOT NULL DEFAULT 0;

-- Index for faster role checks
CREATE INDEX idx_users_role ON users(role);
```

**Files to Update**:
- `backend/app/db/models.py`: Update `User` model
  - Add `role: Mapped[str]` field with CHECK constraint
  - Add `transcript_count: Mapped[int]` field

**Seed Script Update**:
- `backend/scripts/seed_database.py`: Make first user admin

#### 1.2 Increment Transcript Count

**Options**:
1. **Application Layer** (Recommended for MVP):
   - Increment in `TranscriptService.ingest_transcript()`
   - Simpler, easier to test

2. **Database Trigger** (Future Enhancement):
   - Automatic, but adds complexity

---

### Phase 2: WebSocket Message Types

**File**: `backend/app/api/websocket/messages.py`

**New Message Classes**:

```python
class LoadVideoConfirmationMessage(BaseModel):
    """Server asks user to confirm video loading."""
    type: Literal["video_load_confirmation"] = "video_load_confirmation"
    youtube_url: str
    video_id: str
    video_title: Optional[str] = None  # Preview from YouTube
    message: str  # "Load this video? Reply yes/no"

class LoadVideoResponseMessage(BaseModel):
    """Client confirms or rejects video loading."""
    type: Literal["video_load_response"] = "video_load_response"
    confirmed: bool  # True for yes, False for no
    conversation_id: str

class VideoLoadStatusMessage(BaseModel):
    """Server notifies start/completion of loading."""
    type: Literal["video_load_status"] = "video_load_status"
    status: Literal["started", "completed", "failed"]
    message: str
    video_title: Optional[str] = None
    error: Optional[str] = None
```

---

### Phase 3: URL Detection & Intent Classification

#### 3.1 Create URL Detector Utility

**File**: `backend/app/utils/url_detector.py`

```python
import re
from typing import Optional

YOUTUBE_PATTERNS = [
    r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
]

def detect_youtube_url(text: str) -> Optional[str]:
    """
    Detect YouTube URL and extract video ID.

    Returns:
        Video ID if found, None otherwise
    """
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def is_youtube_url(text: str) -> bool:
    """Check if text contains a YouTube URL."""
    return detect_youtube_url(text) is not None
```

**Tests**: `backend/tests/unit/test_url_detector.py`

#### 3.2 Update Intent Classification

**File**: `backend/app/schemas/llm_responses.py`

```python
class IntentClassification(BaseModel):
    intent: Literal["chitchat", "qa", "linkedin", "metadata", "video_load"]
    # Add "video_load" to allowed intents
```

**File**: `backend/app/rag/prompts/query_router.jinja2`

Add video_load intent description:
```
- "video_load": User pasted a YouTube URL and wants to load it to knowledge base
```

---

### Phase 4: Confirmation Flow Handler

#### 4.1 Create Video Loader Module

**File**: `backend/app/api/websocket/video_loader.py`

**Key Components**:

```python
class PendingVideoLoad:
    """Track pending video load confirmations."""
    conversation_id: str
    youtube_url: str
    video_id: str
    video_title: Optional[str]
    user_id: UUID
    created_at: datetime

# In-memory store (MVP: dict, can upgrade to Redis later)
pending_loads: Dict[str, PendingVideoLoad] = {}

async def handle_video_load_intent(
    state: GraphState,
    db: AsyncSession,
    websocket: WebSocket
) -> None:
    """Handle video_load intent: check duplicates, quota, ask confirmation."""

    # 1. Extract video ID
    # 2. Check duplicates
    # 3. Check user quota and role
    # 4. Fetch video metadata preview (optional)
    # 5. Store in pending_loads
    # 6. Send confirmation message via WebSocket

async def handle_confirmation_response(
    response: str,
    conversation_id: str,
    user_id: UUID,
    db: AsyncSession,
    websocket: WebSocket
) -> bool:
    """
    Handle yes/no response to confirmation.

    Returns True if handled as confirmation, False otherwise.
    """

    # Check if pending load exists
    # Match yes/no patterns
    # If yes: trigger background load
    # If no: cancel and clear
    # Send appropriate message
```

#### 4.2 Quota Checking Logic

```python
async def check_user_quota(
    user: User,
    db: AsyncSession
) -> tuple[bool, str]:
    """
    Check if user can load another video.

    Returns:
        (allowed: bool, message: str)
    """
    if user.role == "admin":
        return True, ""

    if user.transcript_count >= 10:
        return False, (
            "You've reached your video limit (10 videos). "
            "Delete some videos to add more, or contact support for an upgrade."
        )

    return True, ""
```

---

### Phase 5: Background Loading Integration

#### 5.1 Async Task Handler

**File**: `backend/app/api/websocket/video_loader.py`

```python
async def trigger_background_load(
    youtube_url: str,
    user_id: UUID,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket
) -> None:
    """Trigger transcript ingestion in background."""

    # Send immediate status
    await websocket.send_json({
        "type": "video_load_status",
        "status": "started",
        "message": "Loading video in background. You can continue chatting..."
    })

    # Create background task
    asyncio.create_task(
        load_video_background(
            youtube_url, user_id, conversation_id, db, websocket
        )
    )

async def load_video_background(
    youtube_url: str,
    user_id: UUID,
    conversation_id: str,
    db: AsyncSession,
    websocket: WebSocket
) -> None:
    """Background task for video loading."""

    try:
        service = TranscriptService()
        result = await service.ingest_transcript(
            youtube_url=youtube_url,
            user_id=user_id,
            db_session=db
        )

        # Increment user transcript count
        user_repo = UserRepository(db)
        await user_repo.increment_transcript_count(user_id)

        # Send success message
        await websocket.send_json({
            "type": "video_load_status",
            "status": "completed",
            "message": f"Video loaded successfully: {result['metadata']['title']}",
            "video_title": result['metadata']['title']
        })

    except Exception as e:
        logger.exception(f"Background video load failed: {e}")
        await websocket.send_json({
            "type": "video_load_status",
            "status": "failed",
            "message": f"Failed to load video: {str(e)}",
            "error": str(e)
        })
```

---

### Phase 6: Chat Handler Integration

**File**: `backend/app/api/websocket/chat_handler.py`

**Updates**:

```python
async def handle_message(self, data: dict) -> None:
    """Handle incoming user message."""

    # ... existing code ...

    # Check if this is a confirmation response
    if conversation_id in pending_loads:
        handled = await handle_confirmation_response(
            content, conversation_id, user.id, self.db, self.websocket
        )
        if handled:
            return  # Don't process as regular message

    # ... continue with normal RAG flow ...

    # In router node result handling:
    if intent == "video_load":
        await handle_video_load_intent(
            state, self.db, self.websocket
        )
        return  # Don't continue to RAG flows
```

---

### Phase 7: Error Handling

**Error Scenarios & Messages**:

| Scenario | Message |
|----------|---------|
| Invalid URL | "This doesn't look like a valid YouTube URL. Please paste a YouTube video link." |
| Video already exists | "You already have this video: **[Title]**. You can start asking questions about it!" |
| Quota exceeded | "You've reached your video limit (10 videos). Delete some to add more, or contact support." |
| Private/unavailable | "This video is unavailable or private. Please check the URL and try again." |
| API failure | "Failed to load video. Please try again in a moment." |
| Network timeout | "Loading is taking longer than expected. Please check back in a minute." |

**Logging** (`app/core/logging.py`):
```python
logger.info(
    "Video load attempt",
    user_id=user_id,
    video_id=video_id,
    result="success|failure",
    reason="duplicate|quota|api_error"
)
```

---

### Phase 8: Testing Strategy

#### 8.1 Unit Tests

**File**: `backend/tests/unit/test_url_detector.py`
- Test valid YouTube URL formats
- Test invalid URLs
- Test URL extraction

**File**: `backend/tests/unit/test_video_loader.py`
- Test quota checking logic
- Test confirmation message formatting
- Test pending load lifecycle

**File**: `backend/tests/unit/test_video_load_messages.py`
- Test new message schema validation

#### 8.2 Integration Tests

**File**: `backend/tests/integration/test_video_loading_flow.py`

**Test Cases**:
1. `test_full_video_load_flow_success`
   - User pastes URL
   - Gets confirmation
   - Replies yes
   - Video loads successfully

2. `test_duplicate_video_detection`
   - User pastes URL for existing video
   - Gets skip message
   - No load triggered

3. `test_quota_enforcement_user`
   - User with 10 videos
   - Pastes new URL
   - Gets quota limit message

4. `test_quota_bypass_admin`
   - Admin user with 50 videos
   - Pastes new URL
   - Load proceeds normally

5. `test_confirmation_cancel`
   - User pastes URL
   - Replies "no"
   - Load cancelled

6. `test_invalid_url_handling`
   - User pastes invalid URL
   - Gets error message

#### 8.3 Manual Testing Checklist

- [ ] Paste valid YouTube URL → Get confirmation with video title
- [ ] Reply "yes" → See "Loading in background" message
- [ ] Wait ~30-60s → See "Video loaded: [title]" message
- [ ] Reply "no" → See cancellation message
- [ ] Paste duplicate URL → Get "already have" message
- [ ] User with 10 videos → Paste URL → Get quota message
- [ ] Admin user → No quota restrictions
- [ ] Invalid URL → Clear error message
- [ ] Private video → Unavailable message
- [ ] Chat continues working during background load

---

### Phase 9: Frontend Updates

**File**: `frontend/src/pages/chat.astro`

**WebSocket Handler Updates**:

```javascript
wsClient.onMessage((data) => {
  // ... existing handlers ...

  if (data.type === 'video_load_confirmation') {
    // Display confirmation message from AI
    addMessage('assistant', data.message);
    // Note: User will reply via normal chat input
  }

  if (data.type === 'video_load_status') {
    // Display loading status
    if (data.status === 'started') {
      // Show loading indicator or status message
      addMessage('assistant', data.message);
    } else if (data.status === 'completed') {
      // Show success message
      addMessage('assistant', `✅ ${data.message}`);
    } else if (data.status === 'failed') {
      // Show error message
      addMessage('assistant', `❌ ${data.message}`);
    }
  }
});
```

**No UI Changes Required**:
- Uses existing chat interface
- Text-based interaction
- Messages display like normal assistant responses

---

## 📝 Implementation Checklist

### Backend - Database (Phase 1)
- [ ] Create Alembic migration for user role and transcript_count
- [ ] Run migration: `alembic upgrade head`
- [ ] Update User model with role and transcript_count fields
- [ ] Add role field to seed script (make first user admin)
- [ ] Test migration rollback

### Backend - Core Logic (Phases 2-5)
- [ ] Create `app/utils/url_detector.py` with YouTube URL detection
- [ ] Write unit tests for URL detector
- [ ] Add "video_load" intent to `IntentClassification` schema
- [ ] Update query_router.jinja2 prompt
- [ ] Create new WebSocket message schemas in `messages.py`
- [ ] Create `app/api/websocket/video_loader.py`:
  - [ ] PendingVideoLoad dataclass
  - [ ] pending_loads in-memory store
  - [ ] check_user_quota() function
  - [ ] handle_video_load_intent() function
  - [ ] handle_confirmation_response() function
  - [ ] trigger_background_load() function
  - [ ] load_video_background() async task
- [ ] Add increment_transcript_count() to UserRepository
- [ ] Integrate video_loader into chat_handler.py

### Backend - Testing (Phase 8)
- [ ] Write unit tests for url_detector
- [ ] Write unit tests for video_loader logic
- [ ] Write unit tests for new message schemas
- [ ] Write integration test for full flow
- [ ] Write integration test for duplicates
- [ ] Write integration test for quota enforcement
- [ ] Write integration test for admin bypass
- [ ] Write integration test for cancellation
- [ ] Run all tests: `pytest tests/ --cov=app`

### Frontend (Phase 9)
- [ ] Update WebSocket message handler in chat.astro
- [ ] Handle video_load_confirmation messages
- [ ] Handle video_load_status messages
- [ ] Test in browser with real YouTube URL

### Documentation & Cleanup
- [ ] Update API documentation
- [ ] Add docstrings to all new functions
- [ ] Update HANDOFF.md with completion status
- [ ] Update POST_MVP_FEATURES.md (mark 2.2 as done)

---

## 🚀 Success Criteria

**Functional**:
- ✅ User can paste YouTube URL and get confirmation
- ✅ User can reply yes/no to load video
- ✅ Video loads in background without blocking chat
- ✅ Duplicate videos are detected and skipped
- ✅ Quota enforcement works (user: 10, admin: unlimited)
- ✅ Clear error messages for all failure scenarios

**Technical**:
- ✅ All unit tests pass (100% of new code)
- ✅ All integration tests pass
- ✅ No regressions in existing chat functionality
- ✅ Code follows project style (Black, Ruff, type hints)
- ✅ Proper error handling and logging

**User Experience**:
- ✅ Simple text-based interaction
- ✅ Fast response (confirmation < 2s)
- ✅ Non-blocking background loading
- ✅ Clear status updates

---

## 🔮 Future Enhancements (Out of Scope)

**Priority 3** (after MVP completion):
- [ ] Playlist support (load multiple videos)
- [ ] Custom video titles/descriptions
- [ ] Progress bar with percentage
- [ ] Edit video metadata after loading
- [ ] Batch loading (paste multiple URLs)
- [ ] Video preview thumbnails
- [ ] Quota increase options (user settings)

**Priority 4** (nice to have):
- [ ] Redis-based pending_loads (for multi-instance)
- [ ] Job queue (Celery/RQ) for better scalability
- [ ] Detailed loading progress (fetching, chunking, embedding)
- [ ] Video tags/categories
- [ ] Shared videos (load once, available to all users)

---

## 📊 Estimated Timeline

| Phase | Task | Time |
|-------|------|------|
| 1 | Database & migration | 2-3 hours |
| 2 | WebSocket messages | 1 hour |
| 3 | URL detection & intent | 2 hours |
| 4 | Confirmation flow | 4-5 hours |
| 5 | Background loading | 3-4 hours |
| 6 | Chat handler integration | 2-3 hours |
| 7 | Error handling | 2 hours |
| 8 | Testing (unit + integration) | 6-8 hours |
| 9 | Frontend updates | 2 hours |
| | **Total Development** | **24-30 hours (3-4 days)** |

---

## 📌 Dependencies

**External APIs**:
- SUPADATA API (existing, for transcript fetching)
- YouTube API (optional, for video title preview - can extract from SUPADATA response)

**Internal Services**:
- TranscriptService (existing, reused)
- UserRepository (needs new method: increment_transcript_count)
- TranscriptRepository (existing, for duplicate check)

**Libraries**:
- No new dependencies required
- Uses existing: asyncio, FastAPI, SQLAlchemy, Pydantic

---

**Last Updated**: 2025-10-27
**Author**: Development Team
**Status**: Ready for Implementation

