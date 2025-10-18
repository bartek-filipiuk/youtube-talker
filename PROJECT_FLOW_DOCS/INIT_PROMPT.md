# YoutubeTalker MVP - Coding Agent Handoff

**Last Updated:** 2025-10-17
**Current Phase:** See HANDOFF.md for progress

---

## Project Context

You're working on **YoutubeTalk er**, an AI-powered chat application that enables users to query knowledge from YouTube video transcripts using RAG (Retrieval-Augmented Generation) and generate content like LinkedIn posts.

**Core Concept:**
1. User uploads YouTube URLs � transcripts are generated, chunked, and embedded
2. User asks questions in chat � system retrieves relevant chunks, grades them, and generates answers
3. User requests LinkedIn post � system uses template-based generation with retrieved knowledge

**MVP Scope:** Single-user prototype with hardcoded configurations, expandable architecture for multi-user post-MVP.

---

## Tech Stack

### Backend (FastAPI)
- **Framework:** FastAPI (async) with WebSockets
- **Database:** PostgreSQL 15+ (SQLAlchemy 2.0 async, Alembic migrations)
- **Vector DB:** Qdrant (semantic search for RAG)
- **RAG:** LangChain + LangGraph (orchestration, flows, stateful agents)
- **LLM:** OpenRouter API (`anthropic/claude-haiku-4.5`)
- **Embeddings:** OpenRouter (`openai/text-embedding-3-small`, 1024-dim)
- **Transcription:** SUPADATA API (YouTube � transcript with metadata)
- **Auth:** Server-side sessions (7-day expiry), bcrypt password hashing
- **Rate Limiting:** SlowAPI
- **Testing:** pytest, pytest-asyncio (target: 80% coverage)

### Frontend (Astro)
- **Framework:** Astro (static + client-side JS)
- **Styling:** TailwindCSS
- **State:** Nanostores (lightweight reactive stores)
- **WebSocket:** Native WebSocket API
- **Markdown:** Marked + DOMPurify (render assistant messages)

### Infrastructure
- **Local Dev:** Docker Compose (PostgreSQL + Qdrant)
- **Config:** `.env` files (Pydantic Settings)
- **Observability:** LangSmith (late MVP, optional)

---

## Architecture Overview

### Data Flow
```
YouTube URL � SUPADATA API � Transcript (Postgres)
  �
Chunking (700 tokens, 20% overlap) � Chunks (Postgres)
  �
Embeddings (OpenRouter) � Qdrant (vectors + metadata)
  �
User Query � WebSocket � LangGraph Router
  �
Intent Classification � Chitchat | Q&A | LinkedIn Flow
  �
Retrieve (Qdrant) � Grade (LLM) � Generate (LLM) � Stream Response
```

### LangGraph Routing
**Router Node** � Classifies user intent (chitchat, qa, linkedin_post)
- **Chitchat Flow:** Simple LLM response (no RAG)
- **Q&A Flow:** Retrieve � Grade � Generate answer
- **LinkedIn Flow:** Retrieve � Grade � Template-based post generation

**Key RAG Components:**
- **Retriever:** Embed query � Qdrant search (top-k=12, filter by user_id)
- **Grader:** LLM binary classification (relevant/not relevant) per chunk
- **Generator:** LLM with graded chunks as context � final response

---

## Database Schema (PostgreSQL)

**Core Tables:**
- `users` - email, password_hash
- `sessions` - token_hash, expires_at (7 days)
- `conversations` - user_id, title
- `messages` - conversation_id, role, content, metadata
- `transcripts` - youtube_video_id, transcript_text, metadata
- `chunks` - transcript_id, user_id (denormalized), chunk_text, token_count, metadata
- `templates` - template_type (linkedin/twitter/blog), template_content (Jinja2), user_id (nullable for defaults)
- `config` - key-value store for settings (e.g., `max_context_messages: 10`)

**Qdrant Collection:** `youtube_chunks`
- Vector size: 1024
- Metadata: `{chunk_id, user_id, youtube_video_id, chunk_index}`
- Indexes: `user_id` (keyword), `youtube_video_id` (keyword)

**See:** `DATABASE_SCHEMA.md` for full SQL schema and relationships.

---

## Project Structure

