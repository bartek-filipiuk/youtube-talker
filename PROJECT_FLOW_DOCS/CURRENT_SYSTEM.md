# YoutubeTalker - Current System Analysis

**Last Updated:** 2025-11-03
**Analysis Type:** Deep Codebase Exploration
**Purpose:** Complete understanding before adding new functionality

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Chat Endpoints](#chat-endpoints)
3. [RAG Implementation](#rag-implementation)
4. [Intent Classification](#intent-classification)
5. [LangGraph Nodes & Flows](#langgraph-nodes--flows)
6. [Database Schema](#database-schema)
7. [Vector Storage (Qdrant)](#vector-storage-qdrant)
8. [LLM Integration](#llm-integration)
9. [Key Services](#key-services)
10. [Architecture Patterns](#architecture-patterns)
11. [Complete Data Flow Examples](#complete-data-flow-examples)
12. [Configuration](#configuration)
13. [File Locations Reference](#file-locations-reference)

---

## System Overview

**YoutubeTalker** is an AI-powered chat application enabling users to query YouTube video transcripts using RAG (Retrieval-Augmented Generation) and generate content like LinkedIn posts.

### Tech Stack
- **Backend:** FastAPI (async) + SQLAlchemy 2.0 + PostgreSQL 15
- **Vector DB:** Qdrant (semantic search, 1536-dim vectors)
- **RAG:** LangGraph + LangChain
- **LLMs:**
  - Claude Haiku 4.5 (text generation via OpenRouter)
  - Gemini 2.5 Flash (structured JSON output via OpenRouter)
- **Embeddings:** OpenAI text-embedding-3-small (1536-dim)
- **Auth:** Server-side sessions (7-day expiry)

### Core Features
1. YouTube transcript ingestion, chunking, embedding
2. Multi-intent chat system (6 intent types)
3. RAG-powered Q&A with chunk grading
4. LinkedIn post generation with retrieved knowledge
5. Semantic video search by subject/topic
6. Real-time WebSocket chat

---

## Chat Endpoints

### REST API Routes

**File:** `backend/app/api/routes/conversations.py`

| Method | Route | Purpose | Auth | Pagination |
|--------|-------|---------|------|------------|
| GET | `/api/conversations` | List user conversations | ✓ | limit/offset |
| GET | `/api/conversations/{id}` | Get conversation + messages | ✓ | - |
| POST | `/api/conversations` | Create new conversation | ✓ | - |
| DELETE | `/api/conversations/{id}` | Delete conversation (cascade) | ✓ | - |

**Key Implementation Details:**
```python
# List conversations - paginated, ordered by updated_at DESC
@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
)
```

### WebSocket Endpoint

**File:** `backend/app/api/websocket/chat_handler.py`
**Route:** `WS /api/ws/chat?token=<session_token>`

**WebSocket Flow:**
1. Authenticate via query param token
2. Accept connection → Register in ConnectionManager
3. Loop: receive JSON messages
4. Validate with `IncomingMessage` schema (max 2000 chars)
5. Rate limiting enforcement (per-user)
6. Auto-create conversation if needed
7. Call RAG pipeline (`run_graph`)
8. Save user + assistant messages to DB
9. Stream response back to client
10. Update conversation.updated_at timestamp

**Special Features:**
- Heartbeat support (ping/pong)
- Video load detection (video_load intent)
- Confirmation response for video loads
- Full message persistence

**Message Format:**
```javascript
// Client → Server
{"message": "What is in the videos?"}

// Server → Client
{"type": "assistant", "content": "<p>...</p>", "metadata": {...}}
```

---

## RAG Implementation

### Architecture Diagram

```
User Query (WebSocket)
       ↓
Router Node → Intent Classification (Gemini)
       ↓
   ┌───┴────┬──────────┬───────────┬──────────────┬─────────────┐
   ↓        ↓          ↓           ↓              ↓             ↓
CHITCHAT   QA      LINKEDIN    METADATA    METADATA_SEARCH  VIDEO_LOAD
  (LLM)  (RAG)    (RAG+topic)    (DB)         (Semantic)     (Parse)
   ↓        ↓          ↓           ↓              ↓             ↓
Generator Retriever  Retriever  MetadataNode  SubjectExtractor VideoLoadNode
          ↓          ↓                          ↓
          Grader     Grader                VideoSearchNode
          ↓          ↓
          Generator  Generator
```

### Entry Point

**File:** `backend/app/rag/graphs/router.py`

```python
async def run_graph(
    user_query: str,
    user_id: str,
    conversation_history: list,
    config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Main RAG orchestrator

    Returns:
        {
            "response": str,
            "intent": str,
            "metadata": {
                "intent_confidence": float,
                "chunks_used": int,
                "source_chunks": List[str],
                "response_type": str
            }
        }
    """
```

**Flow:**
1. Initialize `GraphState` with query, user_id, history, config
2. Call `classify_intent()` (Router Node)
3. Route to appropriate compiled flow
4. Return final state with response + metadata

### Graph State Schema

**File:** `backend/app/rag/utils/state.py`

```python
class GraphState(TypedDict, total=False):
    # Input
    user_query: str
    user_id: str
    conversation_history: List[Dict[str, str]]
    config: Optional[Dict[str, any]]

    # Intermediate
    intent: Optional[str]
    subject: Optional[str]
    retrieved_chunks: Optional[List[Dict]]
    graded_chunks: Optional[List[Dict]]

    # Output
    response: Optional[str]
    metadata: Optional[Dict]
```

---

## Intent Classification

### Intent Types

**File:** `backend/app/rag/nodes/router_node.py`

| Intent | Trigger | RAG Required | Flow Path |
|--------|---------|--------------|-----------|
| **chitchat** | Greetings, casual talk | ✗ | Generator only |
| **qa** | Questions about videos | ✓ | Retriever → Grader → Generator |
| **linkedin** | "Create LinkedIn post" | ✓ | Retriever → Grader → Generator (template) |
| **metadata** | "List all my videos" | ✗ | MetadataNode (DB query) |
| **metadata_search** | "Find videos about X" | ✓ | SubjectExtractor → VideoSearchNode |
| **video_load** | YouTube URL detected | ✗ | VideoLoadNode (parse URL) |

### Classification Implementation

**File:** `backend/app/rag/nodes/router_node.py`

```python
async def classify_intent(state: GraphState) -> Dict[str, Any]:
    # 1. Render query_router.jinja2 template
    # 2. Call LLMClient.ainvoke_gemini_structured(
    #       prompt,
    #       schema=IntentClassification
    #    )
    # 3. Return state with intent + confidence + reasoning
```

**Model:** `google/gemini-2.5-flash` (temperature: 0.3)

**Output Schema:**
```python
class IntentClassification(BaseModel):
    intent: Literal["chitchat", "qa", "linkedin", "metadata", "metadata_search", "video_load"]
    confidence: float  # 0.0-1.0
    reasoning: str     # max 300 chars
```

**Prompt Template:** `backend/app/rag/prompts/query_router.jinja2`

**Key Instructions:**
- Metadata: List ALL videos without filtering
- Metadata_search: Find videos by SPECIFIC SUBJECT/TOPIC
- Video_load: YouTube URL detected
- QA: Video content question
- LinkedIn: Post generation request
- Chitchat: Casual conversation

---

## LangGraph Nodes & Flows

### Node Implementations

#### 1. Retriever Node
**File:** `backend/app/rag/nodes/retriever.py`

```python
async def retrieve_chunks(state: GraphState) -> GraphState:
    # 1. Generate embedding for user_query (1536-dim)
    # 2. Search Qdrant with user_id filter (top-k=12 default)
    # 3. Return state["retrieved_chunks"]
```

**Output Format:**
```python
retrieved_chunks = [
    {
        "chunk_id": str,
        "chunk_text": str,
        "chunk_index": int,
        "youtube_video_id": str,
        "score": float
    },
    ...
]
```

#### 2. Grader Node
**File:** `backend/app/rag/nodes/grader.py`

```python
async def grade_chunks(state: GraphState) -> GraphState:
    # For each chunk:
    #   1. Render chunk_grader.jinja2 template
    #   2. Call ainvoke_gemini_structured(schema=RelevanceGrade)
    #   3. Keep only is_relevant=True chunks
    # Return state["graded_chunks"]
```

**Grader Schema:**
```python
class RelevanceGrade(BaseModel):
    is_relevant: bool
    reasoning: str  # max 500 chars
```

**Prompt:** `backend/app/rag/prompts/chunk_grader.jinja2`

#### 3. Generator Node
**File:** `backend/app/rag/nodes/generator.py`

```python
async def generate_response(state: GraphState) -> Dict[str, Any]:
    intent = state.get("intent", "chitchat")

    if intent == "chitchat":
        prompt = render_prompt("chitchat_flow.jinja2", ...)
    elif intent == "qa":
        prompt = render_prompt("rag_qa.jinja2", ...)
    elif intent == "linkedin":
        prompt = render_prompt("linkedin_post_generate.jinja2", ...)

    response = await llm_client.ainvoke_claude(...)
    return state
```

**Model:** Claude Haiku 4.5 (via OpenRouter)

#### 4. Metadata Node
**File:** `backend/app/rag/nodes/metadata_node.py`

```python
async def get_user_videos(state: GraphState) -> Dict[str, Any]:
    # 1. Query database for user's transcripts (limit 20)
    # 2. Format as HTML list with title, channel, duration, language
    # 3. Return state with HTML response
```

#### 5. Subject Extractor Node
**File:** `backend/app/rag/nodes/subject_extractor_node.py`

```python
async def extract_subject(state: GraphState) -> Dict[str, Any]:
    # 1. Render subject_extractor.jinja2 template
    # 2. Call ainvoke_gemini_structured(schema=SubjectExtraction)
    # 3. Return state["subject"]
```

**Output Schema:**
```python
class SubjectExtraction(BaseModel):
    subject: str  # 1-200 chars
    confidence: float
    reasoning: str  # max 300 chars
```

#### 6. Video Search Node
**File:** `backend/app/rag/nodes/video_search_node.py`

```python
async def search_videos_by_subject(state: GraphState) -> Dict[str, Any]:
    # 1. Generate embedding for subject
    # 2. Search Qdrant (top-100 for more coverage)
    # 3. Group chunks by youtube_video_id, calculate avg score
    # 4. Query database for top-20 videos
    # 5. Sort by relevance score DESC
    # 6. Format as HTML list with relevance scores
```

#### 7. Video Load Node
**File:** `backend/app/rag/graphs/flows/video_load_flow.py`

```python
async def handle_video_load_node(state: GraphState) -> GraphState:
    # 1. Extract YouTube video_id from user_query
    # 2. Return state with response="VIDEO_LOAD_REQUEST:{video_id}"
    # 3. WebSocket handler takes over for actual loading
```

### Compiled Flows

#### A. Chitchat Flow
**File:** `backend/app/rag/graphs/flows/chitchat_flow.py`

**Topology:** `START → Generator → END`

**Nodes:** 1 (Generator)
**Retry Policy:** None
**Use Case:** Casual conversations

#### B. Q&A Flow
**File:** `backend/app/rag/graphs/flows/qa_flow.py`

**Topology:** `START → Retriever → Grader → Generator → END`

**Nodes:** 3
**Retry Policy:**
```python
RetryPolicy(
    max_attempts=3,
    backoff_factor=2.0,        # Exponential backoff
    initial_interval=1.0,      # Start at 1 second
    max_interval=10.0,         # Cap at 10 seconds
    jitter=True
)
```
Applied to: Retriever, Grader (not Generator)

#### C. LinkedIn Flow
**File:** `backend/app/rag/graphs/flows/linkedin_flow.py`

**Topology:** `START → Retriever → Grader → Generator → END`

**Identical to Q&A flow but uses `linkedin_post_generate.jinja2` template**

#### D. Metadata Flow
**File:** `backend/app/rag/graphs/flows/metadata_flow.py`

**Topology:** `START → MetadataNode → END`

**Nodes:** 1
**Use Case:** List all user videos

#### E. Metadata Search Flow
**File:** `backend/app/rag/graphs/flows/metadata_search_flow.py`

**Topology:** `START → SubjectExtractor → VideoSearchNode → END`

**Nodes:** 2
**Retry Policy:** Applied to both nodes
**Use Case:** Find videos by subject/topic

#### F. Video Load Flow
**File:** `backend/app/rag/graphs/flows/video_load_flow.py`

**Topology:** `START → VideoLoadNode → END`

**Nodes:** 1
**Use Case:** Parse YouTube URL

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────┐
│   users (1) │
└──────┬──────┘
       │
       ├──→ sessions (*)        [1:N, CASCADE delete]
       ├──→ conversations (*)   [1:N, CASCADE delete]
       ├──→ transcripts (*)     [1:N, CASCADE delete]
       ├──→ chunks (*)          [1:N, RESTRICT delete]
       └──→ templates (*)       [1:N, CASCADE delete, nullable]

conversations (1)
       │
       └──→ messages (*)        [1:N, CASCADE delete]

transcripts (1)
       │
       └──→ chunks (*)          [1:N, CASCADE delete]
```

### Core Models

**File:** `backend/app/db/models.py`

#### User
```python
class User(Base):
    id: UUID (PK)
    email: str (unique, indexed)
    password_hash: str (bcrypt)
    created_at, updated_at: DateTime(timezone=True)
    role: str ('user' | 'admin', indexed)
    transcript_count: int (quota tracking)

    Relationships:
    - sessions, conversations, transcripts, chunks, templates
```

#### Conversation
```python
class Conversation(Base):
    id: UUID (PK)
    user_id: UUID (FK → users, CASCADE)
    title: Optional[str]
    created_at, updated_at: DateTime(timezone=True)

    Indexes:
    - idx_conversations_updated_at (DESC for listing)
```

#### Message
```python
class Message(Base):
    id: UUID (PK)
    conversation_id: UUID (FK → conversations, CASCADE)
    role: str ('user' | 'assistant' | 'system')
    content: Text (max 2000 chars)
    meta_data: JSONB (default {})
    created_at: DateTime(timezone=True, indexed)

    Indexes:
    - idx_messages_metadata (GIN on JSONB)
```

#### Transcript
```python
class Transcript(Base):
    id: UUID (PK)
    user_id: UUID (FK → users, CASCADE)
    youtube_video_id: str (50 chars, indexed)
    title: Optional[str]
    channel_name: Optional[str]
    duration: Optional[int] (seconds)
    transcript_text: Text
    meta_data: JSONB (language, etc.)
    created_at: DateTime(timezone=True)

    Constraints:
    - unique_user_video (user_id, youtube_video_id)
```

#### Chunk
```python
class Chunk(Base):
    id: UUID (PK)
    transcript_id: UUID (FK → transcripts, CASCADE)
    user_id: UUID (FK → users, RESTRICT)  # Denormalized
    chunk_text: Text (700 tokens, 20% overlap)
    chunk_index: int (0-based order)
    token_count: int
    meta_data: JSONB
    created_at: DateTime(timezone=True)

    Constraints:
    - unique_chunk_index (transcript_id, chunk_index)

    Indexes:
    - idx_chunks_metadata (GIN)
```

### Supporting Models

#### Session
```python
class Session(Base):
    id: UUID (PK)
    user_id: UUID (FK → users, CASCADE)
    token_hash: str (SHA-256, unique, indexed)
    expires_at: DateTime(timezone=True, indexed)
    created_at: DateTime(timezone=True)
```

#### Template
```python
class Template(Base):
    id: UUID (PK)
    user_id: Optional[UUID] (FK → users, CASCADE, nullable)
    template_type: str ('linkedin', 'twitter', etc.)
    template_name: str
    template_content: Text (Jinja2)
    variables: list (JSONB array)
    is_default: bool
    created_at, updated_at: DateTime(timezone=True)

    Constraints:
    - unique_user_template (user_id, template_type, template_name)
```

#### Config
```python
class Config(Base):
    key: str (PK)
    value: dict (JSONB)
    description: Optional[str]
    updated_at: DateTime(timezone=True)
```

#### ModelPricing
```python
class ModelPricing(Base):
    id: int (PK, autoincrement)
    provider: str ('openrouter', 'openai', 'supadata')
    model_name: str
    pricing_type: str ('per_token' | 'per_request' | 'credit_based')
    input_price_per_1m: Optional[Decimal]
    output_price_per_1m: Optional[Decimal]
    cost_per_request: Optional[Decimal]
    cache_discount: Optional[Decimal]
    effective_from, effective_until: DateTime(timezone=True)
    is_active: bool
```

### Repository Pattern

**Location:** `backend/app/db/repositories/`

All database access abstracted through repositories:

| Repository | Key Methods | File |
|-----------|-------------|------|
| UserRepository | get_by_email, increment_transcript_count | user_repo.py |
| SessionRepository | get_by_token, delete_expired | session_repo.py |
| ConversationRepository | list_by_user, create | conversation_repo.py |
| MessageRepository | create, get_last_n | message_repo.py |
| TranscriptRepository | get_by_video_id, list_by_user | transcript_repo.py |
| ChunkRepository | create_many, get_by_ids | chunk_repo.py |
| TemplateRepository | get_template (with fallback) | template_repo.py |
| ConfigRepository | get_value, set_value (UPSERT) | config_repo.py |
| PricingRepository | get_pricing, get_all_active_pricing | pricing_repo.py |

---

## Vector Storage (Qdrant)

**File:** `backend/app/services/qdrant_service.py`

### Collection Configuration

```python
COLLECTION_NAME = "youtube_chunks"
VECTOR_SIZE = 1536              # OpenAI text-embedding-3-small
DISTANCE_METRIC = "cosine"

Payload Indexes:
- user_id (keyword)
- youtube_video_id (keyword)
```

### Key Operations

#### Upsert Chunks
```python
async def upsert_chunks(
    chunk_ids: List[str],
    vectors: List[List[float]],      # 1536-dim
    user_id: str,
    youtube_video_id: str,
    chunk_indices: List[int],
    chunk_texts: List[str]
) -> None
```

**Payload Structure:**
```python
{
    "chunk_id": str,
    "user_id": str,
    "youtube_video_id": str,
    "chunk_index": int,
    "chunk_text": str
}
```

**Retry:** 3 attempts, exponential backoff (2-10s)

#### Search Chunks
```python
async def search(
    query_vector: List[float],
    user_id: str,                    # REQUIRED for data isolation
    top_k: int = 12,
    youtube_video_id: Optional[str] = None
) -> List[Dict]
```

**Returns:** `[{chunk_id, score, payload}, ...]`

**Filter Logic:**
```python
must_conditions = [
    FieldCondition(key="user_id", match=MatchValue(value=user_id))
]
if youtube_video_id:
    must_conditions.append(
        FieldCondition(key="youtube_video_id", match=MatchValue(value=youtube_video_id))
    )
```

#### Delete Chunks
```python
async def delete_chunks(chunk_ids: List[str]) -> None
```

Used when transcript is deleted (cascade cleanup).

---

## LLM Integration

### Dual Model Architecture

**File:** `backend/app/rag/utils/llm_client.py`

```python
class LLMClient:
    # Claude Haiku 4.5 for text generation
    self.claude = ChatOpenAI(
        model="anthropic/claude-haiku-4.5",
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=2000,
        timeout=30.0
    )

    # Gemini 2.5 Flash for structured JSON
    self.gemini = ChatOpenAI(
        model="google/gemini-2.5-flash",
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.3,  # Low for deterministic output
        model_kwargs={"response_format": {"type": "json_object"}},
        timeout=30.0
    )
```

### Methods

#### ainvoke_claude
```python
async def ainvoke_claude(
    prompt: str,
    user_id: Optional[UUID] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None
) -> str
```

**Purpose:** Text generation (Q&A, LinkedIn posts, chitchat)

#### ainvoke_gemini_structured
```python
async def ainvoke_gemini_structured(
    prompt: str,
    schema: Type[T],  # Pydantic BaseModel
    user_id: Optional[UUID] = None,
    temperature: float = 0.3
) -> T
```

**Purpose:** Structured JSON output (intent classification, chunk grading, subject extraction)

**Process:**
1. Create system prompt with JSON schema
2. Invoke Gemini (response_format=json_object)
3. Parse JSON and validate against Pydantic schema
4. Return validated instance

### LangSmith Integration

- Automatic token usage tracking
- Per-user cost tracking via metadata
- Call tagging with user_id

---

## Key Services

### Embedding Service

**File:** `backend/app/services/embedding_service.py`

```python
class EmbeddingService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY,
            max_retries=3
        )

    async def generate_embeddings(
        texts: List[str],
        user_id: Optional[UUID] = None
    ) -> List[List[float]]:
        # 1. Batch texts in groups of 100
        # 2. Call OpenAI API for each batch
        # 3. Automatic retry via LangChain (max 3)
        # 4. LangSmith tracks with user_id metadata
```

**Configuration:**
- Model: text-embedding-3-small (1536-dim)
- Batch size: 100 texts per request
- Retries: 3 (automatic)

### Chunking Service

**File:** `backend/app/services/chunking_service.py`

```python
async def chunk_transcript(
    transcript_text: str,
    chunk_size: int = 700,
    overlap_percent: int = 20
) -> List[Dict]:
    # 1. Use tiktoken to count tokens
    # 2. Split with overlap (140 tokens for 20%)
    # 3. Ensure minimum size (150 tokens)
    # 4. Return chunks with metadata
```

**Output:**
```python
[
    {
        "chunk_text": str,
        "chunk_index": int,
        "token_count": int,
        "start_index": int,
        "end_index": int
    },
    ...
]
```

### Transcription Service

**File:** `backend/app/services/transcription_service.py`

```python
async def fetch_transcript(youtube_url: str) -> Dict:
    # 1. Extract video_id from URL
    # 2. Call SUPADATA API
    # 3. Parse transcript + metadata
    # 4. Return structured data
```

**SUPADATA Integration:**
- Endpoint: `https://api.supadata.ai/v1/transcribe`
- Retry logic: 3 attempts with exponential backoff
- Timeout: 30 seconds

---

## Architecture Patterns

### 1. Dependency Injection
- FastAPI `Depends()` for database sessions, current user
- Constructor injection for repositories and services

### 2. Repository Pattern
- All database access through repository classes
- Abstracts SQLAlchemy details
- Enables easy testing with mocks

### 3. Async/Await Consistency
- All I/O operations async (database, API calls, Qdrant)
- Use `asyncio.gather()` for parallel operations
- Never `time.sleep()` - use `asyncio.sleep()`

### 4. Error Handling
- Custom exceptions: `AuthenticationError`, `ConversationNotFoundError`, etc.
- Exception handlers registered in FastAPI app
- Structured error responses with request_id

### 5. Data Isolation
- All queries filter by `user_id`
- Qdrant searches enforce user_id filter
- Ownership verification before delete operations

### 6. Retry Logic
- LangGraph flows: 3 attempts with exponential backoff
- Qdrant operations: @retry decorator
- LLM calls: LangChain automatic retry

---

## Complete Data Flow Examples

### Example 1: Q&A Intent Flow

```
1. USER → WebSocket
   Content: "What did the video say about FastAPI?"
   Token: <session_token>

2. WEBSOCKET HANDLER (chat_handler.py)
   - Authenticate user via token
   - Auto-create/verify conversation
   - Load RAG config from database (top_k=12, context_messages=10)
   - Fetch last 10 messages as context

3. CALL run_graph() (router.py)
   Input: {
     "user_query": "What did the video say about FastAPI?",
     "user_id": "user-uuid",
     "conversation_history": [
       {"role": "user", "content": "..."},
       {"role": "assistant", "content": "..."}
     ],
     "config": {"top_k": 12, "context_messages": 10}
   }

4. CLASSIFY INTENT (router_node.py)
   - Render query_router.jinja2
   - Call Gemini with IntentClassification schema
   - Result: {"intent": "qa", "confidence": 0.95, ...}

5. ROUTE TO QA FLOW (qa_flow.py)

   a) RETRIEVE (retriever.py)
      - Generate embedding for query (1536-dim)
      - Search Qdrant with user_id filter, top_k=12
      - Result: 12 chunks with text, score, video_id
      - Update state["retrieved_chunks"]

   b) GRADE (grader.py)
      - For each chunk:
        - Render chunk_grader.jinja2
        - Call Gemini with RelevanceGrade schema
        - Keep if is_relevant=True
      - Result: 8 relevant chunks (example)
      - Update state["graded_chunks"]

   c) GENERATE (generator.py)
      - Render rag_qa.jinja2 with graded chunks + history
      - Call Claude Haiku with max_tokens=2000
      - Result: "FastAPI is a modern Python framework..."
      - Update state["response"]

6. RETURN STATE
   {
     "response": "<p>FastAPI is a modern...</p>",
     "intent": "qa",
     "metadata": {
       "intent_confidence": 0.95,
       "chunks_used": 8,
       "source_chunks": ["chunk-uuid-1", ...],
       "response_type": "qa"
     }
   }

7. SAVE TO DATABASE (chat_handler.py)
   - Create user message: role="user", content=original query
   - Create assistant message: role="assistant", content=response
   - Update conversation.updated_at
   - Commit transaction

8. SEND TO CLIENT (WebSocket)
   {
     "type": "assistant",
     "content": "<p>FastAPI is a modern...</p>",
     "metadata": {"chunks_used": 8, "sources": [...]}
   }
```

### Example 2: Metadata Search Flow

```
1. USER QUERY: "Find videos about machine learning"

2. CLASSIFY INTENT
   - Result: "metadata_search" (confidence: 0.92)

3. METADATA SEARCH FLOW

   a) SUBJECT EXTRACTOR (subject_extractor_node.py)
      - Render subject_extractor.jinja2
      - Call Gemini with SubjectExtraction schema
      - Result: {"subject": "machine learning", "confidence": 0.95}

   b) VIDEO SEARCH NODE (video_search_node.py)
      - Generate embedding for "machine learning"
      - Search Qdrant (top-100 for more coverage)
      - Group chunks by youtube_video_id, calculate avg score
      - Query database for top-20 videos
      - Sort by relevance score DESC
      - Format as HTML list with:
        - Video title
        - Channel name
        - Duration
        - Relevance score (percentage)

4. RETURN RESPONSE
   HTML formatted list of videos with relevance scores
```

---

## Configuration

### Environment Variables

**File:** `backend/.env`

```bash
# Application
ENV=development
DEBUG=True

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/youtube_talker

# Qdrant
QDRANT_URL=http://localhost:6335
QDRANT_API_KEY=

# OpenRouter (LLM completions)
OPENROUTER_API_KEY=<key>
OPENROUTER_CLAUDE_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_GEMINI_MODEL=google/gemini-2.5-flash

# OpenAI (Embeddings)
OPENAI_API_KEY=<key>
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# RAG Defaults (prefer database ConfigService)
RAG_TOP_K=12
RAG_CONTEXT_MESSAGES=10
CHUNK_SIZE=700
CHUNK_OVERLAP_PERCENT=20

# LangSmith
LANGSMITH_API_KEY=<key>
LANGSMITH_PROJECT=youtube-talker
LANGSMITH_TRACING=False
```

### Database Config Table

**Preferred over environment variables (runtime configurable)**

```sql
SELECT * FROM config;

key                    | value
-----------------------|-------
max_context_messages   | 10
rag_top_k              | 12
chunk_size             | 700
chunk_overlap_percent  | 20
session_expires_days   | 7
```

---

## File Locations Reference

### Core API & WebSocket
```
backend/app/
├── main.py                                  # FastAPI app, WebSocket route
├── api/
│   ├── routes/
│   │   ├── conversations.py                 # REST endpoints for conversations
│   │   ├── auth.py                          # Register, login, logout
│   │   ├── transcripts.py                   # Ingest YouTube URLs
│   │   └── health.py                        # Health checks
│   └── websocket/
│       └── chat_handler.py                  # WebSocket chat logic
```

### RAG Implementation
```
backend/app/rag/
├── graphs/
│   ├── router.py                            # Main entry: run_graph()
│   └── flows/
│       ├── chitchat_flow.py
│       ├── qa_flow.py
│       ├── linkedin_flow.py
│       ├── metadata_flow.py
│       ├── metadata_search_flow.py
│       └── video_load_flow.py
├── nodes/
│   ├── router_node.py                       # Intent classification
│   ├── retriever.py                         # Qdrant search
│   ├── grader.py                            # Chunk relevance
│   ├── generator.py                         # Response generation
│   ├── metadata_node.py                     # List all videos
│   ├── subject_extractor_node.py            # Extract search subject
│   └── video_search_node.py                 # Semantic video search
├── prompts/
│   ├── query_router.jinja2                  # Intent classification prompt
│   ├── chunk_grader.jinja2                  # Relevance grading prompt
│   ├── rag_qa.jinja2                        # Q&A generation prompt
│   ├── linkedin_post_generate.jinja2        # LinkedIn post prompt
│   ├── chitchat_flow.jinja2                 # Casual chat prompt
│   └── subject_extractor.jinja2             # Subject extraction prompt
└── utils/
    ├── llm_client.py                        # Dual LLM client (Claude + Gemini)
    └── state.py                             # GraphState TypedDict
```

### Database Layer
```
backend/app/db/
├── models.py                                # SQLAlchemy ORM models (9 models)
├── session.py                               # DB session management
└── repositories/
    ├── base.py                              # BaseRepository generic
    ├── user_repo.py
    ├── session_repo.py
    ├── conversation_repo.py
    ├── message_repo.py
    ├── transcript_repo.py
    ├── chunk_repo.py
    ├── template_repo.py
    ├── config_repo.py
    └── pricing_repo.py
```

### Services
```
backend/app/services/
├── qdrant_service.py                        # Vector DB operations
├── embedding_service.py                     # OpenAI embeddings
├── chunking_service.py                      # Transcript chunking
├── transcription_service.py                 # SUPADATA API integration
└── auth_service.py                          # Password hashing, session mgmt
```

### Schemas (Pydantic)
```
backend/app/schemas/
├── llm_responses.py                         # IntentClassification, RelevanceGrade, etc.
├── conversation.py                          # Request/response models
├── message.py
├── transcript.py
└── user.py
```

### Migrations
```
backend/alembic/versions/
├── fcd6e385eb69_initial_schema.py
├── 2b4a2190f4a6_fix_youtube_video_id_unique.py
├── 1a95e025e49d_add_user_role_and_transcript_count.py
├── aa2f19886ae7_add_transcript_count_check_constraint.py
├── 4e67c9eefea6_add_model_pricing_table.py
└── 9660aa8618fd_remove_template_type_constraint.py
```

---

## Summary Statistics

| Component | Count | Notes |
|-----------|-------|-------|
| **REST Endpoints** | 12+ | Auth, conversations, transcripts, health |
| **WebSocket Endpoints** | 1 | /api/ws/chat |
| **Intent Types** | 6 | chitchat, qa, linkedin, metadata, metadata_search, video_load |
| **LangGraph Flows** | 6 | One per intent |
| **LangGraph Nodes** | 7 | Router, Retriever, Grader, Generator, Metadata, SubjectExtractor, VideoSearch |
| **Database Tables** | 9 | Core + system |
| **SQLAlchemy Models** | 9 | 1:1 with tables |
| **Repositories** | 9 | Repository pattern |
| **Prompt Templates** | 6 | Jinja2 templates |
| **LLM Models** | 2 | Claude Haiku 4.5, Gemini 2.5 Flash |
| **Vector Dimensions** | 1536 | OpenAI text-embedding-3-small |
| **Qdrant Collections** | 1 | youtube_chunks |
| **Foreign Keys** | 8 | Carefully designed CASCADE/RESTRICT |
| **Indexes** | ~40 | Strategic placement |

---

## Key Design Decisions

### 1. Dual LLM Strategy
- **Claude:** Natural text generation (conversational, markdown)
- **Gemini:** Structured JSON output (classification, grading)
- **Rationale:** Best tool for each job, cost optimization

### 2. Denormalized user_id in Chunks
- **Trade-off:** Slight redundancy for fast Qdrant → DB lookups
- **Benefit:** No join with transcripts table
- **Protection:** FK uses RESTRICT to prevent multi-cascade conflicts

### 3. Binary Chunk Grading
- **Simpler than scoring:** relevant/not_relevant
- **Effective for MVP:** LLM decides per chunk
- **Extensible:** Can add confidence scores later

### 4. LangGraph over Pure LangChain
- **Stateful flows:** GraphState passed between nodes
- **Easier to extend:** Add new intents/flows without refactoring
- **Retry logic:** Per-node configuration

### 5. Server-Side Sessions
- **Not JWT:** Simpler for MVP, easier revocation
- **7-day expiry:** Automatic cleanup via background job
- **Token hash:** SHA-256 stored in DB (not raw token)

### 6. 700 Token Chunks with 20% Overlap
- **Balance:** Context vs. retrieval precision
- **Overlap:** Prevents cutting sentences mid-thought
- **Minimum size:** 150 tokens (append to previous if smaller)

### 7. Conversation History (Last 10 Messages)
- **Configurable:** Via database config table
- **Trade-off:** Balance between context and token usage
- **Memory:** Provides coherent multi-turn conversations

---

## Next Steps for New Functionality

### Before Adding Features:
1. **Understand dependencies:** Which nodes/flows will be affected?
2. **Plan new intents:** Does this require a new intent type?
3. **Database changes:** New tables? New fields? Migrations needed?
4. **RAG impact:** Will this use retrieval? Grading? New prompts?
5. **API design:** REST endpoint? WebSocket message type? Both?
6. **Testing strategy:** Unit tests for new nodes, integration tests for flows

### Typical Extension Points:
- **New Intent:** Add to `router_node.py`, create new flow in `flows/`, add prompt template
- **New Node:** Create in `nodes/`, add to appropriate flow(s)
- **New Endpoint:** Add route in `api/routes/`, create Pydantic schemas
- **New Model:** Add to `models.py`, create migration, add repository

---

**Last Updated:** 2025-11-03
**Next Review:** Before major feature additions
