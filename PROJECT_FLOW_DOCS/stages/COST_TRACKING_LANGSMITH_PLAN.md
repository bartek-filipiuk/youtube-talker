# LangSmith Cost Tracking Implementation Plan

## Initial User Request

```
ok check what we have here and what we build so far check proper docs from @PROJECT_FLOW_DOCS/
and then we need to check how (if) send costs to Lang Smith. Connection works but i do not see
that we passing costs, we are using llm calls - openrouter, embeddings via openai and also calls
to supadata api. Check the @backend/app/rag/ and detect places where we need send costs to smith.
Prepare a plan where we can store costs, we do not want to hardcoded. SO maybe we can introduce
some /admin/costs path in astro where we can set the costs and backend will use it or maybe easier
will be store them in .env? Use researcher agent to grab current knowledge on how to pass costs to
smith and also how we can estimate it. Ok we need plan it first. DO the research and then ask me
8 solid and clear questions about the implementation, we do not want overcomplications, we need
use modular structure to fit current system.
```

**Date**: 2025-01-29
**Status**: Ready for Implementation

---

## Summary of Research & User Decisions

**Current State:**
- ✅ LangSmith connection configured and working (main.py:136-141)
- ❌ Costs not being tracked (no usage_metadata passed to LangSmith)
- Uses: OpenRouter (Claude Haiku + Gemini Flash), OpenAI embeddings, SUPADATA transcription

**User Decisions:**
1. **Storage**: Database (config table) for pricing configuration
2. **Priority**: LangSmith observability (not user billing)
3. **Database**: LangSmith only - pass user_id as metadata for per-user tracking
4. **Integration**: Use LangChain SDK → **YES, recommended and accepted**
5. **SUPADATA**: Fixed $0.01 per API call
6. **Limits**: No cost limits for MVP
7. **Visibility**: Admin only (via LangSmith dashboard)
8. **Testing**: Unit tests (80% coverage) + manual testing with real APIs

---

## Architecture Decision: LangChain SDK Integration

### Why Migrate to LangChain SDK?

**Recommendation: YES, it's worth it** ✅

**Benefits:**
1. **Automatic LangSmith Integration**: Token counts, costs, and traces sent automatically
2. **Minimal Code Changes**: ~50 lines of refactoring in LLMClient
3. **Per-User Tracking**: Pass user_id as metadata/tags - works out of the box
4. **Standard Patterns**: Industry-standard approach, easier to maintain
5. **Future-Proof**: Automatic support for new models, caching, multi-modal

**Migration Path (Low Risk):**
1. Keep existing `LLMClient` interface (no changes to RAG nodes)
2. Replace internal implementation to use `ChatOpenAI` with OpenRouter base_url
3. Add metadata parameter to pass user_id
4. Total refactoring: ~1-2 hours

**Alternative (Not Recommended):**
- Custom callbacks with existing OpenAI SDK: More code, manual token tracking, harder to maintain

---

## Implementation Plan

### Phase 1: Database Schema for Pricing Configuration

**Goal**: Store API pricing in PostgreSQL config table (dynamically updatable via SQL)

**Tasks:**
1. Create `model_pricing` table in database schema
2. Create SQLAlchemy model `ModelPricing`
3. Create Alembic migration
4. Seed initial pricing data
5. Create `PricingRepository` for querying pricing

**Database Schema:**
```sql
CREATE TABLE model_pricing (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,           -- 'openrouter', 'openai', 'supadata'
    model_name VARCHAR(100) NOT NULL,        -- 'anthropic/claude-haiku-4.5', 'text-embedding-3-small'
    pricing_type VARCHAR(20) NOT NULL,       -- 'per_token', 'per_request'
    input_price_per_1m DECIMAL(10, 6),       -- For per-token models
    output_price_per_1m DECIMAL(10, 6),      -- For per-token models
    cost_per_request DECIMAL(10, 6),         -- For per-request models (SUPADATA)
    cache_discount DECIMAL(5, 4),            -- For cached tokens (e.g., 0.25 for Gemini)
    effective_from TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, model_name, effective_from)
);

CREATE INDEX idx_model_pricing_lookup
ON model_pricing(provider, model_name, is_active);
```