```
backend/
  app/
    api/routes/          # REST endpoints (auth, conversations, transcripts, health)
    api/websocket/       # WebSocket chat handler
    core/                # Security, rate limiting, middleware
    db/                  # Models, repositories, session
    schemas/             # Pydantic request/response models
    services/            # Business logic (auth, transcription, chunking, embedding, qdrant)
    rag/
      graphs/flows/      # qa_flow, linkedin_flow, chitchat_flow
      nodes/             # retriever, grader, generator, router_node
      prompts/           # Jinja2 templates for LLM prompts
  templates/             # Content generation templates (linkedin_default.jinja2)
  tests/                 # unit/, integration/, e2e/

frontend/
  src/
    pages/               # Astro pages (index, chat, register, logout)
    components/          # ChatMessage, ChatInput, ConversationList
    layouts/             # Layout, ChatLayout
    lib/                 # api.ts, websocket.ts, auth.ts
    stores/              # auth.ts, chat.ts, conversations.ts
```

**See:** `PROJECT_STRUCTURE.md` for detailed file descriptions.

---

## Key Configuration

**Environment Variables (`.env`):**
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_talker
QDRANT_URL=http://localhost:6333
OPENROUTER_API_KEY=<your-key>
OPENROUTER_LLM_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
SUPADATA_API_KEY=<your-key>
SUPADATA_BASE_URL=https://api.supadata.ai
RAG_TOP_K=12
RAG_CONTEXT_MESSAGES=10
CHUNK_SIZE=700
CHUNK_OVERLAP_PERCENT=20
SESSION_EXPIRES_DAYS=7
```

---

## Development Workflow

**Incremental Development (See DEVELOPMENT_RULES.md):**
1. Work on **ONE checkbox** from HANDOFF.md at a time
2. Write tests **before/during** implementation (TDD)
3. Every change requires **code review** (PR workflow)
4. **Never push directly to main** - always use feature branches
5. Minimum **80% test coverage** required

**Current Progress:**
- Check `HANDOFF.md` for backend progress
- Check `HANDOFF_FRONT.md` for frontend progress
- Checkboxes show what's done and what's next

**Testing:**
```bash
# Backend
pytest tests/ --cov=app

# Frontend
npm test  # (if tests added)
```

---

## Common Tasks

### 1. Start Local Environment
```bash
# Start PostgreSQL + Qdrant + Backend + Frontend
docker compose up -d

# Or start services separately:
# Backend (if not using Docker)
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload

# Frontend (if not using Docker)
cd frontend
npm run dev
```

### 2. Database Migrations
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### 3. Seed Database
```bash
cd backend
python scripts/seed_database.py
```

### 4. Ingest YouTube Transcript (Manual for MVP)
```bash
curl -X POST http://localhost:8000/api/transcripts/ingest \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

### 5. Test WebSocket
Use Postman or browser console:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/chat/<conversation_id>?token=<token>');
ws.onmessage = (event) => console.log(event.data);
ws.send(JSON.stringify({ message: "What is in the videos?" }));
```

---

## Key Design Decisions

**Why these choices:**
1. **Server-side sessions** (not JWT): Simpler for MVP, easier revocation
2. **Denormalized user_id in chunks**: Faster Qdrant � DB lookups (no join with transcripts)
3. **Binary chunk grading**: Simpler than scoring, effective for MVP
4. **LangGraph over pure LangChain**: Enables stateful flows, easier to extend
5. **Astro over React/Next.js**: Lightweight, minimal JS, perfect for MVP
6. **Nanostores over Redux**: Minimal boilerplate, reactive, 1KB size
7. **700 token chunks with 20% overlap**: Balance between context and retrieval precision

---

## RAG Configuration Details

**Chunking Strategy:**
- Size: 700 tokens (using `tiktoken`)
- Overlap: 20% (140 tokens)
- Minimum size: 150 tokens (append to previous if smaller)
- Metadata: `{youtube_video_id, start_time, end_time}`

**Retrieval Parameters:**
- Top-k: 12 chunks
- Distance: Cosine similarity
- Filter: Always by `user_id` (data isolation)

**Grading:**
- LLM prompt: "Is this chunk relevant to the query?"
- Binary output: "relevant" | "not_relevant"
- Only relevant chunks passed to generator

**Context Window:**
- Last 10 messages from conversation
- Configurable via `config` table (`max_context_messages`)

---

## API Endpoints (Backend)

**Authentication:**
- `POST /api/auth/register` - Create user
- `POST /api/auth/login` - Get session token
- `POST /api/auth/logout` - Invalidate session
- `GET /api/auth/me` - Get current user

**Conversations:**
- `GET /api/conversations` - List user's conversations
- `GET /api/conversations/{id}` - Get conversation with messages
- `POST /api/conversations` - Create new conversation
- `DELETE /api/conversations/{id}` - Delete conversation

**Transcripts:**
- `POST /api/transcripts/ingest` - Ingest YouTube URL

**Chat:**
- `WS /api/chat/{conversation_id}` - WebSocket endpoint
  - Send: `{"message": "user query"}`
  - Receive: `{"type": "chunk", "content": "..."}` or `{"type": "done", "metadata": {...}}`

**Health:**
- `GET /api/health` - Overall status
- `GET /api/health/db` - PostgreSQL connection
- `GET /api/health/qdrant` - Qdrant connection

---

## Templates System

**Default LinkedIn Template** (hardcoded for MVP):
```jinja2
# {{ topic }}

