# Stage 4 Progress & Next Steps

**Last Updated:** 2025-10-21
**Current Status:** PR #6 Complete, Ready for PR #7

---

## ✅ Completed So Far

### PR #5: Foundational Services (MERGED)
**Branch:** `feature/phase4-foundational-services`
**Completed:** 2025-10-20

**What was built:**
- ✅ `TranscriptService.fetch_transcript()` - SUPADATA API client
  - Extracts YouTube video IDs from both URL formats
  - Calls SUPADATA API with retry logic (tenacity)
  - Returns transcript text + metadata
- ✅ `ChunkingService` - Token-based text chunking
  - Sliding window with 700 tokens, 20% overlap
  - Handles short transcripts (< 700 tokens) as single chunk
  - Merges tiny last chunks (< 150 tokens)
  - Uses tiktoken for accurate token counting
- ✅ `app/schemas/transcript.py` - Pydantic schemas
- ✅ Unit tests for both services (>80% coverage)

**Files Created:**
- `app/services/transcript_service.py` (fetch_transcript method only)
- `app/services/chunking_service.py`
- `app/schemas/transcript.py`
- `tests/unit/test_transcript_service.py`
- `tests/unit/test_chunking_service.py`

---

### PR #6: Vector Infrastructure (OPEN - Awaiting Review)
**Branch:** `feature/phase4-vector-infrastructure`
**Completed:** 2025-10-21
**PR:** https://github.com/bartek-filipiuk/youtube-talker/pull/6

**What was built:**
- ✅ `EmbeddingService` - OpenAI embeddings API client
  - Direct OpenAI API integration (NOT OpenRouter)
  - Model: `text-embedding-3-small` (1024-dim vectors)
  - Automatic batching (100 texts per request)
  - Retry logic with exponential backoff (tenacity)
  - Async operations using httpx
- ✅ `QdrantService` - Async vector database client
  - Collection: `youtube_chunks` (1024-dim, cosine distance)
  - Async operations (AsyncQdrantClient)
  - Batch upsert with retry logic
  - Semantic search with user ID filtering (data isolation)
  - Optional video ID filtering
  - Methods: create_collection, upsert_chunks, search, delete_chunks, health_check
- ✅ Configuration split: OpenRouter (LLM) vs OpenAI (embeddings)
- ✅ Setup scripts for Qdrant collection
- ✅ Comprehensive tests (16 total: 7 unit + 9 integration)
- ✅ End-to-end verification script

**Files Created:**
- `app/services/embedding_service.py` (105 lines)
- `app/services/qdrant_service.py` (220 lines)
- `scripts/setup_qdrant.py` (41 lines)
- `scripts/test_vector_services.py` (196 lines)
- `tests/unit/test_embedding_service.py` (232 lines)
- `tests/integration/test_qdrant_service.py` (365 lines)

**Files Modified:**
- `app/config.py` - Added OPENAI_API_KEY and OPENAI_EMBEDDING_MODEL
- `.env.example` - Updated with new OpenAI settings
- `tests/unit/test_config.py` - Updated test for new config structure

**Test Results:**
- Unit tests: 7/7 passing (EmbeddingService - 100% coverage)
- Integration tests: 9/9 passing (QdrantService - 87% coverage)
- Total: 16/16 tests passing ✅

**Verification:**
- ✅ Qdrant connection verified
- ✅ All CRUD operations tested
- ✅ User isolation confirmed
- ✅ Video filtering confirmed
- ✅ End-to-end integration test passed

**PR Status:**
- Codex review feedback addressed ✅
- All tests passing ✅
- Ready for merge

---

## 🔄 Next: PR #7 - Full Pipeline Integration

### Overview
**Goal:** Complete the transcript ingestion pipeline by orchestrating all services and exposing the API endpoint

**Estimated Effort:** 4-6 hours
**Estimated LOC:** 300-400

**Dependencies:** PR #5 ✅ MERGED, PR #6 ⏳ AWAITING REVIEW

---

### Stage 4.5: Transcript Ingestion Orchestration

**What to build:**

Add `ingest_transcript()` method to `TranscriptService` that orchestrates the full pipeline:

```python
async def ingest_transcript(
    self,
    youtube_url: str,
    user_id: str,
    db_session: AsyncSession
) -> Dict:
    """
    Full ingestion pipeline orchestration.

    Steps:
        1. Fetch transcript from SUPADATA (use existing fetch_transcript)
        2. Check for duplicate (by youtube_video_id + user_id)
        3. Save transcript to PostgreSQL (TranscriptRepository)
        4. Chunk the transcript text (ChunkingService)
        5. Generate embeddings for chunks (EmbeddingService)
        6. Save chunks to PostgreSQL (ChunkRepository)
        7. Upsert vectors to Qdrant (QdrantService)

    Returns:
        {
            "transcript_id": str (UUID),
            "youtube_video_id": str,
            "chunk_count": int,
            "metadata": dict
        }

    Raises:
        ValueError: If video already ingested (duplicate)
        Exception: If pipeline fails (partial data kept)
    """
```

**Key Implementation Details:**

1. **Duplicate Detection:**
   - Query `TranscriptRepository.get_by_video_id_and_user(video_id, user_id)`
   - If exists, raise `ValueError("Transcript for video {video_id} already ingested")`

2. **Transaction Handling:**
   - Commit after saving transcript
   - Commit after saving all chunks
   - DO NOT rollback on Qdrant failure (keep PostgreSQL data)

3. **Error Handling:**
   - Log each step with INFO level
   - Log failures with ERROR level
   - If Qdrant upsert fails, log error but don't raise
   - Keep partial data (transcript + chunks in PostgreSQL)

4. **Data Flow:**
   ```
   fetch_transcript() → check_duplicate() → save_transcript()
   → chunk_text() → generate_embeddings() → save_chunks()
   → upsert_to_qdrant()
   ```

**Files to Modify:**
- `app/services/transcript_service.py` (add ingest_transcript method)

**Acceptance Criteria:**
- [ ] Full pipeline completes successfully
- [ ] Duplicate detection works (raises ValueError)
- [ ] Transcript saved to PostgreSQL
- [ ] Chunks saved to PostgreSQL with correct indices
- [ ] Vectors upserted to Qdrant
- [ ] Partial data kept on Qdrant failure
- [ ] Detailed logging at each step

---

### Stage 4.6: Transcript Ingestion API Endpoint

**What to build:**

Create REST API endpoint for transcript ingestion.

**Files to Create:**
- `app/api/routes/transcripts.py`

**Endpoint:**
```python
POST /api/transcripts/ingest
Authorization: Bearer <token>
Content-Type: application/json

Request Body:
{
    "youtube_url": "https://youtube.com/watch?v=VIDEO_ID"
}

Response (201 Created):
{
    "id": "uuid",
    "youtube_video_id": "VIDEO_ID",
    "chunk_count": 12,
    "metadata": {
        "title": "Video Title",
        "duration": 300,
        "language": "en"
    }
}

Error Responses:
- 401: Unauthorized (missing/invalid token)
- 409: Conflict (video already ingested)
- 422: Validation Error (invalid URL format)
- 500: Internal Server Error (pipeline failure)
```

**Implementation:**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.transcript import TranscriptIngestRequest, TranscriptResponse
from app.services.transcript_service import TranscriptService
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])

@router.post("/ingest", response_model=TranscriptResponse, status_code=201)
async def ingest_transcript(
    request: TranscriptIngestRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    service = TranscriptService()

    try:
        result = await service.ingest_transcript(
            youtube_url=request.youtube_url,
            user_id=str(current_user.id),
            db_session=db
        )

        return TranscriptResponse(**result)

    except ValueError as e:
        if "already ingested" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
```

**Files to Modify:**
- `app/main.py` (add transcripts router)

**Acceptance Criteria:**
- [ ] Endpoint successfully ingests transcript
- [ ] Requires authentication (401 without token)
- [ ] Duplicate detection works (409 on re-ingestion)
- [ ] Invalid URLs return 422 validation error
- [ ] Error messages are clear and helpful
- [ ] Swagger documentation auto-generated

---

### Stage 4.7: Seed Database with Test Data

**What to build:**

Create seed script for local development that:
1. Creates test user
2. Seeds default LinkedIn template
3. Seeds config table values
4. Sets up Qdrant collection
5. (Optional) Ingests sample YouTube transcripts

**Files to Create:**
- `scripts/seed_database.py`

**Implementation Outline:**
```python
async def main():
    """Seed test user, templates, config, and sample transcripts."""

    # 1. Create test user
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword123")
    )

    # 2. Seed default LinkedIn template
    template = Template(
        template_type="linkedin",
        template_content="""# {{ topic }}

{{ introduction }}

## Key Insights:
{% for point in key_points %}
- {{ point }}
{% endfor %}

{{ conclusion }}

#{{ hashtags | join(' #') }}""",
        is_default=True,
        user_id=None  # Global default
    )

    # 3. Seed config values
    configs = [
        Config(key="max_context_messages", value="10"),
        Config(key="rag_top_k", value="12"),
        Config(key="chunk_size", value="700"),
        Config(key="chunk_overlap_percent", value="20")
    ]

    # 4. Setup Qdrant collection
    qdrant_service = QdrantService()
    await qdrant_service.create_collection()

    # 5. (Optional) Ingest sample transcripts
    # Skip for MVP - users can ingest via API