**Seed Data:**
```sql
INSERT INTO model_pricing (provider, model_name, pricing_type, input_price_per_1m, output_price_per_1m, notes)
VALUES
    ('openrouter', 'anthropic/claude-haiku-4.5', 'per_token', 1.00, 5.00, 'Claude Haiku 4.5 via OpenRouter'),
    ('openrouter', 'google/gemini-2.5-flash', 'per_token', 0.40, 1.20, 'Gemini Flash 2.5 with caching'),
    ('openai', 'text-embedding-3-small', 'per_token', 0.02, 0.00, 'Embeddings only use input pricing'),
    ('supadata', 'fetch_transcript', 'per_request', NULL, NULL, 'Fixed $0.01 per API call');

UPDATE model_pricing SET cost_per_request = 0.01 WHERE provider = 'supadata';
UPDATE model_pricing SET cache_discount = 0.25 WHERE model_name = 'google/gemini-2.5-flash';
```

**Files to Create:**
- `backend/app/db/models.py` (add ModelPricing model)
- `backend/app/db/repositories/pricing_repo.py` (new repository)
- `backend/alembic/versions/XXXX_add_model_pricing.py` (migration)
- `backend/scripts/seed_pricing.py` (seed script)

**Acceptance Criteria:**
- [ ] model_pricing table created
- [ ] Initial pricing data seeded
- [ ] PricingRepository has `get_pricing(provider, model_name)` method
- [ ] Unit tests for repository (80% coverage)

---

### Phase 2: Migrate LLMClient to LangChain SDK

**Goal**: Replace direct OpenAI SDK calls with LangChain ChatOpenAI for automatic LangSmith integration

**Current Code (backend/app/rag/utils/llm_client.py:42-56):**
```python
# Currently uses OpenAI SDK directly with base_url override
self.client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)
```

**New Approach:**
```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class LLMClient:
    def __init__(self):
        # Claude for text generation
        self.claude = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="anthropic/claude-haiku-4.5",
            temperature=0.7,
            # Metadata for LangSmith
            model_kwargs={
                "extra_headers": {
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                    "X-Title": settings.OPENROUTER_SITE_NAME,
                }
            }
        )

        # Gemini for structured output
        self.gemini = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.5-flash",
            temperature=0.3,
            model_kwargs={
                "response_format": {"type": "json_object"},
                "extra_headers": {
                    "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                    "X-Title": settings.OPENROUTER_SITE_NAME,
                }
            }
        )

    async def ainvoke_claude(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: str = None,
        user_id: str = None,  # NEW: for per-user tracking
    ) -> str:
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Pass metadata for LangSmith
        config = {
            "metadata": {
                "user_id": user_id,
                "ls_provider": "openrouter",
                "ls_model_name": "anthropic/claude-haiku-4.5",
            },
            "tags": ["openrouter", "claude-haiku", f"user:{user_id}"] if user_id else ["openrouter", "claude-haiku"],
        }

        response = await self.claude.ainvoke(messages, config=config)

        # Log usage (automatically sent to LangSmith)
        logger.debug(f"Claude usage: {response.usage_metadata}")

        return response.content

    async def ainvoke_gemini_structured(
        self,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.3,
        user_id: str = None,  # NEW
    ) -> T:
        # Similar implementation for Gemini with structured output
        system_prompt = f"""You are a data extraction assistant.
Respond with valid JSON only that matches this exact schema:

{json.dumps(schema.model_json_schema(), indent=2)}

Do not include explanations or additional text. Only output the JSON object."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]

        config = {
            "metadata": {
                "user_id": user_id,
                "ls_provider": "openrouter",
                "ls_model_name": "google/gemini-2.5-flash",
            },
            "tags": ["openrouter", "gemini-flash", f"user:{user_id}"] if user_id else ["openrouter", "gemini-flash"],
        }

        response = await self.gemini.ainvoke(messages, config=config)
        logger.debug(f"Gemini usage: {response.usage_metadata}")

        # Parse and validate JSON
        try:
            data = json.loads(response.content)
            validated = schema.model_validate(data)
            return validated
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            raise
```

**Key Changes:**
1. Replace `AsyncOpenAI` with `ChatOpenAI` (LangChain)
2. Add `user_id` parameter to all methods (backward compatible with default=None)
3. Pass metadata/tags for LangSmith tracking
4. Remove manual token counting (automatic via LangChain)
5. Keep same interface - no changes to RAG nodes

