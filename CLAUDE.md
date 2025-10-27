# YoutubeTalker MVP - Development Guide

**Auto-loaded reference for Claude Code agents**

---

## 🎯 Core Rules (Must Follow)

1. **Work on ONE checkbox at a time** from HANDOFF.md (see DEVELOPMENT_RULES.md)
2. **Write tests first** (TDD) - 80% coverage minimum
3. **Never push to main** - Always PR via `gh` CLI
4. **Use latest stable libraries** - Check compatibility before upgrading
5. **Use research-synthesizer agent** for external API docs (e.g., SUPADATA)

---

## 📂 Key Files (Read These First)

- **HANDOFF.md** - Backend dev checklist (work from here)
- **HANDOFF_FRONT.md** - Frontend dev checklist
- **INIT_PROMPT.md** - Quick context for resuming work
- **PRD.md** - Product requirements and features
- **DATABASE_SCHEMA.md** - Full DB schema with SQL
- **PROJECT_STRUCTURE.md** - Folder structure guide
- **DOCKER_STRATEGY.md** - Container architecture
- **DEVELOPMENT_RULES.md** - Workflow rules (incremental, TDD, PR workflow)

---

## 🔧 Tech Stack

**Backend:** FastAPI (async) + PostgreSQL + Qdrant + LangChain/LangGraph + OpenRouter API
**Frontend:** Astro + TailwindCSS + Nanostores + WebSockets
**Containers:** Docker Compose (PostgreSQL, Qdrant, Backend, Frontend in dev)

---

## 💻 Common Commands

Start system by ./dev.sh

### Backend
```bash
# Start environment
docker compose up -d                    # Start PostgreSQL + Qdrant
source .venv/bin/activate              # Activate venv
uvicorn app.main:app --reload          # Run API server

# Testing & Quality
pytest tests/ --cov=app                # Run tests with coverage
ruff check app/                        # Lint
black app/                             # Format

# Database
alembic revision --autogenerate -m "msg"  # Create migration
alembic upgrade head                      # Apply migrations
python scripts/seed_database.py           # Seed test data
```

### Frontend
```bash
npm install                            # Install dependencies
npm run dev                            # Dev server (localhost:4321)
npm run build                          # Production build
npm run lint && npm run format         # Lint and format
```

### Docker
```bash
docker compose up -d                   # Start all services
docker compose down                    # Stop all services
docker compose logs -f backend         # View logs
docker compose up -d --build           # Rebuild containers
```

---

## 🔀 Git Workflow (gh CLI Required)

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "feat: description"

# Push and create PR
gh pr create --title "feat: my feature" \
  --body "Description" --base main

# Check PR status
gh pr status
gh pr checks

# Merge after approval
gh pr merge --squash
```

**Commit types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## 🧪 Testing Rules

- **Structure:** `tests/unit/`, `tests/integration/`, `tests/e2e/`
- **Naming:** `test_<scenario>_<expected_result>`
- **Coverage:** Minimum 80% required
- **Run before PR:** `pytest tests/ --cov=app`

---

## 🎨 Code Style

### Python
- **Formatter:** `black` (line length: 100)
- **Linter:** `ruff`
- **Type hints:** Required for all functions
- **Docstrings:** Google style for public functions
- **Async:** Use `async`/`await` consistently (never `time.sleep()`)

### TypeScript
- **Formatter:** Prettier
- **Linter:** ESLint
- **Types:** Explicit (avoid `any`)
- **Imports:** Destructure when possible

---

## 🏗️ Architecture Patterns

### Backend
- **Layered:** API routes → Services → Repositories → Models
- **Dependency Injection:** Pass dependencies via constructors/args
- **Repository Pattern:** All DB access through repositories
- **Async:** Use `asyncio.gather()` for parallel operations
- **Validation:** Pydantic for all input (max 2000 chars for messages)

### RAG Flow
```
User Query → Router Node (classify intent)
  ├─ Chitchat → Simple LLM response
  ├─ Q&A → Retrieve (top-12) → Grade (LLM binary) → Generate
  └─ LinkedIn → Retrieve → Grade → Template render → Generate
```

**Key Config:**
- Chunks: 700 tokens, 20% overlap (tiktoken)
- Context: Last 10 messages
- Grading: Binary (relevant/not_relevant)

---

## 🔒 Security Essentials

- **Secrets:** Never commit (use `.env`, add to `.gitignore`)
- **Passwords:** Bcrypt hash (cost ≥ 12)
- **Sessions:** Hash tokens (SHA-256) before storing, 7-day expiry
- **Validation:** Pydantic for backend, DOMPurify for frontend HTML
- **SQL:** Use SQLAlchemy ORM only (no string interpolation)
- **Ownership:** Always verify `user_id` matches resource owner

---

## 🚨 Common Pitfalls (Don't Do This)

1. **Don't mix sync/async** - Use `async`/`await` consistently (never `time.sleep()`)
2. **Don't hardcode config** - Use `.env` or `config` table
3. **Don't trust user input** - Always validate with Pydantic
4. **Don't ignore errors** - Handle exceptions, log with context
5. **Don't skip tests** - Write as you code (80% coverage minimum)
6. **Don't commit to main** - Always branch + PR via `gh` CLI
7. **Don't expose secrets** - Never log passwords, tokens, API keys

---

## 📝 Before Committing Checklist

- [ ] Tests pass (`pytest tests/ --cov=app`)
- [ ] Linter passes (`ruff check app/`)
- [ ] Formatted (`black app/`)
- [ ] Type hints added
- [ ] Docstrings for public functions
- [ ] No secrets in code
- [ ] HANDOFF.md checkbox updated
- [ ] PR created via `gh pr create`

---

## 🔍 External APIs

**Use research-synthesizer agent** before implementing:
```
"Use research-synthesizer agent to find SUPADATA API documentation
and summarize the transcription endpoint, rate limits, and error handling."
```

**Always add:**
- Retry logic (`tenacity` library)
- Timeouts (30s for LLM, 10s for other APIs)
- Error handling

---

## 🐛 Troubleshooting Quick Fixes

**Database connection fails:**
- Check: `docker compose ps` (is PostgreSQL running?)
- Check: `.env` DATABASE_URL matches compose ports

**Qdrant not accessible:**
- Check: `http://localhost:6333/dashboard`
- Check: QDRANT_URL in `.env`

**Tests failing:**
- Check: Test DB is separate from dev DB
- Run: `alembic upgrade head` in test environment

**Import errors:**
- Activate venv: `source .venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

---

## 📚 Detailed Docs (Read When Needed)

- **HANDOFF.md** - 100+ checkboxes for backend dev (granular tasks)
- **PRD.md** - Full product requirements, user stories, success metrics
- **DATABASE_SCHEMA.md** - Complete SQL schemas, relationships, queries
- **PROJECT_STRUCTURE.md** - File-by-file descriptions, naming conventions
- **DOCKER_STRATEGY.md** - Container architecture, local + prod setup
- **DEVELOPMENT_RULES.md** - Workflow rules (TDD, incremental, PR process)

---

**Last Updated:** 2025-10-17
**Review:** Quarterly or when major changes occur
