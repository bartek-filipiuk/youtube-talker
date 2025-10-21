# Backend Development Handoff
## YoutubeTalker MVP

**Version:** 1.0
**Last Updated:** 2025-10-17
**Target:** Backend (FastAPI + RAG)

---

## How to Use This Document

This is the **master development checklist** for backend implementation. Follow these rules:

1. **Work on ONE checkbox at a time** (see DEVELOPMENT_RULES.md)
2. **Each checkbox = one reviewable unit of work** (usually 1 PR, sometimes grouped)
3. **Check the box** when completed and tested
4. **Do not skip ahead** - phases have dependencies
5. **Write tests** before or during implementation (TDD approach)
6. **Request review** before moving to next checkbox

**Progress Tracking:**
- [ ] = Not started
- [x] = Completed and reviewed

**Dependencies:**
- Some tasks require previous tasks to be completed
- Dependencies are noted in task descriptions

---

## Phase 1: Project Setup & Infrastructure

**Goal:** Set up development environment, tools, and basic project structure

**Testing Note:** Stages 1.1-1.2 are infrastructure setup (no automated tests needed). Stages 1.3-1.4 require unit tests for application code (endpoints, config, middleware). Follow TDD where practical - test only what's worth testing, but maintain >80% coverage.

### 1.1 Initialize Backend Project

- [x] Create `backend/` directory structure (see PROJECT_STRUCTURE.md)
- [x] Initialize Python project with `requirements.txt` or `pyproject.toml`
- [x] Set up virtual environment (`.venv`)
- [x] Install core dependencies:
  - FastAPI, uvicorn
  - SQLAlchemy, asyncpg, alembic
  - Pydantic, pydantic-settings
  - pytest, pytest-asyncio
- [x] Create `.env.example` file with all required variables
- [x] Create `.gitignore` (include `.env`, `__pycache__`, `.venv`, `.pytest_cache`)
- [x] Create `backend/README.md` with setup instructions

**Acceptance Criteria:**
- `pip install -r requirements.txt` works without errors
- Virtual environment activates successfully
- Project structure matches PROJECT_STRUCTURE.md

**Test:** Run `python --version` and `pip list` to verify installation

---

### 1.2 Docker Compose for Local Services

- [x] Create `docker-compose.yml` in project root
- [x] Add PostgreSQL service (port 5432)
- [x] Add Qdrant service (ports 6333, 6334)
- [x] Configure volumes for data persistence
- [x] Test: `docker compose up -d` starts both services
- [x] Test: Connect to PostgreSQL using `psql` or database client
- [x] Test: Access Qdrant dashboard at `http://localhost:6333/dashboard`

**Acceptance Criteria:**
- Both services start without errors
- Services persist data after container restart
- Connection strings in `.env.example` match docker compose ports

**Note:** See DOCKER_STRATEGY.md for complete Docker architecture

---

### 1.3 FastAPI Application Skeleton

- [x] Create `app/main.py` with basic FastAPI app
- [x] Create `app/config.py` with Pydantic Settings
- [x] Load configuration from `.env` file
- [x] Create `app/dependencies.py` for dependency injection setup
- [x] Add basic `/` root endpoint (returns `{"status": "ok"}`)
- [x] Add `/health` endpoint (returns environment info)
- [x] Write tests for endpoints (`tests/unit/test_main.py`)
- [x] Write tests for config loading (`tests/unit/test_config.py`)
- [x] Test: Run `uvicorn app.main:app --reload`
- [x] Test: Access `http://localhost:8000` and see response
- [x] Test: Access `http://localhost:8000/docs` for Swagger UI
- [x] Test: Run `pytest tests/` - all tests pass

**Acceptance Criteria:**
- FastAPI app starts without errors
- Swagger documentation is accessible
- Configuration loads from `.env` file
- All unit tests pass
- Test coverage > 80% for `app/main.py` and `app/config.py`

---

### 1.4 CORS and Middleware Setup

- [x] Add CORS middleware in `app/core/middleware.py`
- [x] Configure allowed origins from env wironment variable
- [x] Add request logging middleware
- [x] Add exception handling middleware
- [x] Apply middleware in `main.py`
- [x] Write tests for middleware (`tests/unit/test_middleware.py`)
- [x] Test: Frontend origin (e.g., `http://localhost:4321`) is allowed
- [x] Test: Run `pytest tests/` - all tests pass

**Acceptance Criteria:**
- CORS headers present in responses
- Requests are logged to console
- Unhandled exceptions return proper JSON responses
- All unit tests pass
- Test coverage > 80% for `app/core/middleware.py`

---