{{ introduction }}

## Key Insights:
{% for point in key_points %}
- {{ point }}
{% endfor %}

{{ conclusion }}

#{{ hashtags | join(' #') }}
```

**Template Retrieval:**
- User-specific templates (future): `user_id` is not null
- Default template: `user_id` is null, `is_default=true`
- Fallback: If user has no template, use default

**Template Storage:**
- Table: `templates`
- Fields: `template_type`, `template_content`, `variables`, `is_default`, `user_id`

---

## Error Handling

**Backend:**
- Custom exceptions in `app/core/errors.py`
- Global exception handler in `main.py`
- All errors return JSON: `{"detail": "Error message"}`
- HTTP status codes: 400 (validation), 401 (auth), 404 (not found), 409 (conflict), 500 (server error)

**Frontend:**
- Display errors in UI (toasts or inline)
- Network errors: "Could not connect to server"
- Auth errors: Redirect to login
- Validation errors: Show under form fields

---

## Testing Strategy

**Backend:**
- **Unit tests:** Services, repositories, RAG nodes (mock external APIs)
- **Integration tests:** API endpoints (with test database)
- **E2E test:** Full user journey (register � ingest � chat � logout)
- **Coverage:** > 80% overall

**Frontend:**
- Manual testing (browser)
- E2E manual test: Full user flow
- Future: Playwright/Cypress for automated tests

---

## What to Work on Next

**Check the HANDOFF.md file** - find the first unchecked `[ ]` checkbox and work on that.

**Typical flow:**
1. Read checkbox description
2. Check dependencies (some tasks require previous tasks)
3. Write tests (TDD approach)
4. Implement feature
5. Run tests: `pytest tests/`
6. Run linter: `ruff check app/` or `black app/`
7. Commit changes to feature branch
8. Create PR for review
9. Mark checkbox as `[x]` after review

**Current development phase should be indicated by checkboxes in HANDOFF.md.**

---

## Troubleshooting

**Database connection fails:**
- Check `docker compose ps` - is PostgreSQL running?
- Check `.env` DATABASE_URL matches docker compose port

**Qdrant connection fails:**
- Check `http://localhost:6333/dashboard` is accessible
- Verify QDRANT_URL in `.env`

**WebSocket not connecting:**
- Check backend is running: `http://localhost:8000/docs`
- Verify session token is valid
- Check browser console for errors

**Tests failing:**
- Ensure test database is separate from dev database
- Run `alembic upgrade head` in test environment
- Check fixtures in `tests/conftest.py`

**Import errors:**
- Activate virtual environment: `source .venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

---

## Quick Reference Links

**Detailed Documentation:**
- **PRD.md** - Product requirements, user stories, success metrics
- **DATABASE_SCHEMA.md** - Complete SQL schemas, table relationships, example queries
- **PROJECT_STRUCTURE.md** - Full folder structure, file descriptions, naming conventions
- **HANDOFF.md** - Backend development checklist (work on this for backend)
- **HANDOFF_FRONT.md** - Frontend development checklist (work on this for frontend)
- **DEVELOPMENT_RULES.md** - Workflow rules, TDD, PR requirements

**External Docs:**
- LangChain: https://python.langchain.com/
- LangGraph: https://langchain-ai.github.io/langgraph/
- Qdrant: https://qdrant.tech/documentation/
- FastAPI: https://fastapi.tiangolo.com/
- Astro: https://astro.build/

---

## Notes for Continuity

**If development is paused and resumed later:**
1. Read this file (INIT_PROMPT.md) to get context
2. Check HANDOFF.md to see current progress
3. Review recent commits/PRs to understand what was last completed
4. Run local environment (docker compose, backend, frontend)
5. Run tests to ensure everything still works
6. Continue from next unchecked checkbox

**Remember:**
- Always follow DEVELOPMENT_RULES.md
- One checkbox at a time
- Tests before code
- Review before merge
- Update documentation as you go

---

**You're ready to code!** Check HANDOFF.md for your next task.
