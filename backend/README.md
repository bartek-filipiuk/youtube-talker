# YoutubeTalker Backend

FastAPI-based backend for AI-powered YouTube video Q&A and content generation using RAG (Retrieval-Augmented Generation).

## Tech Stack

- **Framework:** FastAPI (async)
- **Database:** PostgreSQL 15+ with SQLAlchemy 2.0 (async)
- **Vector DB:** Qdrant (semantic search)
- **RAG:** LangChain + LangGraph
- **LLM:** OpenRouter API (`anthropic/claude-haiku-4.5`)
- **Embeddings:** OpenRouter (`openai/text-embedding-3-small`, 1024-dim)
- **Transcription:** SUPADATA API

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (via Docker)
- Qdrant (via Docker)
- OpenRouter API key
- SUPADATA API key

## Quick Start

### 1. Clone and Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Required variables:**
- `OPENROUTER_API_KEY` - Get from https://openrouter.ai
- `SUPADATA_API_KEY` - Get from https://supadata.ai
- `DATABASE_URL` - PostgreSQL connection string
- `QDRANT_URL` - Qdrant server URL

### 3. Start Services

```bash
# Start PostgreSQL and Qdrant (from project root)
docker compose up -d

# Verify services are running
docker compose ps
```

### 4. Run Migrations

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head
```

### 5. Start Development Server

```bash
uvicorn app.main:app --reload

# Server will start at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

## Project Structure

```
backend/
├── app/
│   ├── api/           # API routes and WebSocket handlers
│   ├── core/          # Security, middleware, errors
│   ├── db/            # Database models and repositories
│   ├── schemas/       # Pydantic request/response models
│   ├── services/      # Business logic
│   └── rag/           # LangGraph flows and nodes
├── templates/         # Content generation templates
├── tests/             # Unit, integration, and e2e tests
├── scripts/           # Utility scripts
└── alembic/           # Database migrations
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ --cov=app

# Run specific test file
pytest tests/unit/test_auth_service.py

# Run with verbose output
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/ tests/

# Lint code
ruff check app/ tests/

# Type checking
mypy app/
```

### Database Operations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Seed Database

```bash
# Seed with test data (dev only)
python scripts/seed_database.py
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Create user
- `POST /api/auth/login` - Get session token
- `POST /api/auth/logout` - Invalidate session
- `GET /api/auth/me` - Get current user

### Conversations
- `GET /api/conversations` - List user's conversations
- `GET /api/conversations/{id}` - Get conversation with messages
- `POST /api/conversations` - Create new conversation
- `DELETE /api/conversations/{id}` - Delete conversation

### Transcripts
- `POST /api/transcripts/ingest` - Ingest YouTube URL

### Chat
- `WS /api/chat/{conversation_id}` - WebSocket endpoint

### Health
- `GET /api/health` - Overall status
- `GET /api/health/db` - PostgreSQL connection
- `GET /api/health/qdrant` - Qdrant connection

## Configuration

All configuration is managed via environment variables (see `.env.example`).

**Key settings:**
- `RAG_TOP_K=12` - Number of chunks to retrieve
- `RAG_CONTEXT_MESSAGES=10` - Messages to include in context
- `CHUNK_SIZE=700` - Token count per chunk
- `CHUNK_OVERLAP_PERCENT=20` - Overlap between chunks
- `SESSION_EXPIRES_DAYS=7` - Session lifetime

## RAG Pipeline

1. **Ingestion:** YouTube URL → SUPADATA → Transcript → Chunks → Embeddings → Qdrant
2. **Query:** User question → Embed → Retrieve (top-12) → Grade (LLM) → Generate (LLM)
3. **Flows:**
   - **Chitchat:** Simple LLM response (no RAG)
   - **Q&A:** Full RAG pipeline with grading
   - **LinkedIn:** RAG + template-based post generation

## Troubleshooting

### Database Connection Failed
```bash
# Check PostgreSQL is running
docker compose ps

# Check connection string in .env
echo $DATABASE_URL
```

### Qdrant Not Accessible
```bash
# Check Qdrant dashboard
open http://localhost:6333/dashboard

# Check logs
docker compose logs qdrant
```

### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -e ".[dev]"
```

### Tests Failing
```bash
# Ensure test database is separate
# Check DATABASE_URL in .env.test

# Run migrations for test DB
alembic upgrade head
```

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Write tests (TDD approach)
3. Implement feature
4. Run tests: `pytest tests/ --cov=app`
5. Format and lint: `black app/ && ruff check app/`
6. Commit changes: `git commit -m "feat: description"`
7. Push and create PR: `gh pr create`

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check `PROJECT_FLOW_DOCS/` for detailed documentation
- Review `HANDOFF.md` for development progress
- See `DEVELOPMENT_RULES.md` for workflow guidelines