## Phase 2: Database Setup & Migrations

**Goal:** Set up PostgreSQL with SQLAlchemy and create all tables

**Dependencies:** Phase 1.2 completed (PostgreSQL running)

### 2.1 SQLAlchemy Configuration

- [x] Create `app/db/session.py` with async engine
- [x] Configure connection pool (size=20, max_overflow=10)
- [x] Create `get_db()` dependency for session management
- [x] Create `app/db/models.py` with Base declarative class
- [x] Test database connection with a simple query

**Acceptance Criteria:**
- Database connection succeeds
- Connection pooling is configured
- `get_db()` dependency works in routes

---

### 2.2 Alembic Setup

- [x] Initialize Alembic: `alembic init alembic`
- [x] Configure `alembic/env.py` to use async engine
- [x] Configure `alembic.ini` with database URL from environment
- [x] Test: `alembic check` runs without errors

**Acceptance Criteria:**
- Alembic is configured for async SQLAlchemy
- Migrations can be generated and applied

---

### 2.3 Define Database Models

- [x] Create `User` model in `app/db/models.py`
- [x] Create `Session` model
- [x] Create `Conversation` model
- [x] Create `Message` model
- [x] Create `Transcript` model
- [x] Create `Chunk` model
- [x] Create `Template` model
- [x] Create `Config` model
- [x] Add relationships between models (ForeignKey, relationships)
- [x] Add indexes (see DATABASE_SCHEMA.md)

**Acceptance Criteria:**
- All models match DATABASE_SCHEMA.md
- Indexes are defined
- Relationships are correctly configured

**MVP Note:** Template model validation is handled in application layer (Pydantic) rather than database CHECK constraints. This allows flexible addition of new content types post-MVP (twitter, blog, email) without requiring database migrations. For MVP, only 'linkedin' template type is needed.

**Reference:** See DATABASE_SCHEMA.md for complete schema

---

### 2.4 Create Initial Migration

- [x] Generate migration: `alembic revision --autogenerate -m "Initial schema"`
- [x] Review generated migration file
- [x] Add any custom SQL (triggers, constraints) if needed
- [x] Apply migration: `alembic upgrade head`
- [x] Verify: Connect to database and check tables exist
- [x] Test: `alembic downgrade -1` and `alembic upgrade head` (reversibility)

**Acceptance Criteria:**
- All 8 tables created successfully
- Indexes and constraints are present
- Migration is reversible

---

### 2.5 Create Repository Layer

- [x] Create `app/db/repositories/base.py` with BaseRepository class
- [x] Create `app/db/repositories/user_repo.py`
  - `get_by_id(user_id)`
  - `get_by_email(email)`
  - `create(email, password_hash)`
- [x] Create `app/db/repositories/session_repo.py`
  - `create(user_id, token_hash, expires_at)`
  - `get_by_token(token_hash)`
  - `delete(session_id)`
  - `delete_expired()`
- [x] Create `app/db/repositories/conversation_repo.py`
- [x] Create `app/db/repositories/message_repo.py`
- [x] Create `app/db/repositories/transcript_repo.py`
- [x] Create `app/db/repositories/chunk_repo.py`
- [x] Create `app/db/repositories/template_repo.py`
- [x] Create `app/db/repositories/config_repo.py`

**Acceptance Criteria:**
- Each repository has async methods
- Repositories use dependency injection (accept `AsyncSession`)
- Type hints are used throughout

---

### 2.6 Unit Tests for Repositories

- [x] Create `tests/conftest.py` with database fixtures
- [x] Set up test database (separate from dev database)
- [x] Write tests for `UserRepository` (CRUD operations)
- [x] Write tests for `SessionRepository`
- [x] Write tests for at least 2 other repositories
- [x] Test: `pytest tests/unit/test_*_repo.py` passes
- [x] Verify: Test coverage > 80% for repositories

**Acceptance Criteria:**
- All repository tests pass
- Test database is created and cleaned up properly
- Coverage meets requirements

---

## Phase 3: Authentication & Session Management

**Goal:** Implement user registration, login, and session-based auth

**Dependencies:** Phase 2 completed (database models and repos)

### 3.1 Security Utilities

- [x] Create `app/core/security.py`
- [x] Implement `hash_password(password: str) -> str` using bcrypt
- [x] Implement `verify_password(plain: str, hashed: str) -> bool`
- [x] Implement `generate_session_token() -> str` (random 32-byte hex)
- [x] Implement `hash_token(token: str) -> str` (SHA-256)
- [x] Unit test all security functions

**Acceptance Criteria:**
- Password hashing uses bcrypt with proper salt
- Token generation is cryptographically secure
- All security functions have unit tests