**Files to Modify:**
- `backend/app/rag/utils/llm_client.py` (~100 lines, mostly replacing OpenAI SDK calls)
- Update method signatures to accept `user_id` (backward compatible with default=None)

**Files to Update (pass user_id):**
- `backend/app/rag/nodes/router_node.py` (classify_intent)
- `backend/app/rag/nodes/grader.py` (grade_chunks)
- `backend/app/rag/nodes/generator.py` (generate_response)

**Acceptance Criteria:**
- [ ] LLMClient uses LangChain ChatOpenAI
- [ ] user_id passed to all LLM calls
- [ ] usage_metadata logged for each call
- [ ] Existing tests pass (mock LangChain instead of OpenAI)
- [ ] LangSmith dashboard shows traces with user_id

---

### Phase 3: Add LangSmith Metadata to Embedding Service

**Goal**: Track OpenAI embedding costs in LangSmith

**Current Code (backend/app/services/embedding_service.py:83-97):**
```python
# Currently uses direct httpx calls to OpenAI API
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{self.base_url}/embeddings",
        json={"model": self.model, "input": texts},
        ...
    )
```

**New Approach (LangChain):**
```python
from langchain_openai import OpenAIEmbeddings

class EmbeddingService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )

    async def generate_embeddings(
        self,
        texts: List[str],
        user_id: str = None,
    ) -> List[List[float]]:
        if not texts:
            return []

        # Pass metadata for LangSmith
        config = {
            "metadata": {
                "user_id": user_id,
                "operation": "embedding",
                "num_texts": len(texts),
            },
            "tags": ["openai", "embeddings", f"user:{user_id}"] if user_id else ["openai", "embeddings"],
        }

        # LangChain automatically batches and tracks usage
        vectors = await self.embeddings.aembed_documents(texts, config=config)

        logger.debug(f"Generated {len(vectors)} embeddings for user {user_id}")

        return vectors
```

**Files to Modify:**
- `backend/app/services/embedding_service.py` (~50 lines)
- Update calls in `backend/app/rag/nodes/retriever.py` to pass user_id

**Acceptance Criteria:**
- [ ] Embedding service uses LangChain OpenAIEmbeddings
- [ ] user_id passed to embedding calls
- [ ] LangSmith shows embedding costs per user
- [ ] Tests updated (mock LangChain embeddings)

---

### Phase 4: Track SUPADATA Costs in LangSmith

**Goal**: Track SUPADATA API calls as $0.01 per request in LangSmith

**Approach**: Custom metadata injection (no LangChain integration needed)

**Implementation:**
```python
from langsmith import Client as LangSmithClient
from datetime import datetime

class TranscriptService:
    def __init__(self):
        self.client = Supadata(api_key=settings.SUPADATA_API_KEY)
        self.langsmith = LangSmithClient() if settings.LANGSMITH_TRACING else None

    async def fetch_transcript(
        self,
        youtube_url: str,
        user_id: str = None,
    ) -> Dict:
        start_time = datetime.now()

        try:
            # Existing SUPADATA call
            video_id = self._extract_video_id(youtube_url)
            video = await asyncio.to_thread(self.client.youtube.video, id=video_id)
            transcript = await asyncio.to_thread(
                self.client.youtube.transcript, video_id=video_id, text=True
            )

            # Track cost in LangSmith
            if self.langsmith and user_id:
                self._track_supadata_cost(
                    user_id=user_id,
                    video_id=video_id,
                    duration=(datetime.now() - start_time).total_seconds(),
                )

            return {
                "youtube_video_id": getattr(video, "id", video_id),
                "transcript_text": getattr(transcript, "content", ""),
                "metadata": {...}
            }
        except Exception as e:
            logger.exception("SUPADATA call failed")
            raise

    def _track_supadata_cost(self, user_id: str, video_id: str, duration: float):
        """Create LangSmith trace for SUPADATA API call."""
        try:
            run_start = datetime.now() - timedelta(seconds=duration)
            self.langsmith.create_run(
                name="SUPADATA: Fetch Transcript",
                run_type="llm",  # Use "llm" type for cost tracking
                inputs={"video_id": video_id},
                outputs={"status": "success"},
                start_time=run_start,
                end_time=datetime.now(),
                extra={
                    "metadata": {
                        "user_id": user_id,
                        "ls_provider": "supadata",
                        "ls_model_name": "fetch_transcript",
                        "usage_metadata": {
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "total_tokens": 0,
                        },
                        "cost": 0.01,  # Fixed cost
                    },
                    "tags": ["supadata", "transcription", f"user:{user_id}"],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to track SUPADATA cost in LangSmith: {e}")
```

