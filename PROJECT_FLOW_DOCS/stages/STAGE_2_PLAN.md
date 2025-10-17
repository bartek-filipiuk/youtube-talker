# Phase 2: Database Setup & Migrations - Implementation Plan

**Phase:** 2
**Stages:** 2.1 - 2.6
**Status:** Ready for Implementation
**Created:** 2025-10-17

---

## Overview

Implement complete database layer with SQLAlchemy ORM, Alembic migrations, and repository pattern for all 8 database models.

---

## Prerequisites Verified ✅

- PostgreSQL running on port 5435 (docker compose)
- Qdrant running on port 6335
- Phase 1 completed (FastAPI app, config, middleware with tests)
- All dependencies installed (SQLAlchemy, asyncpg, alembic, pytest)
- Currently on `main` branch

---

## Work Plan (6 Stages, 6 Commits)

### Stage 2.1: SQLAlchemy Configuration

**Objective:** Set up async SQLAlchemy engine with connection pooling and database session management.

**Files to create:**
- `backend/app/db/session.py` - Async engine, connection pool (size=20, max_overflow=10), get_db() dependency
- `backend/app/db/models.py` - Base declarative class

**Implementation Details:**
```python
# session.py requirements:
- AsyncEngine with DATABASE_URL from config
- Connection pool: pool_size=20, max_overflow=10
- async_sessionmaker with AsyncSession
- get_db() async generator for dependency injection
- Proper session lifecycle (commit/rollback/close)

# models.py requirements:
- DeclarativeBase class for all models
- Import all models for Alembic autogenerate
```

**Testing:**
- Simple query to verify connection works
- Test get_db() dependency injection

**Acceptance Criteria:**
- [ ] Database connection succeeds
- [ ] Connection pooling is configured
- [ ] get_db() dependency works in routes

**Commit Message:** `feat(db): add SQLAlchemy async configuration and session management`

---

### Stage 2.2: Alembic Setup

**Objective:** Configure Alembic for async database migrations.

**Actions:**
1. Initialize Alembic: `cd backend && alembic init alembic`
2. Configure `alembic/env.py` for async engine
3. Configure `alembic.ini` to read DATABASE_URL from config
4. Test with `alembic check`

**Implementation Details:**
```python
# alembic/env.py modifications:
- Import app.db.models.Base
- Use async engine from app.db.session
- Configure run_async() for migrations
- Set target_metadata = Base.metadata

# alembic.ini modifications:
- Remove hardcoded sqlalchemy.url
- Read from environment via config.py
```

**Testing:**
- Run `alembic check` without errors
- Verify Alembic can connect to database

**Acceptance Criteria:**
- [ ] Alembic is configured for async SQLAlchemy
- [ ] Migrations can be generated and applied
- [ ] `alembic check` runs without errors

**Commit Message:** `feat(db): configure Alembic for async migrations`

---

### Stage 2.3: Define Database Models

**Objective:** Implement all 8 database models according to DATABASE_SCHEMA.md.

**File to update:** `backend/app/db/models.py`

**Models to implement (8 total):**

1. **User**
   - id (UUID, PK)
   - email (VARCHAR(255), unique, indexed)
   - password_hash (VARCHAR(255))
   - created_at, updated_at (TIMESTAMP)
   - Constraint: email format validation

2. **Session**
   - id (UUID, PK)
   - user_id (UUID, FK → users.id, indexed)
   - token_hash (VARCHAR(255), unique, indexed)
   - expires_at (TIMESTAMP, indexed)
   - created_at (TIMESTAMP)

3. **Conversation**
   - id (UUID, PK)
   - user_id (UUID, FK → users.id, indexed)
   - title (VARCHAR(500), nullable)
   - created_at, updated_at (TIMESTAMP, updated_at indexed DESC)

4. **Message**
   - id (UUID, PK)
   - conversation_id (UUID, FK → conversations.id, indexed)
   - role (VARCHAR(50), CHECK: 'user'|'assistant'|'system')
   - content (TEXT)
   - metadata (JSONB, GIN indexed)
   - created_at (TIMESTAMP, indexed)

5. **Transcript**
   - id (UUID, PK)
   - user_id (UUID, FK → users.id, indexed)
   - youtube_video_id (VARCHAR(50), unique, indexed)
   - title (VARCHAR(500), nullable)
   - channel_name (VARCHAR(255), nullable)
   - duration (INTEGER, nullable)
   - transcript_text (TEXT)
   - metadata (JSONB, GIN indexed)
   - created_at (TIMESTAMP)