---

### 3.2 Authentication Service

- [x] Create `app/services/auth_service.py`
- [x] Implement `register_user(email, password) -> User`
  - Validate email format
  - Check if email already exists
  - Hash password
  - Create user via UserRepository
- [x] Implement `login(email, password) -> dict`
  - Verify credentials
  - Create session (7-day expiry)
  - Return token and user info
- [x] Implement `logout(token) -> None`
  - Delete session from database
- [x] Implement `validate_session(token) -> User`
  - Check token hash in sessions table
  - Check expiry
  - Return user or raise exception
- [x] Unit test all service methods

**Acceptance Criteria:**
- Registration validates input and creates user
- Login returns valid session token
- Session validation works correctly
- Expired sessions are rejected
- All methods have unit tests

---

### 3.3 Pydantic Schemas for Auth

- [x] Create `app/schemas/auth.py`
- [x] Define `RegisterRequest(email, password)`
- [x] Define `LoginRequest(email, password)`
- [x] Define `TokenResponse(token, user_id, email)`
- [x] Define `UserResponse(id, email, created_at)`
- [x] Add validation (email format, password min length 8)

**Acceptance Criteria:**
- All schemas have proper validation
- Schemas match API requirements

---

### 3.4 Auth API Endpoints

- [x] Create `app/api/routes/auth.py`
- [x] Implement `POST /api/auth/register`
  - Accept RegisterRequest
  - Call auth_service.register_user()
  - Return 201 with user data
  - Handle duplicate email (409 Conflict)
  - **Add rate limiting: 5 attempts/minute** (SlowAPI)
- [x] Implement `POST /api/auth/login`
  - Accept LoginRequest
  - Call auth_service.login()
  - Return TokenResponse
  - Handle invalid credentials (401 Unauthorized)
  - **Add rate limiting: 5 attempts/minute** (SlowAPI)
- [x] Implement `POST /api/auth/logout`
  - Accept token in header
  - Call auth_service.logout()
  - Return 204 No Content
- [x] Implement `GET /api/auth/me`
  - Require valid session token
  - Return current user info
- [x] Add router to `main.py`
- [x] Configure SlowAPI in `main.py` if not already present

**Acceptance Criteria:**
- All endpoints return correct status codes
- Rate limiting works (5/min on register and login)
- Error responses include meaningful messages
- Swagger docs are updated

---

### 3.5 Authentication Dependency

- [x] Create `get_current_user()` dependency in `app/dependencies.py`
- [x] Extract token from `Authorization: Bearer <token>` header
- [x] Call `auth_service.validate_session(token)`
- [x] Return user or raise 401 exception
- [x] Test with a protected endpoint

**Acceptance Criteria:**
- Dependency works with FastAPI `Depends()`
- Invalid/missing tokens return 401
- Valid tokens return user object

---

### 3.6 Integration Tests for Auth

- [x] Create `tests/integration/test_auth_endpoints.py`
- [x] Test registration flow (success and duplicate email)
- [x] Test login flow (success and invalid credentials)
- [x] Test logout flow
- [x] Test protected endpoint with valid/invalid tokens
- [x] Test session expiry (mock time if needed)
- [x] Verify all tests pass

**Acceptance Criteria:**
- Full auth flow tested end-to-end
- Edge cases covered (expired sessions, invalid tokens)
- Test coverage > 80%

---

## Phase 4: Transcript Ingestion Pipeline

**Goal:** Implement YouTube URL � Transcription � Chunking � Embedding � Qdrant

**Dependencies:** Phase 3 completed (auth working)

**See:** `stages/STAGE_4_PLAN.md` for detailed implementation plan with PR strategy
**See:** `LANGCHAIN_RETRY.md` for retry mechanism decisions (use tenacity for external APIs)

### 4.1 SUPADATA API Client (PR #5 - Partial)

- [x] Create `app/services/transcript_service.py`
- [x] Implement `fetch_transcript(youtube_url: str) -> dict`
  - Call SUPADATA API with YouTube URL
  - Parse response (transcript text + metadata)
  - Handle API errors (rate limits, invalid URLs)
  - Return structured data
- [x] Add retry logic with exponential backoff (use `tenacity`)
- [x] Unit test with mocked API responses

**Acceptance Criteria:**
- Successfully fetches transcript from SUPADATA
- Handles errors gracefully
- Retries on transient failures

**Note:** Full orchestration (ingest_transcript method) will be in PR #7

**Status:** ✅ Completed in PR #5 (merged)

---

### 4.2 Chunking Service (PR #5)