**Files to Modify:**
- `backend/app/services/transcript_service.py` (~40 lines added)
- Update `ingest_transcript` to pass user_id to `fetch_transcript`

**Acceptance Criteria:**
- [ ] SUPADATA calls tracked in LangSmith
- [ ] Fixed $0.01 cost per call
- [ ] user_id included in metadata
- [ ] Errors don't break transcription flow (best-effort tracking)

---

### Phase 5: Configure LangSmith Pricing via Web UI

**Goal**: Set up custom pricing in LangSmith for OpenRouter models

**Manual Steps (Web UI):**
1. Go to `https://smith.langchain.com/settings/workspaces/models`
2. Click "Add new model"
3. Configure Claude Haiku:
   - **Model Name**: "Claude Haiku 4.5 (OpenRouter)"
   - **Match Pattern**: `anthropic/claude-haiku-4.5` 
   - **Provider**: "openrouter"
   - **Prompt Price**: $1.00 per 1M tokens
   - **Completion Price**: $5.00 per 1M tokens
4. Configure Gemini Flash:
   - **Model Name**: "Gemini Flash 2.5 (OpenRouter)"
   - **Match Pattern**: `google/gemini-2\.5-flash.*`
   - **Provider**: "openrouter"
   - **Prompt Price**: $0.40 per 1M tokens
   - **Completion Price**: $1.20 per 1M tokens
   - **Cache Read Price**: $0.10 per 1M tokens (25% discount)
5. Configure OpenAI Embeddings:
   - **Model Name**: "text-embedding-3-small"
   - **Match Pattern**: `text-embedding-3-small`
   - **Provider**: "openai"
   - **Prompt Price**: $0.02 per 1M tokens
   - **Completion Price**: $0.00
6. Configure SUPADATA:
   - **Model Name**: "SUPADATA Transcription"
   - **Match Pattern**: `fetch_transcript`
   - **Provider**: "supadata"
   - **Fixed Cost**: $0.01 per request (use prompt price field)

**Documentation:**
- Create `docs/LANGSMITH_SETUP.md` with screenshots and instructions
- Document pricing update process

**Acceptance Criteria:**
- [ ] All 4 models configured in LangSmith UI
- [ ] Match patterns tested (verify traces match pricing)
- [ ] Documentation created

---

### Phase 6: Update RAG Nodes to Pass user_id

**Goal**: Propagate user_id through entire RAG pipeline

**Current GraphState (backend/app/rag/utils/state.py):**
```python
class GraphState(TypedDict):
    user_query: str
    user_id: str  # Already exists! ✅
    conversation_history: List[Dict[str, str]]
    intent: Optional[str]
    retrieved_chunks: Optional[List[Dict]]
    graded_chunks: Optional[List[Dict]]
    response: Optional[str]
    metadata: Optional[Dict]
```

**Changes Needed:**

**1. Router Node** (backend/app/rag/nodes/router_node.py:18):
```python
async def classify_intent(state: GraphState) -> Dict[str, Any]:
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")  # Extract user_id
    conversation_history = state.get("conversation_history", [])

    prompt = render_prompt(
        "query_router.jinja2",
        user_query=user_query,
        conversation_history=conversation_history
    )

    # Pass user_id to LLM
    llm_client = LLMClient()
    classification = await llm_client.ainvoke_gemini_structured(
        prompt=prompt,
        schema=IntentClassification,
        temperature=0.3,
        user_id=user_id,  # NEW
    )

    logger.info(f"Intent classified as '{classification.intent}' for user {user_id}")

    return {
        **state,
        "intent": classification.intent,
        "metadata": {
            **(state.get("metadata", {})),
            "intent_confidence": classification.confidence,
            "intent_reasoning": classification.reasoning
        }
    }
```