6. **Chunk**
   - id (UUID, PK)
   - transcript_id (UUID, FK → transcripts.id, indexed)
   - user_id (UUID, FK → users.id, indexed)
   - chunk_text (TEXT)
   - chunk_index (INTEGER)
   - token_count (INTEGER)
   - metadata (JSONB, GIN indexed)
   - created_at (TIMESTAMP)
   - Constraint: UNIQUE(transcript_id, chunk_index)

7. **Template**
   - id (UUID, PK)
   - user_id (UUID, FK → users.id, nullable, indexed)
   - template_type (VARCHAR(50), CHECK: 'linkedin'|'twitter'|'blog'|'email')
   - template_name (VARCHAR(255))
   - template_content (TEXT)
   - variables (JSONB, default '[]')
   - is_default (BOOLEAN, default False)
   - created_at, updated_at (TIMESTAMP)
   - Constraint: UNIQUE(user_id, template_type, template_name)
   - Index: (template_type, is_default)

8. **Config**
   - key (VARCHAR(100), PK)
   - value (JSONB)
   - description (TEXT, nullable)
   - updated_at (TIMESTAMP)

**Implementation Requirements:**
- Use SQLAlchemy 2.0 syntax (Mapped, mapped_column)
- All ForeignKeys with ON DELETE CASCADE
- All indexes defined per DATABASE_SCHEMA.md
- JSONB columns with proper defaults
- UUID primary keys with server_default=gen_random_uuid()
- Proper relationships (relationship() with back_populates)

**Testing:**
- Verify models can be imported without errors
- Check Base.metadata.tables contains all 8 tables

**Acceptance Criteria:**
- [ ] All 8 models match DATABASE_SCHEMA.md
- [ ] All indexes are defined
- [ ] All relationships are correctly configured
- [ ] All constraints (unique, check, FK) are present

**Commit Message:** `feat(db): define all 8 database models with relationships and indexes`

---

### Stage 2.4: Create Initial Migration

**Objective:** Generate and apply the initial database migration.

**Actions:**
1. Generate migration: `alembic revision --autogenerate -m "Initial schema"`
2. Review generated migration file in `alembic/versions/`
3. Add custom SQL for trigger (conversation.updated_at)
4. Apply migration: `alembic upgrade head`
5. Test reversibility: `alembic downgrade -1` && `alembic upgrade head`
6. Verify tables in PostgreSQL: `psql` or database client

**Custom SQL to Add:**
```sql
-- Trigger function for updating conversation.updated_at
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on messages INSERT
CREATE TRIGGER trigger_update_conversation
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_timestamp();
```

**Testing:**
- Run migration: `alembic upgrade head`
- Connect to database and verify 8 tables exist
- Check indexes: `\di` in psql
- Test downgrade: `alembic downgrade -1`
- Test upgrade again: `alembic upgrade head`
- Test trigger: Insert message, verify conversation.updated_at changes

**Acceptance Criteria:**
- [ ] All 8 tables created successfully
- [ ] Indexes and constraints are present
- [ ] Migration is reversible
- [ ] Trigger for conversation.updated_at works

**Commit Message:** `feat(db): create initial migration with all tables and triggers`

---

### Stage 2.5: Create Repository Layer

**Objective:** Implement repository pattern for all database models.

**Files to create:**

1. **`backend/app/db/repositories/base.py`**
   - BaseRepository abstract class
   - Common methods: get_by_id, create, update, delete
   - Type hints with generics
   - AsyncSession dependency

2. **`backend/app/db/repositories/user_repo.py`**
   ```python
   class UserRepository(BaseRepository[User]):
       async def get_by_id(user_id: UUID) -> User | None
       async def get_by_email(email: str) -> User | None
       async def create(email: str, password_hash: str) -> User
   ```

3. **`backend/app/db/repositories/session_repo.py`**
   ```python
   class SessionRepository(BaseRepository[Session]):
       async def create(user_id: UUID, token_hash: str, expires_at: datetime) -> Session
       async def get_by_token(token_hash: str) -> Session | None
       async def delete(session_id: UUID) -> None
       async def delete_expired() -> int
   ```