- [x] Create `app/services/chunking_service.py`
- [x] Implement `ChunkingService` class
  - Constructor: `chunk_size=700`, `overlap_percent=20`
  - Method: `chunk_text(text: str) -> List[dict]`
  - Use `tiktoken` for token counting
  - Implement sliding window with overlap
  - Enforce minimum chunk size (150 tokens)
- [x] Return list of dicts: `{"text": str, "token_count": int, "index": int}`
- [x] Unit test with various text lengths

**Acceptance Criteria:**
- Chunks are ~700 tokens with 20% overlap
- No chunks < 150 tokens (append to previous if needed)
- Chunk indices are sequential (0, 1, 2, ...)

**Status:** ✅ Completed in PR #5 (merged)

---

### 4.3 Embedding Service (PR #6)

- [x] Create `app/services/embedding_service.py`
- [x] Implement `EmbeddingService` class
  - Method: `generate_embeddings(texts: List[str]) -> List[List[float]]`
  - Use **OpenAI API directly** (not OpenRouter) for embeddings
  - Model: `text-embedding-3-small` (1024-dim)
  - Batch requests (max 100 texts per request)
- [x] Add retry logic for API failures (tenacity)
- [x] Unit tests with mocked API responses (7 tests, 100% coverage)
- [x] Update config: Split OpenRouter (LLM) and OpenAI (embeddings) settings

**Acceptance Criteria:**
- Returns 1024-dimensional vectors ✅
- Handles batching correctly ✅
- Retries on failures ✅
- Test coverage > 80% ✅

**Status:** ✅ Completed in PR #6 (open - awaiting review)

---

### 4.4 Qdrant Service (PR #6)

- [x] Create `app/services/qdrant_service.py`
- [x] Implement `QdrantService` class
  - Method: `create_collection()` - creates "youtube_chunks" collection
  - Method: `upsert_chunks(...)` - batch upsert with retry
  - Method: `search(query_vector, user_id, top_k=12)` - semantic search with filter
  - Method: `delete_chunks(chunk_ids: List[str])` - delete by IDs
  - Method: `health_check()` - verify connection
- [x] Use AsyncQdrantClient with proper error handling
- [x] Create payload indexes for `user_id` and `youtube_video_id`
- [x] Integration tests with local Qdrant instance (9 tests, 87% coverage)
- [x] Create `scripts/setup_qdrant.py` for collection setup
- [x] Create `scripts/test_vector_services.py` for end-to-end verification

**Acceptance Criteria:**
- Collection is created with correct vector size (1024) ✅
- Upsert and search work correctly ✅
- User ID filtering is applied in searches ✅
- Async operations work properly ✅
- Test coverage > 80% ✅

**Status:** ✅ Completed in PR #6 (open - awaiting review)

---

### 4.5 Transcript Ingestion Orchestration

- [ ] Create `ingest_transcript()` function in `transcript_service.py`
- [ ] Orchestrate full pipeline:
  1. Fetch transcript from SUPADATA
  2. Save transcript to PostgreSQL (TranscriptRepository)
  3. Chunk the transcript (ChunkingService)
  4. Generate embeddings (EmbeddingService)
  5. Save chunks to PostgreSQL (ChunkRepository)
  6. Upsert to Qdrant (QdrantService)
- [ ] Make entire process transactional (rollback on failure)
- [ ] Add detailed logging at each step
- [ ] Integration test with real YouTube URL (or mocked)

**Acceptance Criteria:**
- Full pipeline completes successfully
- Database and Qdrant are in sync
- Failures rollback properly

---

### 4.6 Transcript Ingestion API Endpoint

- [ ] Create `app/api/routes/transcripts.py`
- [ ] Create Pydantic schema `TranscriptIngestRequest(youtube_url: str)`
- [ ] Implement `POST /api/transcripts/ingest`
  - Require authentication
  - Accept YouTube URL
  - Check for duplicate (by youtube_video_id and user_id)
  - Call `ingest_transcript()` service
  - Return transcript metadata
- [ ] Handle errors (invalid URL, API failures, duplicates)
- [ ] Add router to `main.py`
- [ ] Integration test: Ingest a YouTube URL

**Acceptance Criteria:**
- Endpoint successfully ingests transcript
- Duplicate detection works
- Error messages are clear

---

### 4.7 Seed Database with Test Data

- [ ] Create `scripts/seed_database.py`
- [ ] Seed 1 test user (email/password)
- [ ] Seed 3-5 YouTube transcripts for that user
- [ ] Seed default LinkedIn template
- [ ] Seed config table values
- [ ] Test: Run script and verify data in database