**2. Retriever Node** (backend/app/rag/nodes/retriever.py:16):
```python
async def retrieve_chunks(state: GraphState) -> GraphState:
    user_query = state.get("user_query")
    user_id = state.get("user_id")

    if not user_query or not user_id:
        logger.warning(f"Missing required fields: user_query={bool(user_query)}, user_id={bool(user_id)}")
        state["retrieved_chunks"] = []
        return state

    logger.info(f"Retrieving chunks for query: '{user_query[:50]}...' (user_id={user_id})")

    # Step 1: Generate query embedding
    embedding_service = EmbeddingService()
    embeddings = await embedding_service.generate_embeddings(
        [user_query],
        user_id=user_id,  # NEW
    )
    query_vector = embeddings[0]

    # Rest of retrieval logic...
```

**3. Grader Node** (backend/app/rag/nodes/grader.py:17):
```python
async def grade_chunks(state: GraphState) -> GraphState:
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")  # NEW
    retrieved_chunks = state.get("retrieved_chunks", [])

    if not user_query:
        logger.warning("Missing user_query in state")
        state["graded_chunks"] = []
        return state

    if not retrieved_chunks:
        logger.info("No retrieved chunks to grade")
        state["graded_chunks"] = []
        return state

    logger.info(f"Grading {len(retrieved_chunks)} chunks for user {user_id}")

    llm_client = LLMClient()
    graded_chunks = []

    for chunk in retrieved_chunks:
        try:
            prompt = render_prompt(
                "chunk_grader.jinja2",
                user_query=user_query,
                chunk_text=chunk["chunk_text"],
                chunk_metadata={
                    "youtube_video_id": chunk["youtube_video_id"],
                    "chunk_index": chunk["chunk_index"],
                },
            )

            grade: RelevanceGrade = await llm_client.ainvoke_gemini_structured(
                prompt=prompt,
                schema=RelevanceGrade,
                user_id=user_id,  # NEW
            )

            if grade.is_relevant:
                graded_chunk = {
                    **chunk,
                    "relevance_reasoning": grade.reasoning,
                }
                graded_chunks.append(graded_chunk)
        except Exception as e:
            logger.exception(f"Error grading chunk: {e}")
            continue

    state["graded_chunks"] = graded_chunks
    logger.info(f"Graded {len(graded_chunks)} relevant chunks for user {user_id}")
    return state
```

**4. Generator Node** (backend/app/rag/nodes/generator.py:17):
```python
async def generate_response(state: GraphState) -> Dict[str, Any]:
    intent = state.get("intent", "chitchat")
    user_query = state.get("user_query", "")
    user_id = state.get("user_id")  # NEW
    conversation_history = state.get("conversation_history", [])
    graded_chunks = state.get("graded_chunks", [])

    logger.info(f"Generating response for intent: {intent} (user: {user_id})")

    llm_client = LLMClient()

    if intent == "chitchat":
        prompt = render_prompt(
            "chitchat_flow.jinja2",
            user_query=user_query,
            conversation_history=conversation_history
        )
        response = await llm_client.ainvoke_claude(
            prompt=prompt,
            max_tokens=500,
            temperature=0.8,
            user_id=user_id,  # NEW
        )
        metadata = {
            **(state.get("metadata", {})),
            "response_type": "chitchat",
            "chunks_used": 0
        }

    elif intent == "qa":
        prompt = render_prompt(
            "rag_qa.jinja2",
            user_query=user_query,
            conversation_history=conversation_history,
            graded_chunks=graded_chunks
        )
        response = await llm_client.ainvoke_claude(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.7,
            user_id=user_id,  # NEW
        )
        # ... rest of qa logic

    # ... similar for linkedin
```

**Files to Modify:**
- `backend/app/rag/nodes/router_node.py`
- `backend/app/rag/nodes/retriever.py`
- `backend/app/rag/nodes/grader.py`
- `backend/app/rag/nodes/generator.py`

**Acceptance Criteria:**
- [ ] user_id passed to all LLM/embedding calls
- [ ] RAG flow tests pass
- [ ] LangSmith traces show user_id in metadata

---

### Phase 7: Testing & Validation

**Goal**: Ensure 80% test coverage and validate LangSmith integration

