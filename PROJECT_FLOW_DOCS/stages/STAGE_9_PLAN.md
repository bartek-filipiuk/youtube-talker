# Phase 9: Health Checks & Conversation API - Implementation Plan

**Version:** 1.0
**Last Updated:** 2025-10-22
**Status:** Ready for Implementation

---

## Overview

Implement health check endpoints, full CRUD conversation API, simple config management, error handling improvements, and hybrid E2E testing strategy to complete Phase 9.

**User Decisions:**
1. **Config Management:** Simple (seed + service, keep hardcoded values)
2. **Conversation API:** Full CRUD (all 4 endpoints)
3. **E2E Testing:** Hybrid (1 automated test + manual checklist)

---

## PR Strategy: 2 PRs

### **PR #17: Core API Endpoints** (~8-12 hours)
**Scope:**
- Health check endpoints (9.1)
- Conversation CRUD API (9.2)
- Config service + seed script (9.4)

**Why together:** These are core API features needed for system testing

### **PR #18: Testing & Polish** (~6-8 hours)
**Scope:**
- Error handling improvements (9.5)
- E2E test (hybrid approach) (9.6)
- Coverage report (9.8)
- Documentation updates (9.9)

**Why together:** Testing and polish work that validates PR #17

**Already Complete:**
- ✅ 9.3 (message validation) - `IncomingMessage` has `max_length=2000`

**Deferred:**
- 9.7 (LangSmith) - optional, can add post-MVP

---

## PR #17: Core API Endpoints

### Files to Create:

**1. `app/api/routes/health.py`**
- `GET /api/health` - basic health check
- `GET /api/health/db` - PostgreSQL connection test
- `GET /api/health/qdrant` - Qdrant connection test

**2. `app/api/routes/conversations.py`**
- `GET /api/conversations` - list user's conversations (paginated)
- `GET /api/conversations/{id}` - get conversation with messages
- `POST /api/conversations` - create new conversation
- `DELETE /api/conversations/{id}` - delete conversation

**3. `app/schemas/conversation.py`**
- `ConversationListResponse`
- `ConversationDetailResponse` (includes messages)
- `ConversationCreateRequest`
- `ConversationResponse`

**4. `app/services/config_service.py`**
- Simple config service with in-memory caching
- `get_config(key: str) -> Any`
- `get_all_config() -> Dict`

**5. `scripts/seed_config.py`**
- Seed config table with default values:
  - `max_context_messages = 10`
  - `rag_top_k = 12`
  - `chunk_size = 700`
  - `chunk_overlap_percent = 20`

### Implementation Details:

#### Health Checks (9.1)
```python
@router.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "youtube-talker-api",
        "version": "0.1.0"
    }

@router.get("/api/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "postgresql"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "postgresql",
                "error": str(e)
            }
        )

@router.get("/api/health/qdrant")
async def health_check_qdrant():
    try:
        qdrant_service = QdrantService()
        await qdrant_service.health_check()
        return {
            "status": "healthy",
            "service": "qdrant"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "qdrant",
                "error": str(e)
            }
        )
```

#### Conversation API (9.2)

##### List Conversations
```python
@router.get("/api/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all conversations for the authenticated user.

    Returns conversations ordered by most recent activity.
    """
    repo = ConversationRepository(db)
    conversations = await repo.list_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )

    return {
        "conversations": conversations,
        "total": len(conversations),
        "limit": limit,
        "offset": offset
    }
```

##### Get Conversation Detail
```python
@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific conversation with all its messages.

    Requires user to own the conversation.
    """
    conv_repo = ConversationRepository(db)
    msg_repo = MessageRepository(db)

    # Get conversation
    conversation = await conv_repo.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership
    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get messages
    messages = await msg_repo.list_by_conversation(conversation_id)

    return {
        "conversation": conversation,
        "messages": messages
    }
```

##### Create Conversation
```python
@router.post("/api/conversations", status_code=201, response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation with optional custom title.

    If no title provided, generates timestamp-based title.
    """
    repo = ConversationRepository(db)

    title = request.title or f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    conversation = await repo.create(
        user_id=current_user.id,
        title=title
    )
    await db.commit()
    await db.refresh(conversation)

    return conversation
```

##### Delete Conversation
```python
@router.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and all its messages.

    Requires user to own the conversation.
    """
    repo = ConversationRepository(db)

    # Get conversation
    conversation = await repo.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership
    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete (cascade deletes messages)
    await repo.delete(conversation_id)
    await db.commit()

    return Response(status_code=204)
```