**Acceptance Criteria:**
- Script runs without errors
- Database contains test data
- Qdrant contains vectors for seeded chunks

---

## Phase 5: RAG Foundation (Retrieval & Grading)

**Goal:** Build core RAG components (retrieval, grading, LLM client)

**Dependencies:** Phase 4 completed (data in Qdrant)

**See:** `LANGCHAIN_RETRY.md` for retry strategy (use LangGraph RetryPolicy for nodes in Phase 6)

### 5.1 OpenRouter LLM Client

- [ ] Create `app/rag/utils/llm_client.py`
- [ ] Implement `LLMClient` class
  - Method: `ainvoke(prompt: str) -> str` (async LLM call)
  - Use OpenRouter API with `anthropic/claude-haiku-4.5`
  - Add retry logic
  - Add timeout (30 seconds)
- [ ] Unit test with mocked API responses

**Acceptance Criteria:**
- LLM calls work asynchronously
- Retries on transient failures
- Returns text response

---

### 5.2 Jinja2 Prompt Templates

- [ ] Create `app/rag/prompts/` directory
- [ ] Create `query_router.jinja2` (intent classification)
  - Template variables: `user_query`, `context` (last 10 messages)
  - Output: "chitchat" | "qa" | "linkedin_post"
- [ ] Create `rag_qa.jinja2` (Q&A generation)
  - Variables: `user_query`, `context`, `chunks`
- [ ] Create `chunk_grader.jinja2` (relevance grading)
  - Variables: `user_query`, `chunk_text`
  - Output: "relevant" | "not_relevant"
- [ ] Create `linkedin_post_generate.jinja2`
  - Variables: `topic`, `chunks`, `template_content`
- [ ] Create `chitchat_flow.jinja2` (simple responses)

**Acceptance Criteria:**
- All templates render correctly with Jinja2
- Templates produce valid prompts

---

### 5.3 LangGraph State Definition

- [ ] Create `app/rag/utils/state.py`
- [ ] Define `GraphState` TypedDict with fields:
  - `user_query: str`
  - `conversation_history: List[dict]`
  - `intent: str`
  - `retrieved_chunks: List[dict]`
  - `graded_chunks: List[dict]`
  - `response: str`
  - `metadata: dict`
- [ ] Add type hints and docstrings

**Acceptance Criteria:**
- State schema is well-defined
- All fields have correct types

---

### 5.4 Retriever Node

- [ ] Create `app/rag/nodes/retriever.py`
- [ ] Implement `retrieve_chunks(state: GraphState) -> GraphState`
  - Extract user query from state
  - Generate embedding for query (EmbeddingService)
  - Search Qdrant (top-k=12, filter by user_id)
  - Fetch full chunk data from PostgreSQL (ChunkRepository)
  - Store in `state["retrieved_chunks"]`
- [ ] Unit test with mocked Qdrant and database

**Acceptance Criteria:**
- Retrieves 12 chunks from Qdrant
- Filters by user ID correctly
- Returns chunks with metadata

---

### 5.5 Grader Node

- [ ] Create `app/rag/nodes/grader.py`
- [ ] Implement `grade_chunks(state: GraphState) -> GraphState`
  - Loop through `state["retrieved_chunks"]`
  - For each chunk, render `chunk_grader.jinja2` prompt
  - Call LLM to classify as "relevant" or "not_relevant"
  - Keep only "relevant" chunks
  - Store in `state["graded_chunks"]`
- [ ] Unit test with mocked LLM responses

**Acceptance Criteria:**
- Grades each chunk with LLM
- Binary classification works
- Graded chunks list is updated

---

### 5.6 Unit Tests for RAG Nodes

- [ ] Write tests for `retriever.py`
  - Test with different query embeddings
  - Test user ID filtering
  - Test empty results
- [ ] Write tests for `grader.py`
  - Test with all chunks relevant
  - Test with no chunks relevant
  - Test with mixed relevance
- [ ] Verify all tests pass

**Acceptance Criteria:**
- All RAG node tests pass
- Edge cases are covered

---

## Phase 6: LangGraph Flows

**Goal:** Build complete LangGraph flows for QA, LinkedIn, and routing

**Dependencies:** Phase 5 completed (RAG nodes working)

### 6.1 Router Node (Intent Classification)

- [ ] Create `app/rag/nodes/router_node.py`
- [ ] Implement `classify_intent(state: GraphState) -> GraphState`
  - Render `query_router.jinja2` with user query and context
  - Call LLM to classify intent
  - Parse response to extract intent: "chitchat" | "qa" | "linkedin_post"
  - Store in `state["intent"]`
- [ ] Unit test with various query types