**Unit Tests:**
1. **Test PricingRepository**:
   - `test_get_pricing_for_valid_model()`
   - `test_get_pricing_for_missing_model()`
   - `test_get_pricing_with_date_range()`

2. **Test LLMClient** (mock LangChain):
   - `test_ainvoke_claude_with_user_id()`
   - `test_ainvoke_gemini_with_metadata()`
   - `test_usage_metadata_logged()`

3. **Test EmbeddingService**:
   - `test_generate_embeddings_with_user_id()`
   - `test_embedding_batching_preserves_metadata()`

4. **Test RAG Nodes**:
   - Update existing tests to pass user_id
   - Verify metadata propagation

**Integration Tests:**
```python
# backend/tests/integration/test_cost_tracking.py

@pytest.mark.asyncio
async def test_rag_flow_tracks_costs_in_langsmith(db_session, mock_langsmith):
    """Test that RAG flow sends cost data to LangSmith."""
    # Setup
    user_id = "test-user-123"
    query = "What is FastAPI?"

    # Execute RAG flow
    result = await run_rag_flow(
        user_id=user_id,
        query=query,
    )

    # Verify LangSmith received traces
    assert mock_langsmith.create_run.called
    calls = mock_langsmith.create_run.call_args_list

    # Check user_id in metadata
    for call in calls:
        metadata = call[1].get("extra", {}).get("metadata", {})
        assert metadata.get("user_id") == user_id

    # Verify expected calls: router, grader (12x), generator, embeddings
    assert len(calls) >= 15
```

**Manual Testing Checklist:**
- [ ] Run real OpenRouter call, verify cost in LangSmith dashboard
- [ ] Run real OpenAI embedding, verify cost in LangSmith
- [ ] Trigger SUPADATA transcript fetch, verify $0.01 cost logged
- [ ] Check LangSmith dashboard filters by user_id
- [ ] Verify pricing matches configuration (OpenRouter $1/$5 per 1M tokens)
- [ ] Test full RAG flow end-to-end with real APIs

**Files to Create/Modify:**
- `backend/tests/unit/test_pricing_repo.py` (new)
- `backend/tests/unit/test_llm_client.py` (update mocks)
- `backend/tests/unit/test_embedding_service.py` (update mocks)
- `backend/tests/integration/test_cost_tracking.py` (new)

**Acceptance Criteria:**
- [ ] Unit test coverage ≥80% for new code
- [ ] Integration tests pass
- [ ] Manual testing checklist completed
- [ ] LangSmith dashboard shows accurate costs per user

---

### Phase 8: Documentation & Cleanup

**Goal**: Document implementation and clean up code

**Tasks:**
1. Update `HANDOFF.md` with completed checkboxes
2. Create `docs/COST_TRACKING.md` with:
   - Architecture overview
   - How to update pricing in database
   - How to view costs in LangSmith
   - Troubleshooting guide
3. Update `CLAUDE.md` with cost tracking patterns
4. Add comments to code explaining LangSmith metadata
5. Run linter (`ruff check app/`)
6. Run formatter (`black app/`)

**Files to Create/Update:**
- `docs/COST_TRACKING.md` (new)
- `docs/LANGSMITH_SETUP.md` (new)
- `HANDOFF.md` (update Phase 9.7 checkbox)
- `CLAUDE.md` (add cost tracking section)

**Acceptance Criteria:**
- [ ] Documentation complete and accurate
- [ ] Code formatted and linted
- [ ] No unused imports or dead code
- [ ] HANDOFF.md updated

---

## Implementation Summary

**Files to Create (8):**
1. `backend/app/db/repositories/pricing_repo.py`
2. `backend/alembic/versions/XXXX_add_model_pricing.py`
3. `backend/scripts/seed_pricing.py`
4. `backend/tests/unit/test_pricing_repo.py`
5. `backend/tests/integration/test_cost_tracking.py`
6. `docs/COST_TRACKING.md`
7. `docs/LANGSMITH_SETUP.md`
8. `PROJECT_FLOW_DOCS/stages/COST_TRACKING_LANGSMITH_PLAN.md` (this file)