#### Config Service (9.4)
```python
class ConfigService:
    """
    Simple configuration service with in-memory caching.

    For MVP: Provides visibility into config values without
    requiring refactoring of hardcoded values throughout codebase.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: Dict[str, Any] = {}
        self._cache_loaded = False

    async def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Returns cached value if available, otherwise queries database.
        """
        if not self._cache_loaded:
            await self._load_cache()

        return self._cache.get(key, default)

    async def get_all_config(self) -> Dict[str, Any]:
        """
        Get all configuration values as dictionary.
        """
        if not self._cache_loaded:
            await self._load_cache()

        return self._cache.copy()

    async def refresh_cache(self):
        """
        Reload configuration from database.
        """
        self._cache_loaded = False
        await self._load_cache()

    async def _load_cache(self):
        """
        Internal method to load config from database into memory.
        """
        repo = ConfigRepository(self.db)
        configs = await repo.get_all()  # Assumes this method exists

        self._cache = {
            config.key: self._parse_value(config.value, config.value_type)
            for config in configs
        }
        self._cache_loaded = True

    def _parse_value(self, value: str, value_type: str) -> Any:
        """
        Parse string value to appropriate Python type.
        """
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        else:
            return value
```

### Pydantic Schemas:

```python
# app/schemas/conversation.py

class ConversationBase(BaseModel):
    """Base conversation schema."""
    title: Optional[str] = Field(None, max_length=200)

class ConversationCreateRequest(ConversationBase):
    """Request schema for creating conversation."""
    pass

class ConversationResponse(BaseModel):
    """Response schema for single conversation."""
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    """Response schema for single message."""
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    meta_data: Dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetailResponse(BaseModel):
    """Response schema for conversation with messages."""
    conversation: ConversationResponse
    messages: List[MessageResponse]

class ConversationListResponse(BaseModel):
    """Response schema for conversation list."""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int
```

### Tests:

**`tests/integration/test_health_endpoints.py`**
```python
def test_health_check(client):
    """Basic health check returns 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_health_check_db_healthy(client, db):
    """DB health check returns healthy when connected."""
    response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_health_check_qdrant_healthy(client):
    """Qdrant health check returns healthy when connected."""
    response = client.get("/api/health/qdrant")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

**`tests/integration/test_conversation_api.py`**
```python
def test_list_conversations_empty(auth_client):
    """List conversations returns empty list for new user."""
    response = auth_client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert data["conversations"] == []
    assert data["total"] == 0