**Acceptance Criteria:**
- Correctly classifies chitchat queries
- Correctly identifies Q&A queries
- Correctly identifies LinkedIn post requests

---

### 6.2 Generator Node

- [ ] Create `app/rag/nodes/generator.py`
- [ ] Implement `generate_response(state: GraphState) -> GraphState`
  - Check intent
  - Render appropriate prompt (rag_qa.jinja2 or linkedin_post_generate.jinja2)
  - Call LLM with graded chunks as context
  - Store response in `state["response"]`
  - Store metadata (source chunk IDs, etc.)
- [ ] Unit test for both QA and LinkedIn generation

**Acceptance Criteria:**
- Generates answers for Q&A
- Generates formatted LinkedIn posts
- Includes metadata in state

---

### 6.3 Chitchat Flow

- [ ] Create `app/rag/graphs/flows/chitchat_flow.py`
- [ ] Implement simple flow (no RAG):
  - Render `chitchat_flow.jinja2` with user query
  - Call LLM
  - Return response
- [ ] No retrieval or grading needed

**Acceptance Criteria:**
- Handles chitchat queries (e.g., "how are you?")
- No database/Qdrant calls made

---

### 6.4 Q&A Flow

- [ ] Create `app/rag/graphs/flows/qa_flow.py`
- [ ] Build LangGraph with nodes:
  1. Retrieve chunks
  2. Grade chunks
  3. Generate response
- [ ] Connect nodes in sequence
- [ ] Return final state

**Acceptance Criteria:**
- Flow executes all steps
- Returns answer based on graded chunks

---

### 6.5 LinkedIn Flow

- [ ] Create `app/rag/graphs/flows/linkedin_flow.py`
- [ ] Extract topic from user query
- [ ] Build LangGraph with nodes:
  1. Retrieve chunks (for topic)
  2. Grade chunks
  3. Fetch LinkedIn template from database
  4. Generate post using template
- [ ] Return formatted LinkedIn post

**Acceptance Criteria:**
- Topic extraction works
- Post follows template format
- Uses only relevant chunks

---

### 6.6 Main Router Graph

- [ ] Create `app/rag/graphs/router.py`
- [ ] Build master graph:
  1. Classify intent (router_node)
  2. Conditional edges based on intent:
     - "chitchat" � chitchat_flow
     - "qa" � qa_flow
     - "linkedin_post" � linkedin_flow
- [ ] Compile graph
- [ ] Export `run_graph(user_query, user_id, conversation_id)` function

**Acceptance Criteria:**
- Router correctly directs to appropriate flow
- All flows execute successfully

---

### 6.7 Integration Tests for Flows

- [ ] Create `tests/integration/test_rag_flows.py`
- [ ] Test Q&A flow with real database and Qdrant
- [ ] Test LinkedIn flow end-to-end
- [ ] Test routing with different query types
- [ ] Verify response quality (manual check)

**Acceptance Criteria:**
- All flows complete without errors
- Responses are coherent and relevant

---

## Phase 7: WebSocket Chat API

**Goal:** Build real-time chat interface with WebSocket

**Dependencies:** Phase 6 completed (LangGraph flows working)

### 7.1 WebSocket Connection Manager

- [ ] Create `app/api/websocket/connection_manager.py`
- [ ] Implement `ConnectionManager` class
  - `connect(websocket, user_id, conversation_id)`
  - `disconnect(websocket)`
  - `send_message(websocket, data)`
  - Track active connections per conversation
- [ ] Add heartbeat/ping-pong mechanism (30-second interval)

**Acceptance Criteria:**
- Manages multiple WebSocket connections
- Heartbeat detects dead connections

---

### 7.2 WebSocket Chat Handler

- [ ] Create `app/api/websocket/chat_handler.py`
- [ ] Implement `websocket_endpoint(websocket, conversation_id)`
- [ ] On message received:
  1. Validate session token (from query param or initial message)
  2. Get user from token
  3. Verify user owns conversation
  4. Retrieve last 10 messages (MessageRepository)
  5. Run LangGraph with `run_graph(user_query, user_id, conversation_id, context)`
  6. Stream response chunks to client
  7. Save user message and assistant response to database
- [ ] Handle disconnections and errors

**Acceptance Criteria:**
- WebSocket connection established successfully
- Messages are streamed in real-time
- Conversation history is persisted

---

### 7.3 Message Streaming

- [ ] Implement streaming in chat_handler
- [ ] Send chunks as: `{"type": "chunk", "content": "..."}`
- [ ] Send final message: `{"type": "done", "metadata": {...}}`
- [ ] Handle LLM streaming (if OpenRouter supports it, else simulate)