**Files to Modify (8):**
1. `backend/app/db/models.py` (add ModelPricing)
2. `backend/app/rag/utils/llm_client.py` (migrate to LangChain)
3. `backend/app/services/embedding_service.py` (migrate to LangChain)
4. `backend/app/services/transcript_service.py` (add LangSmith tracking)
5. `backend/app/rag/nodes/router_node.py` (pass user_id)
6. `backend/app/rag/nodes/grader.py` (pass user_id)
7. `backend/app/rag/nodes/generator.py` (pass user_id)
8. `backend/app/rag/nodes/retriever.py` (pass user_id)

**New Dependencies:**
```bash
pip install langchain-openai langchain-core langsmith
```

**Environment Variables (already configured in .env.example:33-37):**
- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=<your-key>`
- `LANGSMITH_PROJECT=youtube-talker`
- `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com`

---

## Estimated Effort

**Total Time**: ~8-12 hours

**Breakdown:**
- Phase 1 (Database): 2 hours
- Phase 2 (LLMClient refactor): 2 hours
- Phase 3 (Embeddings): 1 hour
- Phase 4 (SUPADATA): 1 hour
- Phase 5 (LangSmith UI): 1 hour
- Phase 6 (RAG nodes): 2 hours
- Phase 7 (Testing): 2-3 hours
- Phase 8 (Documentation): 1 hour

**Risk Level**: Low-Medium
- LangChain SDK is well-documented and widely used
- Minimal refactoring (keep existing interfaces)
- Can test incrementally per phase
- Rollback easy (just revert LLMClient changes)

---

## Success Metrics

**After Implementation:**
1. ✅ LangSmith dashboard shows costs for all LLM calls
2. ✅ Costs broken down by user_id
3. ✅ Pricing stored in database (no hardcoding)
4. ✅ 80%+ test coverage for new code
5. ✅ No breaking changes to existing RAG flows
6. ✅ Documentation complete

**Cost Tracking in LangSmith:**
- Can filter traces by user_id
- Can see total cost per user
- Can see cost breakdown by model (Claude vs Gemini vs Embeddings)
- SUPADATA calls tracked as $0.01 each

---

## Next Steps After Plan Approval

1. ✅ Plan saved to `PROJECT_FLOW_DOCS/stages/COST_TRACKING_LANGSMITH_PLAN.md`
2. Create feature branch: `git checkout -b feature/langsmith-cost-tracking`
3. Start with Phase 1 (database schema) - safest, no code changes yet
4. Test each phase before moving to next
5. Create PR after Phase 7 (after tests pass)
6. Manual validation in Phase 7 before merging

---

## Research Summary

**Key Findings from Research Agent:**

1. **LangSmith Automatic Integration**: LangChain SDK automatically sends usage_metadata to LangSmith when tracing is enabled
2. **Per-User Tracking**: Pass user_id in metadata/tags - LangSmith supports filtering by metadata
3. **Custom Pricing**: Configure via LangSmith web UI (no programmatic API available)
4. **Token Counting**: Use `usage_metadata` attribute from LangChain responses
5. **Multiple Models**: LangChain ChatOpenAI works with OpenRouter via base_url override
6. **Embeddings**: LangChain OpenAIEmbeddings supports metadata/tags for tracking
7. **Cost Calculation**: LangSmith auto-calculates costs based on configured pricing + token counts
8. **No Database Needed**: For observability-only use case, LangSmith stores all cost data

**Implementation Pattern:**
- Pricing config in database (for flexibility)
- Actual cost tracking in LangSmith (no user_costs table needed)
- Pass user_id as metadata to enable per-user filtering
- Use LangChain SDK for automatic integration

---

## Open Questions (All Answered)

1. ✅ **LangChain SDK worth it?** YES - automatic LangSmith integration
2. ✅ **Per-user tracking?** YES - pass user_id as metadata/tags
3. ✅ **Database for costs?** NO - LangSmith only (pricing in DB)
4. ✅ **SUPADATA cost?** Fixed $0.01 per call
5. ✅ **User-facing costs?** NO - admin only via LangSmith
6. ✅ **Cost limits?** NO - not for MVP
7. ✅ **Testing?** Unit tests (80%) + manual with real APIs
8. ✅ **Storage?** Database for pricing config, LangSmith for actual costs

---

**Plan Status**: ✅ APPROVED - Ready for Implementation
**Created**: 2025-01-29
**Author**: Claude Code Agent
**Next Action**: Start Phase 1 - Database Schema