4. **`backend/app/db/repositories/conversation_repo.py`**
   ```python
   class ConversationRepository(BaseRepository[Conversation]):
       async def create(user_id: UUID, title: str | None) -> Conversation
       async def get_by_id(conversation_id: UUID) -> Conversation | None
       async def list_by_user(user_id: UUID, limit: int, offset: int) -> List[Conversation]
       async def delete(conversation_id: UUID) -> None
   ```

5. **`backend/app/db/repositories/message_repo.py`**
   ```python
   class MessageRepository(BaseRepository[Message]):
       async def create(conversation_id: UUID, role: str, content: str, metadata: dict) -> Message
       async def list_by_conversation(conversation_id: UUID, limit: int, offset: int) -> List[Message]
       async def get_last_n(conversation_id: UUID, n: int) -> List[Message]
   ```

6. **`backend/app/db/repositories/transcript_repo.py`**
   ```python
   class TranscriptRepository(BaseRepository[Transcript]):
       async def create(user_id: UUID, youtube_video_id: str, title: str, ...) -> Transcript
       async def get_by_id(transcript_id: UUID) -> Transcript | None
       async def get_by_video_id(user_id: UUID, youtube_video_id: str) -> Transcript | None
       async def list_by_user(user_id: UUID) -> List[Transcript]
   ```

7. **`backend/app/db/repositories/chunk_repo.py`**
   ```python
   class ChunkRepository(BaseRepository[Chunk]):
       async def create_many(chunks: List[dict]) -> List[Chunk]
       async def get_by_ids(chunk_ids: List[UUID]) -> List[Chunk]
       async def list_by_transcript(transcript_id: UUID) -> List[Chunk]
       async def delete_by_transcript(transcript_id: UUID) -> int
   ```

8. **`backend/app/db/repositories/template_repo.py`**
   ```python
   class TemplateRepository(BaseRepository[Template]):
       async def get_template(user_id: UUID, template_type: str) -> Template | None
       async def create_template(user_id: UUID | None, template_type: str, ...) -> Template
   ```

9. **`backend/app/db/repositories/config_repo.py`**
   ```python
   class ConfigRepository(BaseRepository[Config]):
       async def get_value(key: str) -> Any | None
       async def set_value(key: str, value: Any, description: str | None) -> Config
   ```

**Implementation Requirements:**
- All methods are async
- Use dependency injection (accept AsyncSession in constructor)
- Full type hints (use typing.List, typing.Optional, UUID, datetime)
- Docstrings for all public methods (Google style)
- Proper error handling (raise specific exceptions)
- Use SQLAlchemy select() queries (not query() - deprecated)

**Testing:**
- Verify all repositories can be instantiated
- Test that methods have correct signatures

**Acceptance Criteria:**
- [ ] All 8 repositories implemented with key methods
- [ ] All methods are async
- [ ] Repositories use dependency injection (accept AsyncSession)
- [ ] Type hints are used throughout
- [ ] Docstrings for public methods

**Commit Message:** `feat(db): implement repository layer for all 8 models`

---

### Stage 2.6: Unit Tests for Repositories

**Objective:** Comprehensive test coverage for all repositories.

**Files to create/update:**

1. **`backend/tests/conftest.py`**
   ```python
   # Test database fixtures
   @pytest.fixture(scope="session")
   async def test_engine():
       """Create test database engine"""
       # Use separate test database

   @pytest.fixture
   async def db_session():
       """Create test database session"""
       # Setup: create tables
       # Yield session
       # Teardown: rollback and drop tables

   @pytest.fixture
   async def test_user(db_session):
       """Create test user fixture"""

   @pytest.fixture
   async def test_conversation(db_session, test_user):
       """Create test conversation fixture"""
   ```

2. **`backend/tests/unit/test_user_repo.py`**
   - Test: create user
   - Test: get user by ID
   - Test: get user by email
   - Test: get non-existent user returns None
   - Test: duplicate email raises error

3. **`backend/tests/unit/test_session_repo.py`**
   - Test: create session
   - Test: get session by token
   - Test: delete session
   - Test: delete expired sessions
   - Test: expired session detection

4. **`backend/tests/unit/test_conversation_repo.py`**
   - Test: create conversation
   - Test: get conversation by ID
   - Test: list conversations by user
   - Test: delete conversation (cascade to messages)
   - Test: pagination works

5. **`backend/tests/unit/test_message_repo.py`**
   - Test: create message
   - Test: list messages by conversation
   - Test: get last N messages (ordered correctly)
   - Test: message with metadata (JSONB)