**Acceptance Criteria:**
- Response is streamed token-by-token (or in small chunks)
- Client can display progressive response

---

### 7.4 Rate Limiting for WebSocket

- [ ] Configure SlowAPI for WebSocket messages
- [ ] Limit to 10 messages per minute per user
- [ ] Return error message if rate exceeded
- [ ] Test with rapid message sending

**Acceptance Criteria:**
- Rate limiting works for WebSocket
- Excess messages are rejected with clear error

---

### 7.5 Integration Test for WebSocket

- [ ] Create `tests/integration/test_chat_websocket.py`
- [ ] Test WebSocket connection
- [ ] Test sending a message and receiving response
- [ ] Test conversation context (last 10 messages)
- [ ] Test disconnection and reconnection
- [ ] Test rate limiting

**Acceptance Criteria:**
- Full WebSocket flow tested
- Edge cases handled

---

## Phase 8: Templates System

**Goal:** Implement template management for content generation

**Dependencies:** Phase 6 completed (LinkedIn flow exists)

### 8.1 Template Repository

- [ ] Verify `TemplateRepository` exists from Phase 2.5
- [ ] Implement `get_template(user_id, template_type) -> Template`
  - Returns user template if exists, else default template
- [ ] Implement `create_template(...)` for future use

**Acceptance Criteria:**
- Template retrieval with fallback works

---

### 8.2 Default LinkedIn Template

- [ ] Create `templates/linkedin_default.jinja2`
- [ ] Define template with variables:
  - `{{ topic }}`
  - `{{ introduction }}`
  - `{{ key_points }}` (loop)
  - `{{ conclusion }}`
  - `{{ hashtags }}`
- [ ] Seed database with this template (user_id=NULL, is_default=TRUE)

**Acceptance Criteria:**
- Template renders correctly with Jinja2
- Database contains default template

---

### 8.3 Template Service

- [ ] Create `app/services/template_service.py`
- [ ] Implement `get_template(user_id, template_type) -> str`
- [ ] Implement `render_template(template_content, variables) -> str`
  - Use Jinja2 to render
  - Handle missing variables gracefully

**Acceptance Criteria:**
- Template retrieval works
- Rendering produces valid output

---

### 8.4 Integrate Templates into LinkedIn Flow

- [ ] Update `linkedin_flow.py` to use TemplateService
- [ ] Extract template variables from LLM-generated content
- [ ] Render final post using template
- [ ] Test with different topics

**Acceptance Criteria:**
- LinkedIn posts use template format
- Variables are filled correctly

---

## Phase 9: Testing, Health Checks & Observability

**Goal:** Final polish, monitoring, and testing

### 9.1 Health Check Endpoints

- [ ] Create `app/api/routes/health.py`
- [ ] Implement `GET /api/health` - returns `{"status": "ok"}`
- [ ] Implement `GET /api/health/db` - checks PostgreSQL connection
- [ ] Implement `GET /api/health/qdrant` - checks Qdrant connection
- [ ] Add router to `main.py`
- [ ] Test all health endpoints

**Acceptance Criteria:**
- All health checks return proper status
- Failed checks return 503 Service Unavailable

---

### 9.2 Conversation Management API

- [ ] Create `app/api/routes/conversations.py`
- [ ] Implement `GET /api/conversations` - list user's conversations
- [ ] Implement `GET /api/conversations/{id}` - get conversation with messages
- [ ] Implement `POST /api/conversations` - create new conversation
- [ ] Implement `DELETE /api/conversations/{id}` - delete conversation
- [ ] Add authentication to all endpoints
- [ ] Integration tests for all endpoints

**Acceptance Criteria:**
- All CRUD operations work
- Only user's own conversations are accessible

---

### 9.3 Message Length Validation

- [ ] Add validation to chat message schema (max 2000 chars)
- [ ] Return 400 Bad Request if exceeded
- [ ] Test with long messages

**Acceptance Criteria:**
- Messages > 2000 chars are rejected

---

### 9.4 Configuration Management

- [ ] Ensure `config` table is seeded with:
  - `max_context_messages = 10`
  - `rag_top_k = 12`
  - `chunk_size = 700`
  - `chunk_overlap_percent = 20`
- [ ] Create `ConfigService` to read from database
- [ ] Use config values throughout codebase (not hardcoded)

**Acceptance Criteria:**
- Configuration is centralized
- Values can be changed without code changes

---

### 9.5 Error Handling & Logging

- [ ] Add structured logging (use `loguru` or Python `logging`)
- [ ] Log all API requests (method, path, status, duration)
- [ ] Log all LangGraph runs (query, intent, chunks used)
- [ ] Create custom exception classes in `app/core/errors.py`
- [ ] Add global exception handler in `main.py`
- [ ] Test error responses