def test_create_conversation(auth_client):
    """Create conversation with custom title."""
    response = auth_client.post(
        "/api/conversations",
        json={"title": "Test Conversation"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Conversation"

def test_get_conversation_detail(auth_client, conversation_id):
    """Get conversation with messages."""
    response = auth_client.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 200
    data = response.json()
    assert "conversation" in data
    assert "messages" in data

def test_get_conversation_forbidden(auth_client, other_user_conversation_id):
    """Cannot access other user's conversation."""
    response = auth_client.get(f"/api/conversations/{other_user_conversation_id}")
    assert response.status_code == 403

def test_delete_conversation(auth_client, conversation_id):
    """Delete conversation returns 204."""
    response = auth_client.delete(f"/api/conversations/{conversation_id}")
    assert response.status_code == 204

    # Verify deleted
    response = auth_client.get(f"/api/conversations/{conversation_id}")
    assert response.status_code == 404
```

**`tests/unit/test_config_service.py`**
```python
@pytest.mark.asyncio
async def test_get_config(db_session):
    """Get config value from database."""
    service = ConfigService(db_session)
    value = await service.get_config("max_context_messages")
    assert value == 10

@pytest.mark.asyncio
async def test_get_config_with_default(db_session):
    """Get config returns default for missing key."""
    service = ConfigService(db_session)
    value = await service.get_config("nonexistent_key", default=42)
    assert value == 42

@pytest.mark.asyncio
async def test_config_caching(db_session):
    """Config values are cached in memory."""
    service = ConfigService(db_session)

    # First call loads from DB
    value1 = await service.get_config("max_context_messages")

    # Second call uses cache (no DB query)
    value2 = await service.get_config("max_context_messages")

    assert value1 == value2
```

### Seed Script:

**`scripts/seed_config.py`**
```python
"""
Seed configuration table with default values for Phase 9.
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker
from app.db.repositories.config_repo import ConfigRepository

async def seed_config():
    """Seed config table with default values."""
    async with async_session_maker() as session:
        repo = ConfigRepository(session)

        # Define default configurations
        configs = [
            {
                "key": "max_context_messages",
                "value": "10",
                "value_type": "int",
                "description": "Maximum number of messages to include in conversation context"
            },
            {
                "key": "rag_top_k",
                "value": "12",
                "value_type": "int",
                "description": "Number of chunks to retrieve from Qdrant"
            },
            {
                "key": "chunk_size",
                "value": "700",
                "value_type": "int",
                "description": "Target chunk size in tokens"
            },
            {
                "key": "chunk_overlap_percent",
                "value": "20",
                "value_type": "int",
                "description": "Percentage overlap between chunks"
            }
        ]

        # Create or update configs
        for config_data in configs:
            # Check if exists
            existing = await repo.get_by_key(config_data["key"])

            if not existing:
                await repo.create(**config_data)
                print(f"✓ Created config: {config_data['key']} = {config_data['value']}")
            else:
                print(f"○ Config already exists: {config_data['key']}")

        await session.commit()
        print("\n✅ Config seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_config())
```

### Acceptance Criteria:
- ✅ All health checks return proper status
- ✅ Failed health checks return 503
- ✅ All CRUD operations work
- ✅ Only user's own conversations accessible
- ✅ Config service reads from database
- ✅ Test coverage > 80%

---

## PR #18: Testing & Polish

### Files to Create/Update:

**1. `app/core/errors.py`** (new)
```python
"""Custom exception classes for better error handling."""

class ConversationNotFoundError(Exception):
    """Raised when conversation doesn't exist."""
    pass

class ConversationAccessDeniedError(Exception):
    """Raised when user doesn't own conversation."""
    pass

class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""
    pass

class InvalidInputError(Exception):
    """Raised when input validation fails."""
    pass
```

**2. `app/core/exception_handlers.py`** (new)
```python
"""Global exception handlers for FastAPI."""

from fastapi import Request
from fastapi.responses import JSONResponse

async def conversation_not_found_handler(request: Request, exc: ConversationNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": "Conversation not found"}
    )

async def conversation_access_denied_handler(request: Request, exc: ConversationAccessDeniedError):
    return JSONResponse(
        status_code=403,
        content={"detail": "Access denied to this conversation"}
    )

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceededError):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )
```

**3. `app/main.py`** (update)
```python
# Add exception handlers
from app.core.errors import (
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    RateLimitExceededError
)
from app.core.exception_handlers import (
    conversation_not_found_handler,
    conversation_access_denied_handler,
    rate_limit_exceeded_handler
)

# Register handlers
app.add_exception_handler(ConversationNotFoundError, conversation_not_found_handler)
app.add_exception_handler(ConversationAccessDeniedError, conversation_access_denied_handler)
app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
```

**4. `tests/e2e/test_user_journey.py`** (new)
```python
"""
End-to-end test for complete user journey.

Tests the happy path with mocked LLM for speed and reliability.
"""