```

**Usage:**
```bash
cd backend
python scripts/seed_database.py
```

**Output:**
```
Starting database seed...
✓ Created test user: test@example.com (ID: uuid)
✓ Created default LinkedIn template
✓ Created config values
✓ Qdrant collection created
⚠ Skipping transcript ingestion (no test videos configured)

🎉 Seed complete!

Test credentials:
  Email: test@example.com
  Password: testpassword123

Next steps:
  1. Login: POST /api/auth/login
  2. Ingest video: POST /api/transcripts/ingest
```

**Acceptance Criteria:**
- [ ] Script runs without errors
- [ ] Test user created successfully
- [ ] Default template seeded
- [ ] Config values seeded
- [ ] Qdrant collection created
- [ ] Script is idempotent (can run multiple times)
- [ ] Clear output messages
- [ ] Test credentials displayed

---

## Testing Strategy for PR #7

### Integration Tests

**File:** `tests/integration/test_transcript_ingestion.py`

**Test Cases:**
1. ✅ `test_ingest_transcript_success` - Full pipeline end-to-end
2. ✅ `test_ingest_duplicate_returns_409` - Duplicate detection
3. ✅ `test_ingest_requires_authentication` - Auth requirement
4. ✅ `test_ingest_invalid_url_returns_422` - URL validation
5. ✅ `test_full_pipeline_database_and_qdrant` - Verify both DBs updated
6. ✅ `test_short_transcript_single_chunk` - Short transcript handling
7. ✅ `test_qdrant_failure_keeps_postgresql_data` - Partial failure handling

**Coverage Target:** > 80% for all new code

---

## PR #7 Checklist

**Before Creating PR:**
- [ ] All code written and tested locally
- [ ] All tests pass (pytest tests/)
- [ ] Test coverage > 80%
- [ ] Code passes linting (ruff check app/)
- [ ] Code formatted (black app/)
- [ ] Type hints present for all functions
- [ ] Docstrings follow Google style
- [ ] No secrets in code
- [ ] Logging present for each pipeline step

**PR Description Should Include:**
- Summary of orchestration logic
- API endpoint documentation
- Seed script usage instructions
- Test coverage report
- Known limitations (if any)

**After PR Created:**
- [ ] Request review
- [ ] Address review feedback
- [ ] Verify CI/CD passes (if configured)
- [ ] Update HANDOFF.md checkboxes
- [ ] Merge to main

---

## Expected Outcomes After PR #7

**Functional:**
✅ Users can ingest YouTube transcripts via API
✅ Full pipeline: URL → SUPADATA → Chunk → Embed → Store (PostgreSQL + Qdrant)
✅ Duplicate detection prevents re-ingestion
✅ Data isolation by user ID
✅ Both YouTube URL formats supported

**Technical:**
✅ All 3 PRs merged to main
✅ Test coverage > 80% for all Phase 4 code
✅ Comprehensive logging
✅ Graceful error handling
✅ Retry mechanisms for external APIs
✅ Seed script for local development

**Documentation:**
✅ API endpoint auto-documented in Swagger
✅ HANDOFF.md checkboxes updated
✅ README updated (if needed)

---

## Timeline Estimate for PR #7

**Development:** 4-6 hours
- Orchestration method: 1-2 hours
- API endpoint: 1 hour
- Seed script: 1 hour
- Integration tests: 1-2 hours
- Testing and debugging: 1 hour

**Review:** 1-2 hours
**Total:** 5-8 hours

**Calendar Time:** 1-2 days (with review and iterations)

---

## After Phase 4 Complete

**Next Phase: Phase 5 - RAG Foundation**

Will include:
- OpenRouter LLM client
- Jinja2 prompt templates
- LangGraph state definition
- Retriever and Grader nodes
- Unit tests for RAG components

**Key Change:** Switch from `tenacity` to **LangGraph RetryPolicy** for graph nodes (see LANGCHAIN_RETRY.md)

---

## Summary

**Completed:** PR #5 ✅ MERGED, PR #6 ✅ READY FOR MERGE
**Next:** PR #7 - Full pipeline orchestration + API + seed script
**Remaining Work:** ~4-6 hours development + 1-2 hours review
**Blockers:** None - all dependencies ready

**Status:** 🟢 Ready to proceed with PR #7