**Acceptance Criteria:**
- All errors return JSON with meaningful messages
- Logs are structured (JSON format)

---

### 9.6 End-to-End Test

- [ ] Create `tests/e2e/test_user_journey.py`
- [ ] Test complete user journey:
  1. Register user
  2. Login
  3. Ingest YouTube transcript
  4. Create conversation
  5. Ask Q&A question via WebSocket
  6. Request LinkedIn post generation
  7. Logout
- [ ] Verify data in database and Qdrant

**Acceptance Criteria:**
- Full user journey completes successfully
- All features work together

---

### 9.7 LangSmith Integration (Optional)

- [ ] Add LangSmith API key to config
- [ ] Configure LangChain to send traces to LangSmith
- [ ] Test: Verify traces appear in LangSmith dashboard
- [ ] Tag traces with conversation_id and user_id

**Acceptance Criteria:**
- LangGraph runs are visible in LangSmith
- Traces include relevant metadata

**Note:** This is optional for MVP, can be deferred to post-MVP

---

### 9.8 Test Coverage Report

- [ ] Run `pytest --cov=app tests/` to generate coverage report
- [ ] Verify coverage > 80% overall
- [ ] Identify and test any uncovered critical paths
- [ ] Generate HTML coverage report for review

**Acceptance Criteria:**
- Test coverage meets 80% threshold
- All critical paths are tested

---

### 9.9 Documentation Review

- [ ] Review and update `backend/README.md`
- [ ] Document all API endpoints (Swagger is auto-generated)
- [ ] Add setup instructions for new developers
- [ ] Document environment variables
- [ ] Add troubleshooting section

**Acceptance Criteria:**
- Documentation is complete and accurate
- New developer can set up project from README

---

## Phase 10: Final Polish & Deployment Prep

**Goal:** Prepare for deployment and final review

### 10.1 Performance Testing

- [ ] Test with 50+ messages in a conversation
- [ ] Test with 100+ chunks in Qdrant
- [ ] Measure response times for:
  - RAG retrieval (< 500ms)
  - WebSocket first token (< 2s)
  - Message history load (< 200ms)
- [ ] Optimize slow queries if needed

**Acceptance Criteria:**
- Performance meets requirements
- No obvious bottlenecks

---

### 10.2 Security Review

- [ ] Verify all passwords are hashed
- [ ] Verify session tokens are hashed
- [ ] Check for SQL injection vulnerabilities (use SQLAlchemy ORM)
- [ ] Verify CORS configuration
- [ ] Check for exposed secrets in code
- [ ] Test rate limiting on all endpoints

**Acceptance Criteria:**
- No security vulnerabilities identified
- All best practices followed

---

### 10.3 Cleanup & Code Quality

- [ ] Run linter (e.g., `ruff` or `pylint`)
- [ ] Fix all linting errors
- [ ] Remove unused imports and dead code
- [ ] Ensure all functions have docstrings
- [ ] Format code with `black`

**Acceptance Criteria:**
- Code passes linting
- Code style is consistent

---

### 10.4 Create Seed Script for Production

- [ ] Create `scripts/seed_production.py`
- [ ] Seed only essential data:
  - Default templates
  - Config values
- [ ] NO test users or test data
- [ ] Document usage in README

**Acceptance Criteria:**
- Script is production-ready
- Only necessary data is seeded

---

### 10.5 Final Testing

- [ ] Run full test suite: `pytest tests/`
- [ ] Verify all tests pass
- [ ] Run end-to-end test manually
- [ ] Test with different YouTube videos
- [ ] Test error scenarios (API failures, invalid input)

**Acceptance Criteria:**
- All tests pass
- Manual testing confirms functionality

---

## Completion Checklist

Before marking backend as "complete", verify:

- [ ] All Phase 1-10 checkboxes are marked complete
- [ ] Test coverage > 80%
- [ ] All API endpoints documented
- [ ] README.md is up to date
- [ ] No critical bugs or errors
- [ ] Performance meets requirements
- [ ] Security review passed
- [ ] Code quality is high (linted, formatted, documented)

**MVP Backend Status:**  Complete (once all above checked)

---

## Notes & Decisions

**Use this section to track important decisions during development:**

- Decision 1: [Date] - Chose tiktoken over NLTK for chunking (better for embeddings)
- Decision 2: [Date] - Used server-side sessions instead of JWT (simpler for MVP)
- ...

---

**Document Version:**
- v1.0 (2025-10-17): Initial handoff checklist