**Test Requirements:**
- Use separate test database (not dev database)
- Use fixtures for common test data
- Test edge cases (not found, duplicates, empty results)
- Test cascading deletes
- Test JSONB columns
- Test pagination and ordering
- Mock external dependencies if any
- All tests must pass
- Coverage >80% for app/db/repositories/

**Running Tests:**
```bash
# Run all repository tests
pytest tests/unit/test_*_repo.py -v

# Check coverage
pytest tests/unit/test_*_repo.py --cov=app/db/repositories --cov-report=term-missing

# Coverage report should show >80%
```

**Acceptance Criteria:**
- [ ] All repository tests pass
- [ ] Test database is created and cleaned up properly
- [ ] Coverage meets >80% requirement
- [ ] Edge cases covered (not found, duplicates, cascades)
- [ ] JSONB columns tested
- [ ] Pagination tested

**Commit Message:** `test(db): add comprehensive unit tests for repository layer`

---

## Final Steps

### Update HANDOFF.md

Mark the following checkboxes as complete:
- [x] Stage 2.1: SQLAlchemy Configuration
- [x] Stage 2.2: Alembic Setup
- [x] Stage 2.3: Define Database Models
- [x] Stage 2.4: Create Initial Migration
- [x] Stage 2.5: Create Repository Layer
- [x] Stage 2.6: Unit Tests for Repositories

**Commit Message:** `docs: update HANDOFF.md - Phase 2 complete`

---

### Create Pull Request

```bash
# Create feature branch first
git checkout -b feat/phase-2-database-setup

# After all commits
gh pr create \
  --title "feat: Phase 2 - Database Setup & Migrations" \
  --body "Implements complete database layer with SQLAlchemy, Alembic migrations, and repository pattern.

## Changes
- SQLAlchemy async configuration with connection pooling
- Alembic setup for migrations
- All 8 database models (User, Session, Conversation, Message, Transcript, Chunk, Template, Config)
- Initial migration with triggers
- Repository layer for all models
- Comprehensive unit tests (>80% coverage)

## Acceptance Criteria Met
✅ All 8 tables created successfully
✅ Indexes and constraints present
✅ Migration reversible
✅ All repository tests pass
✅ Coverage >80%

## Testing
\`\`\`bash
# Run all tests
pytest tests/unit/test_*_repo.py -v

# Check coverage
pytest --cov=app/db/repositories --cov-report=term-missing
\`\`\`

Closes stages 2.1-2.6 from HANDOFF.md" \
  --base main
```

---

## Acceptance Criteria Summary

**Stage 2.1:**
- [x] Database connection works with async engine
- [x] Connection pool configured (size=20, max_overflow=10)
- [x] get_db() dependency works

**Stage 2.2:**
- [x] Alembic configured for async operations
- [x] alembic check runs without errors

**Stage 2.3:**
- [x] All 8 models match DATABASE_SCHEMA.md exactly
- [x] All relationships and indexes defined
- [x] All constraints present

**Stage 2.4:**
- [x] Migration creates all tables successfully
- [x] Migration is reversible
- [x] Trigger for conversation.updated_at works

**Stage 2.5:**
- [x] All 8 repositories implemented with key methods
- [x] Async methods throughout
- [x] Type hints and docstrings

**Stage 2.6:**
- [x] Repository tests pass with >80% coverage
- [x] Test database isolated from dev database
- [x] Edge cases tested

---

## Estimated Time

- Stage 2.1: 30 minutes
- Stage 2.2: 30 minutes
- Stage 2.3: 1.5 hours
- Stage 2.4: 45 minutes
- Stage 2.5: 2 hours
- Stage 2.6: 2 hours

**Total:** ~7-8 hours (assuming no major blockers)

---

## Dependencies & References

**Documentation:**
- DATABASE_SCHEMA.md - Complete schema reference
- HANDOFF.md - Master checklist
- DEVELOPMENT_RULES.md - Workflow rules

**Tools:**
- SQLAlchemy 2.0 docs: https://docs.sqlalchemy.org/en/20/
- Alembic docs: https://alembic.sqlalchemy.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/

**Database:**
- PostgreSQL port: 5435 (docker-compose)
- Database name: youtube_talker
- Connection string in: backend/app/config.py

---

**Plan Status:** Ready for Implementation
**Next Action:** Create feature branch and start Stage 2.1