@pytest.mark.asyncio
async def test_complete_user_journey(client, mock_llm):
    """
    Complete user journey from registration to cleanup.

    Steps:
    1. Register user
    2. Login (get token)
    3. Create conversation via API
    4. Connect WebSocket with token
    5. Send message (mocked LLM response)
    6. Verify messages saved in DB
    7. List conversations via API
    8. Delete conversation via API
    9. Verify deletion
    10. Logout
    """
    # 1. Register
    register_response = client.post("/api/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert register_response.status_code == 201

    # 2. Login
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert login_response.status_code == 200
    token = login_response.json()["token"]

    # 3. Create conversation
    conv_response = client.post(
        "/api/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test Conversation"}
    )
    assert conv_response.status_code == 201
    conversation_id = conv_response.json()["id"]

    # 4-6. WebSocket interaction (simplified)
    # ... WebSocket test code ...

    # 7. List conversations
    list_response = client.get(
        "/api/conversations",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["conversations"]) == 1

    # 8-9. Delete conversation
    delete_response = client.delete(
        f"/api/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_response.status_code == 204

    # Verify deletion
    get_response = client.get(
        f"/api/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404

    # 10. Logout
    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_response.status_code == 204
```

**5. `docs/MANUAL_TEST_CHECKLIST.md`** (new)
```markdown
# Manual Test Checklist

Complete system verification with real services.

## Prerequisites
- ✅ All services running (PostgreSQL, Qdrant, Backend)
- ✅ Database seeded with test data
- ✅ Valid OpenRouter API key
- ✅ Valid OpenAI API key (for embeddings)

## Test Scenarios

### 1. User Registration & Authentication
- [ ] Register new user
- [ ] Login with valid credentials
- [ ] Login with invalid credentials (should fail)
- [ ] Access protected endpoint without token (should fail)
- [ ] Access protected endpoint with valid token
- [ ] Logout

### 2. YouTube Transcript Ingestion
- [ ] Ingest valid YouTube URL
- [ ] Verify transcript saved in database
- [ ] Verify chunks created in database
- [ ] Verify vectors in Qdrant
- [ ] Attempt duplicate ingest (should fail)
- [ ] Ingest invalid URL (should fail)

### 3. WebSocket Chat
- [ ] Connect with valid token
- [ ] Connect with invalid token (should fail)
- [ ] Send chitchat message → receive response
- [ ] Send Q&A question → see status updates → receive answer
- [ ] Request LinkedIn post → receive formatted post
- [ ] Verify conversation auto-creation
- [ ] Verify messages saved to database

### 4. Conversation Management
- [ ] List conversations (should see WebSocket-created conversations)
- [ ] Get conversation detail with messages
- [ ] Create conversation via API
- [ ] Delete conversation
- [ ] Attempt to access other user's conversation (should fail)

### 5. Rate Limiting
- [ ] Send 10 WebSocket messages rapidly (all succeed)
- [ ] Send 11th message (should be rate-limited)
- [ ] Wait 60 seconds
- [ ] Send message (should work again)

### 6. Error Scenarios
- [ ] Invalid YouTube URL → user-friendly error
- [ ] LLM API failure → user-friendly error
- [ ] Database connection issue → 503 from health check
- [ ] Qdrant unavailable → 503 from health check

### 7. Multi-User Testing
- [ ] Register 2 different users
- [ ] Each user creates conversation
- [ ] User A cannot access User B's conversation
- [ ] Rate limits are independent per user

## Performance Checks
- [ ] RAG retrieval < 500ms
- [ ] WebSocket first message < 3s
- [ ] List conversations < 200ms
- [ ] Health checks < 100ms

## Success Criteria
All checkboxes above must pass for Phase 9 to be considered complete.
```

**6. `backend/README.md`** (update)
Add section on Phase 9 endpoints:
```markdown
## API Endpoints

### Health Checks
- `GET /api/health` - Basic health check
- `GET /api/health/db` - Database connection status
- `GET /api/health/qdrant` - Qdrant connection status

### Conversations
- `GET /api/conversations` - List user's conversations
- `GET /api/conversations/{id}` - Get conversation with messages
- `POST /api/conversations` - Create new conversation
- `DELETE /api/conversations/{id}` - Delete conversation

All conversation endpoints require authentication.
```

### Acceptance Criteria:
- ✅ Custom exception classes defined
- ✅ Global exception handlers registered
- ✅ Structured logging implemented
- ✅ E2E test passes
- ✅ Manual test checklist documented
- ✅ Test coverage > 80%
- ✅ README updated

---

## File Structure Summary
```
app/
├── api/
│   └── routes/
│       ├── health.py           # NEW (PR #17)
│       └── conversations.py     # NEW (PR #17)
├── core/
│   ├── errors.py               # NEW (PR #18)
│   └── exception_handlers.py   # NEW (PR #18)
├── schemas/
│   └── conversation.py         # NEW (PR #17)
├── services/
│   └── config_service.py       # NEW (PR #17)
scripts/
└── seed_config.py              # NEW (PR #17)
tests/
├── integration/
│   ├── test_health_endpoints.py      # NEW (PR #17)
│   └── test_conversation_api.py      # NEW (PR #17)
├── unit/
│   └── test_config_service.py        # NEW (PR #17)
└── e2e/
    └── test_user_journey.py          # NEW (PR #18)
docs/
└── MANUAL_TEST_CHECKLIST.md          # NEW (PR #18)
```

---

## Success Criteria

✅ **PR #17 Complete When:**
- Health endpoints work (3/3)
- Conversation CRUD works (4/4)
- Config service retrieves values
- All integration tests pass
- Coverage > 80% for new code

✅ **PR #18 Complete When:**
- Error handling improved
- E2E test passes
- Manual checklist documented
- Overall coverage > 80%
- README updated

✅ **Phase 9 Complete When:**
- System can be tested end-to-end
- All core APIs documented
- Ready for frontend integration

---

**Document Version:**
- v1.0 (2025-10-22): Initial Phase 9 plan based on user decisions
