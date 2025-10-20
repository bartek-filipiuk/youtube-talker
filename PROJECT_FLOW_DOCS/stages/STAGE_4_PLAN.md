# Phase 4: Transcript Ingestion Pipeline - Implementation Plan

**Version:** 1.0
**Last Updated:** 2025-10-20
**Stages:** 4.1 - 4.7
**Dependencies:** Phase 3 completed (authentication working)

---

## Executive Summary

**Goal:** Build complete YouTube transcript ingestion pipeline: URL → SUPADATA API → Chunking → Embeddings → PostgreSQL + Qdrant

**PR Strategy:** Split into 3 logical, reviewable pull requests:
- **PR #5:** Foundational Services (4.1 + 4.2) - ~200-300 LOC
- **PR #6:** Vector Infrastructure (4.3 + 4.4) - ~250-350 LOC
- **PR #7:** Full Pipeline (4.5 + 4.6 + 4.7) - ~300-400 LOC

**Key Decisions** (from user clarifications):
- ✅ Use real SUPADATA API key (mock in tests)
- ✅ Support both YouTube URL formats: `youtube.com/watch?v=ID` and `youtu.be/ID`
- ✅ Duplicate handling: Return **409 Conflict** with message "Already ingested"
- ✅ Short transcripts (< 700 tokens): Keep as **single chunk**
- ✅ Pipeline failures: **Keep partial data** (transcript + any saved chunks)
- ✅ Qdrant collection: Create via **setup script** (production-ready)

**Retry Strategy:** See `LANGCHAIN_RETRY.md` - Use **tenacity** library for all external APIs in Phase 4.

---

## PR #5: Foundational Services (4.1 + 4.2)

**Goal:** Build SUPADATA client and chunking service - independent, testable utilities

**Files to Create:**

### 1. `app/services/transcript_service.py`

**Purpose:** SUPADATA API client for fetching YouTube transcripts

**Class:** `TranscriptService`

**Methods:**

```python
class TranscriptService:
    def __init__(self):
        """Initialize with SUPADATA credentials from settings."""
        self.api_key = settings.SUPADATA_API_KEY
        self.base_url = settings.SUPADATA_BASE_URL
        self.timeout = 30.0

    async def fetch_transcript(self, youtube_url: str) -> Dict:
        """
        Fetch transcript from SUPADATA API with retry logic.

        Args:
            youtube_url: YouTube URL (youtube.com/watch?v=ID or youtu.be/ID)

        Returns:
            {
                "youtube_video_id": str,
                "transcript_text": str,
                "metadata": {
                    "title": str,
                    "duration": int,
                    "language": str,
                    ...
                }
            }

        Raises:
            ValueError: If URL format is invalid
            httpx.HTTPError: If API request fails after retries

        Retry Strategy:
            - Max attempts: 3
            - Wait: Exponential backoff (2s, 4s, 8s)
            - Retry on: httpx.HTTPError, httpx.TimeoutException
        """
        pass

    def _extract_video_id(self, url: str) -> str:
        """
        Extract video ID from YouTube URL.

        Supports:
            - https://www.youtube.com/watch?v=VIDEO_ID
            - https://youtube.com/watch?v=VIDEO_ID
            - https://youtu.be/VIDEO_ID

        Raises:
            ValueError: If URL doesn't match expected patterns
        """
        pass
```

**Implementation Details:**
- Use `httpx.AsyncClient` for async HTTP requests
- Use `tenacity` decorator for retry logic:
  ```python
  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=2, max=10),
      retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
  )
  ```
- Regex patterns for URL parsing:
  ```python
  patterns = [
      r'(?:youtube\.com\/watch\?v=)([\w-]+)',
      r'(?:youtu\.be\/)([\w-]+)'
  ]
  ```
- Set timeout to 30 seconds (SUPADATA can be slow for long videos)
- Pass API key in `Authorization: Bearer` header

---

### 2. `app/services/chunking_service.py`

**Purpose:** Token-based text chunking with sliding window overlap

**Class:** `ChunkingService`

**Constructor:**
```python
def __init__(
    self,
    chunk_size: int = 700,         # From config: 700 tokens
    overlap_percent: int = 20,      # From config: 20% overlap = 140 tokens
    min_chunk_size: int = 150       # Minimum viable chunk
):
    self.chunk_size = chunk_size
    self.overlap_tokens = int(chunk_size * overlap_percent / 100)
    self.min_chunk_size = min_chunk_size
    self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
```

**Methods:**

```python
def chunk_text(self, text: str) -> List[Dict]:
    """
    Chunk text into overlapping segments using token-based sliding window.

    Args:
        text: Full transcript text

    Returns:
        List of dicts with keys:
            - text: str (chunk content)
            - token_count: int (actual token count)
            - index: int (sequential 0, 1, 2, ...)

    Example:
        [
            {"text": "First chunk...", "token_count": 700, "index": 0},
            {"text": "Second chunk...", "token_count": 685, "index": 1}
        ]

    Behavior:
        - If total_tokens <= chunk_size: Return single chunk
        - If last chunk < min_chunk_size: Merge with previous chunk
        - Window slides by (chunk_size - overlap_tokens)
    """
    pass
```

**Algorithm:**
1. Encode full text to tokens using tiktoken
2. Check if text fits in single chunk (< 700 tokens):
   - YES → Return single chunk with index 0
   - NO → Continue with sliding window
3. Sliding window loop:
   - Start at position 0
   - Take next chunk_size tokens (700)
   - Decode tokens back to text
   - Check if this is last chunk AND too small (< 150 tokens):
     - YES → Merge with previous chunk
     - NO → Add as separate chunk
   - Move start forward by `chunk_size - overlap_tokens` (560 tokens)
   - Repeat until end of text

**Edge Cases:**
- Empty text → Return empty list
- Text < 150 tokens → Return single chunk
- Text = 701 tokens → Return 2 chunks (first 700, last 141 merged into first)
- Very long transcript (10,000 tokens) → ~18 chunks with overlap

---

### 3. `app/schemas/transcript.py`

**Purpose:** Pydantic schemas for transcript API

**Schemas:**

```python
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any
import re

class TranscriptIngestRequest(BaseModel):
    """Request schema for transcript ingestion."""
    youtube_url: str = Field(
        ...,
        description="YouTube video URL (youtube.com or youtu.be format)",
        examples=["https://youtube.com/watch?v=dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ"]
    )

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate YouTube URL format."""
        patterns = [
            r'(?:youtube\.com\/watch\?v=)([\w-]+)',
            r'(?:youtu\.be\/)([\w-]+)'
        ]
        if not any(re.search(p, v) for p in patterns):
            raise ValueError(
                "Invalid YouTube URL format. "
                "Expected: youtube.com/watch?v=ID or youtu.be/ID"
            )
        return v

class TranscriptResponse(BaseModel):
    """Response schema for successful ingestion."""
    id: str = Field(..., description="Transcript database ID (UUID)")
    youtube_video_id: str = Field(..., description="YouTube video ID extracted from URL")
    chunk_count: int = Field(..., description="Number of chunks created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Video metadata from SUPADATA")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "youtube_video_id": "dQw4w9WgXcQ",
                "chunk_count": 12,
                "metadata": {
                    "title": "Rick Astley - Never Gonna Give You Up",
                    "duration": 213,
                    "language": "en"
                }
            }
        }
```

---

### 4. Tests

#### `tests/unit/test_transcript_service.py`

**Test Cases:**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.transcript_service import TranscriptService
import httpx

class TestTranscriptService:
    """Unit tests for TranscriptService."""

    @pytest.mark.asyncio
    async def test_extract_video_id_youtube_com(self):
        """Extract video ID from youtube.com URL."""
        service = TranscriptService()
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_extract_video_id_youtu_be(self):
        """Extract video ID from youtu.be URL."""
        service = TranscriptService()
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_extract_video_id_invalid_url(self):
        """Raise ValueError for invalid URL."""
        service = TranscriptService()
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            service._extract_video_id("https://vimeo.com/123456")

    @pytest.mark.asyncio
    async def test_fetch_transcript_success(self):
        """Test successful transcript fetch with mocked API."""
        service = TranscriptService()

        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "transcript": "This is the transcript text.",
            "metadata": {
                "title": "Test Video",
                "duration": 120,
                "language": "en"
            }
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await service.fetch_transcript("https://youtube.com/watch?v=TEST123")

        assert result["youtube_video_id"] == "TEST123"
        assert result["transcript_text"] == "This is the transcript text."
        assert result["metadata"]["title"] == "Test Video"

    @pytest.mark.asyncio
    async def test_fetch_transcript_retry_on_timeout(self):
        """Test retry logic on timeout."""
        service = TranscriptService()

        # First call fails, second succeeds
        mock_responses = [
            httpx.TimeoutException("Request timeout"),
            AsyncMock(
                json=lambda: {"transcript": "Success after retry", "metadata": {}},
                raise_for_status=lambda: None
            )
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=mock_responses
            )

            result = await service.fetch_transcript("https://youtube.com/watch?v=RETRY")

        assert result["transcript_text"] == "Success after retry"
        # Verify retry happened (2 calls)
        assert mock_client.return_value.__aenter__.return_value.post.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_transcript_api_error(self):
        """Test handling of API errors after retries exhausted."""
        service = TranscriptService()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Server Error",
                    request=AsyncMock(),
                    response=AsyncMock(status_code=500)
                )
            )

            with pytest.raises(httpx.HTTPStatusError):
                await service.fetch_transcript("https://youtube.com/watch?v=ERROR")
```

**Coverage Target:** > 80% for `transcript_service.py`

---

#### `tests/unit/test_chunking_service.py`

**Test Cases:**

```python
import pytest
from app.services.chunking_service import ChunkingService

class TestChunkingService:
    """Unit tests for ChunkingService."""

    def test_chunk_short_text_single_chunk(self):
        """Text shorter than chunk_size stays as single chunk."""
        service = ChunkingService(chunk_size=700)
        text = "Short text. " * 10  # ~100 tokens

        chunks = service.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0]["index"] == 0
        assert chunks[0]["token_count"] < 700
        assert chunks[0]["text"] == text

    def test_chunk_empty_text(self):
        """Empty text returns empty list."""
        service = ChunkingService()
        chunks = service.chunk_text("")
        assert chunks == []

    def test_chunk_long_text_with_overlap(self):
        """Long text creates multiple overlapping chunks."""
        service = ChunkingService(chunk_size=100, overlap_percent=20)
        text = "word " * 500  # ~500 tokens

        chunks = service.chunk_text(text)

        assert len(chunks) > 1
        # Check first chunk is ~100 tokens
        assert 90 <= chunks[0]["token_count"] <= 110
        # Check overlap exists (later chunks start before previous ends)
        # This is implicit in the sliding window algorithm

    def test_chunk_indices_sequential(self):
        """Chunk indices are sequential starting from 0."""
        service = ChunkingService(chunk_size=100)
        text = "word " * 500

        chunks = service.chunk_text(text)

        for i, chunk in enumerate(chunks):
            assert chunk["index"] == i

    def test_chunk_last_too_small_merges(self):
        """Last chunk smaller than min_chunk_size merges with previous."""
        service = ChunkingService(chunk_size=100, min_chunk_size=50)
        # Create text that will produce a tiny last chunk
        text = "word " * 102  # ~102 tokens -> should create 2 chunks, last tiny

        chunks = service.chunk_text(text)

        # If last chunk was < 50 tokens, it should merge with previous
        # Total chunks should be less than expected without merging
        assert all(chunk["token_count"] >= 50 or len(chunks) == 1 for chunk in chunks)

    def test_chunk_exact_boundary(self):
        """Text exactly chunk_size tokens."""
        service = ChunkingService(chunk_size=100)
        # Create text of exactly 100 tokens (approximate)
        text = "word " * 100
        chunks = service.chunk_text(text)

        # Should be 1 chunk since it fits exactly
        assert len(chunks) >= 1

    def test_custom_chunk_size_and_overlap(self):
        """Test with custom chunk size and overlap."""
        service = ChunkingService(chunk_size=50, overlap_percent=10)
        text = "word " * 200

        chunks = service.chunk_text(text)

        assert len(chunks) > 1
        # Overlap is 5 tokens (10% of 50)
        # Window slides by 45 tokens each time
```

**Coverage Target:** > 80% for `chunking_service.py`

---

### Acceptance Criteria for PR #5:

- [ ] SUPADATA client extracts video IDs from both URL formats
- [ ] Invalid URLs raise `ValueError` with descriptive message
- [ ] Retry logic works (test with mocked transient failures)
- [ ] Chunking produces chunks with target size ~700 tokens
- [ ] Chunking implements 20% overlap correctly
- [ ] Short transcripts (< 700 tokens) kept as single chunk
- [ ] Last chunk < 150 tokens merges with previous
- [ ] All unit tests pass
- [ ] Test coverage > 80% for both services
- [ ] Code passes linting (`ruff check`)
- [ ] Type hints present for all functions
- [ ] Docstrings follow Google style

**Dependencies:** None (independent services)

**Estimated LOC:** 200-300

---

## PR #6: Vector Infrastructure (4.3 + 4.4)

**Goal:** Build embedding and Qdrant services - tightly coupled vector infrastructure

**Files to Create:**

### 1. `app/services/embedding_service.py`

**Purpose:** OpenRouter embeddings API client with batching

**Class:** `EmbeddingService`

**Methods:**

```python
class EmbeddingService:
    def __init__(self):
        """Initialize with OpenRouter credentials."""
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_EMBEDDING_MODEL  # "openai/text-embedding-3-small"
        self.batch_size = 100  # Max texts per API request
        self.timeout = 30.0

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for list of texts with automatic batching.

        Args:
            texts: List of text strings to embed (can be any length)

        Returns:
            List of 1024-dimensional vectors (one per input text)
            Example: [[0.1, 0.2, ..., 0.5], [0.3, 0.1, ..., 0.8]]

        Raises:
            httpx.HTTPError: If API request fails after retries

        Retry Strategy:
            - Max attempts: 3
            - Wait: Exponential backoff (2s, 4s, 8s)
            - Retry on: httpx.HTTPError, httpx.TimeoutException

        Performance:
            - Batches requests in groups of 100 texts
            - Parallel batching not implemented (sequential for MVP)
        """
        pass

    async def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a single batch (≤ 100 texts).

        Internal method with retry decorator.
        """
        pass
```

**Implementation Details:**
- Use `httpx.AsyncClient` for async HTTP
- Batch processing: Split large inputs into 100-text chunks
- Tenacity retry on `_embed_batch` method
- OpenRouter API endpoint: `https://openrouter.ai/api/v1/embeddings`
- Request format:
  ```json
  {
    "model": "openai/text-embedding-3-small",
    "input": ["text1", "text2", ...]
  }
  ```
- Response format:
  ```json
  {
    "data": [
      {"embedding": [0.1, 0.2, ..., 0.5]},
      {"embedding": [0.3, 0.1, ..., 0.8]}
    ]
  }
  ```
- Extract embeddings from response and flatten into single list

---

### 2. `app/services/qdrant_service.py`

**Purpose:** Qdrant vector database client for chunk storage and search

**Class:** `QdrantService`

**Constants:**
```python
COLLECTION_NAME = "youtube_chunks"
VECTOR_SIZE = 1024
```

**Methods:**

```python
class QdrantService:
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(url=settings.QDRANT_URL)

    async def create_collection(self) -> None:
        """
        Create youtube_chunks collection with indexes.

        Idempotent: No-op if collection already exists.

        Collection Config:
            - Vectors: 1024-dim, cosine distance
            - Payload indexes: user_id (keyword), youtube_video_id (keyword)
        """
        pass

    async def upsert_chunks(
        self,
        chunk_ids: List[str],
        vectors: List[List[float]],
        user_id: str,
        youtube_video_id: str,
        chunk_indices: List[int]
    ) -> None:
        """
        Batch upsert chunks to Qdrant.

        Args:
            chunk_ids: List of chunk UUIDs (from PostgreSQL)
            vectors: List of 1024-dim embeddings
            user_id: User UUID (for filtering)
            youtube_video_id: YouTube video ID (for filtering)
            chunk_indices: Chunk sequence numbers (0, 1, 2, ...)

        Creates points with payload:
            {
                "chunk_id": str,
                "user_id": str,
                "youtube_video_id": str,
                "chunk_index": int
            }

        Note: chunk_id is used as both point ID and in payload
        """
        pass

    async def search(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int = 12,
        youtube_video_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Semantic search with user ID filtering.

        Args:
            query_vector: 1024-dim query embedding
            user_id: Filter by user (REQUIRED for data isolation)
            top_k: Number of results (default: 12 from config)
            youtube_video_id: Optional filter by specific video

        Returns:
            List of dicts sorted by score (descending):
            [
                {
                    "chunk_id": "uuid-string",
                    "score": 0.95,
                    "payload": {
                        "chunk_id": "uuid-string",
                        "user_id": "user-uuid",
                        "youtube_video_id": "VIDEO_ID",
                        "chunk_index": 0
                    }
                },
                ...
            ]

        Filter Logic:
            - ALWAYS filter by user_id (data isolation)
            - Optionally filter by youtube_video_id (single video search)
        """
        pass

    async def delete_chunks(self, chunk_ids: List[str]) -> None:
        """
        Delete chunks by IDs.

        Args:
            chunk_ids: List of chunk UUIDs to delete

        Use Case: Clean up when transcript is deleted
        """
        pass

    async def health_check(self) -> bool:
        """
        Verify Qdrant connection.

        Returns:
            True if connected, False otherwise

        Used by health check endpoint.
        """
        pass
```

**Implementation Details:**
- Use `qdrant-client` library (already installed)
- Collection creation:
  ```python
  self.client.create_collection(
      collection_name=self.COLLECTION_NAME,
      vectors_config=VectorParams(
          size=self.VECTOR_SIZE,
          distance=Distance.COSINE
      )
  )
  ```
- Payload indexes:
  ```python
  self.client.create_payload_index(
      collection_name=self.COLLECTION_NAME,
      field_name="user_id",
      field_schema="keyword"
  )
  ```
- Upsert points:
  ```python
  points = [
      PointStruct(
          id=chunk_id,
          vector=vector,
          payload={"chunk_id": chunk_id, "user_id": user_id, ...}
      )
      for chunk_id, vector in zip(chunk_ids, vectors)
  ]
  self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)
  ```
- Search with filters:
  ```python
  results = self.client.search(
      collection_name=self.COLLECTION_NAME,
      query_vector=query_vector,
      query_filter=Filter(
          must=[
              FieldCondition(key="user_id", match=MatchValue(value=user_id))
          ]
      ),
      limit=top_k
  )
  ```

---

### 3. `scripts/setup_qdrant.py`

**Purpose:** Setup script to create Qdrant collection

```python
"""Setup script to create Qdrant collection for youtube_chunks."""
import asyncio
from app.services.qdrant_service import QdrantService

async def main():
    """Create Qdrant collection if it doesn't exist."""
    print("Setting up Qdrant collection...")

    service = QdrantService()
    await service.create_collection()

    print("✓ Qdrant collection 'youtube_chunks' created successfully")
    print("  - Vector size: 1024")
    print("  - Distance: Cosine")
    print("  - Indexes: user_id, youtube_video_id")

if __name__ == "__main__":
    asyncio.run(main())
```

**Usage:**
```bash
cd backend
python scripts/setup_qdrant.py
```

---

### 4. Tests

#### `tests/unit/test_embedding_service.py`

**Test Cases:**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.embedding_service import EmbeddingService

class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_generate_embeddings_single_batch(self):
        """Test embedding generation for texts within batch size."""
        service = EmbeddingService()
        texts = ["text one", "text two", "text three"]

        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1024},
                {"embedding": [0.2] * 1024},
                {"embedding": [0.3] * 1024}
            ]
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            embeddings = await service.generate_embeddings(texts)

        assert len(embeddings) == 3
        assert len(embeddings[0]) == 1024
        assert embeddings[0][0] == 0.1

    @pytest.mark.asyncio
    async def test_generate_embeddings_multiple_batches(self):
        """Test batching for > 100 texts."""
        service = EmbeddingService()
        texts = [f"text {i}" for i in range(250)]  # 3 batches

        # Mock responses for 3 batches
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1024} for _ in range(100)]
        }
        mock_response.raise_for_status = lambda: None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            embeddings = await service.generate_embeddings(texts)

        assert len(embeddings) == 250
        # Verify 3 API calls were made (3 batches)
        assert mock_client.return_value.__aenter__.return_value.post.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_embeddings_retry_on_error(self):
        """Test retry logic on API error."""
        service = EmbeddingService()
        texts = ["test"]

        # First call fails, second succeeds
        mock_responses = [
            httpx.TimeoutException("Timeout"),
            AsyncMock(
                json=lambda: {"data": [{"embedding": [0.5] * 1024}]},
                raise_for_status=lambda: None
            )
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=mock_responses
            )

            embeddings = await service.generate_embeddings(texts)

        assert len(embeddings) == 1
        assert embeddings[0][0] == 0.5
```

#### `tests/integration/test_qdrant_service.py`

**Test Cases:** (requires running Qdrant instance)

```python
import pytest
from app.services.qdrant_service import QdrantService
from uuid import uuid4

class TestQdrantService:
    @pytest.mark.asyncio
    async def test_create_collection_idempotent(self):
        """Test collection creation is idempotent."""
        service = QdrantService()

        # First creation
        await service.create_collection()

        # Second creation (should not error)
        await service.create_collection()

        assert await service.health_check()

    @pytest.mark.asyncio
    async def test_upsert_and_search(self):
        """Test upserting chunks and searching."""
        service = QdrantService()
        await service.create_collection()

        # Upsert test chunks
        chunk_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        vectors = [
            [0.1] * 1024,  # Similar to query
            [0.5] * 1024,  # Less similar
            [0.9] * 1024   # Least similar
        ]
        user_id = "test-user-123"
        video_id = "VIDEO123"

        await service.upsert_chunks(
            chunk_ids=chunk_ids,
            vectors=vectors,
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0, 1, 2]
        )

        # Search with similar vector
        query_vector = [0.15] * 1024
        results = await service.search(
            query_vector=query_vector,
            user_id=user_id,
            top_k=5
        )

        assert len(results) == 3
        # First result should be most similar
        assert results[0]["chunk_id"] == chunk_ids[0]
        assert results[0]["payload"]["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_search_filters_by_user_id(self):
        """Test user ID filtering works."""
        service = QdrantService()
        await service.create_collection()

        # Upsert chunks for two different users
        chunk_id_user1 = str(uuid4())
        chunk_id_user2 = str(uuid4())

        await service.upsert_chunks(
            chunk_ids=[chunk_id_user1],
            vectors=[[0.1] * 1024],
            user_id="user-1",
            youtube_video_id="VIDEO1",
            chunk_indices=[0]
        )

        await service.upsert_chunks(
            chunk_ids=[chunk_id_user2],
            vectors=[[0.1] * 1024],
            user_id="user-2",
            youtube_video_id="VIDEO2",
            chunk_indices=[0]
        )

        # Search for user-1 only
        results = await service.search(
            query_vector=[0.1] * 1024,
            user_id="user-1",
            top_k=10
        )

        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk_id_user1

    @pytest.mark.asyncio
    async def test_delete_chunks(self):
        """Test chunk deletion."""
        service = QdrantService()
        await service.create_collection()

        chunk_id = str(uuid4())
        await service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[[0.1] * 1024],
            user_id="user-1",
            youtube_video_id="VIDEO1",
            chunk_indices=[0]
        )

        # Delete chunk
        await service.delete_chunks([chunk_id])

        # Search should return empty
        results = await service.search(
            query_vector=[0.1] * 1024,
            user_id="user-1"
        )

        assert len(results) == 0
```

---

### Acceptance Criteria for PR #6:

- [ ] Embeddings return 1024-dimensional vectors
- [ ] Batching works correctly (100 texts per request)
- [ ] Large inputs (> 100 texts) processed in multiple batches
- [ ] Retry logic works for embedding API
- [ ] Qdrant collection created with correct vector size (1024)
- [ ] Qdrant collection uses cosine distance
- [ ] Payload indexes created for user_id and youtube_video_id
- [ ] Upsert and search work correctly
- [ ] Search filters by user_id correctly (data isolation)
- [ ] Optional youtube_video_id filter works
- [ ] Delete operation removes chunks
- [ ] Health check returns True when Qdrant is accessible
- [ ] Setup script runs successfully
- [ ] All tests pass (unit + integration)
- [ ] Test coverage > 80%
- [ ] Code passes linting
- [ ] Type hints present

**Dependencies:** PR #5 merged (no code dependencies, but logical sequence)

**Estimated LOC:** 250-350

---

## PR #7: Full Pipeline Integration (4.5 + 4.6 + 4.7)

**Goal:** Orchestrate full pipeline, expose API endpoint, create seed script

**Files to Create/Update:**

### 1. Update `app/services/transcript_service.py`

**Add method:**

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
        1. Fetch transcript from SUPADATA
        2. Check for duplicate (by youtube_video_id + user_id)
        3. Save transcript to PostgreSQL
        4. Chunk the transcript text
        5. Generate embeddings for chunks
        6. Save chunks to PostgreSQL
        7. Upsert vectors to Qdrant

    Args:
        youtube_url: YouTube URL
        user_id: User UUID (for ownership)
        db_session: Database session (for transaction)

    Returns:
        {
            "transcript_id": str,
            "youtube_video_id": str,
            "chunk_count": int,
            "metadata": dict
        }

    Raises:
        ValueError: If video already ingested (duplicate)
        Exception: If pipeline fails (partial data kept)

    Transaction Handling:
        - Commits after saving transcript
        - Commits after saving all chunks
        - Does NOT rollback on Qdrant failure (keeps PostgreSQL data)

    Error Handling Strategy (per user preference):
        - On failure: Keep partial data (transcript + any saved chunks)
        - Rationale: User can retry ingestion or manual cleanup
        - Log detailed error info for debugging
    """
    pass
```

**Implementation Notes:**
- Use structured logging (log each step)
- Duplicate check: Query `TranscriptRepository.get_by_video_id_and_user()`
- Raise `ValueError("Transcript for video {video_id} already ingested")`
- Generate UUIDs for chunks using `uuid4()`
- Denormalize user_id in chunks table (for faster queries)
- If Qdrant upsert fails, log error but keep PostgreSQL data
- Return detailed metadata for API response

---

### 2. `app/api/routes/transcripts.py`

**Purpose:** REST API endpoint for transcript ingestion

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies import get_current_user
from app.db.models import User
from app.schemas.transcript import TranscriptIngestRequest, TranscriptResponse
from app.services.transcript_service import TranscriptService
import logging

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])
logger = logging.getLogger(__name__)

@router.post(
    "/ingest",
    response_model=TranscriptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest YouTube transcript",
    description="""
    Ingest a YouTube video transcript through SUPADATA API.

    **Pipeline:**
    1. Fetch transcript from SUPADATA
    2. Chunk into 700-token segments (20% overlap)
    3. Generate embeddings (1024-dim vectors)
    4. Store in PostgreSQL + Qdrant

    **Duplicate Handling:**
    - Returns 409 Conflict if video already ingested by this user

    **Authentication:**
    - Requires valid session token in Authorization header

    **Rate Limiting:**
    - None for MVP (can add in future)
    """
)
async def ingest_transcript(
    request: TranscriptIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest YouTube transcript."""
    service = TranscriptService()

    try:
        logger.info(f"User {current_user.id} ingesting: {request.youtube_url}")

        result = await service.ingest_transcript(
            youtube_url=request.youtube_url,
            user_id=str(current_user.id),
            db_session=db
        )

        logger.info(f"✓ Ingestion complete: {result['chunk_count']} chunks")

        return TranscriptResponse(
            id=result["transcript_id"],
            youtube_video_id=result["youtube_video_id"],
            chunk_count=result["chunk_count"],
            metadata=result["metadata"]
        )

    except ValueError as e:
        # Duplicate video or invalid URL
        if "already ingested" in str(e):
            logger.warning(f"Duplicate ingestion attempt: {request.youtube_url}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )
```

**Update `app/main.py`:**
```python
from app.api.routes import transcripts

app.include_router(transcripts.router)
```

---

### 3. `scripts/seed_database.py`

**Purpose:** Seed database with test data for local development

```python
"""Seed database with test data for local development."""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import User, Template, Config
from app.core.security import hash_password
from app.services.transcript_service import TranscriptService
from app.services.qdrant_service import QdrantService
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Seed test user, templates, config, and sample transcripts."""
    logger.info("Starting database seed...")

    # Create database engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Create test user
        logger.info("Creating test user...")
        user = User(
            email="test@example.com",
            password_hash=hash_password("testpassword123")
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        logger.info(f"✓ Created test user: {user.email} (ID: {user.id})")

        # 2. Seed default LinkedIn template
        logger.info("Creating default LinkedIn template...")
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
            user_id=None,  # Global default
            variables={
                "topic": "str",
                "introduction": "str",
                "key_points": "list",
                "conclusion": "str",
                "hashtags": "list"
            }
        )
        session.add(template)
        logger.info("✓ Created default LinkedIn template")

        # 3. Seed config values
        logger.info("Creating config values...")
        configs = [
            Config(key="max_context_messages", value="10"),
            Config(key="rag_top_k", value="12"),
            Config(key="chunk_size", value="700"),
            Config(key="chunk_overlap_percent", value="20")
        ]
        for config in configs:
            session.add(config)
        logger.info("✓ Created config values")

        await session.commit()
        logger.info("✓ Database seeded successfully")

        # 4. Setup Qdrant collection
        logger.info("Setting up Qdrant collection...")
        qdrant_service = QdrantService()
        await qdrant_service.create_collection()
        logger.info("✓ Qdrant collection created")

        # 5. Ingest sample YouTube transcripts
        # NOTE: For MVP, use mock/test videos or skip this step
        # In production, users will ingest their own videos
        logger.info("Ingesting sample transcripts...")

        # OPTION 1: Use real YouTube URLs (requires SUPADATA API key)
        test_videos = [
            # "https://youtube.com/watch?v=dQw4w9WgXcQ",  # Example
        ]

        # OPTION 2: Skip for now (manual ingestion via API)
        if not test_videos:
            logger.info("⚠ Skipping transcript ingestion (no test videos configured)")
            logger.info("  → Use API endpoint to ingest transcripts manually")
        else:
            transcript_service = TranscriptService()
            for video_url in test_videos:
                try:
                    result = await transcript_service.ingest_transcript(
                        youtube_url=video_url,
                        user_id=str(user.id),
                        db_session=session
                    )
                    logger.info(
                        f"✓ Ingested: {result['youtube_video_id']} "
                        f"({result['chunk_count']} chunks)"
                    )
                except Exception as e:
                    logger.error(f"✗ Failed to ingest {video_url}: {e}")

        logger.info("\n🎉 Seed complete!")
        logger.info(f"\nTest credentials:")
        logger.info(f"  Email: test@example.com")
        logger.info(f"  Password: testpassword123")
        logger.info(f"\nNext steps:")
        logger.info(f"  1. Login: POST /api/auth/login")
        logger.info(f"  2. Ingest video: POST /api/transcripts/ingest")

if __name__ == "__main__":
    asyncio.run(main())
```

**Usage:**
```bash
cd backend
python scripts/seed_database.py
```

---

### 4. Tests

#### `tests/integration/test_transcript_ingestion.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock, patch

class TestTranscriptIngestion:
    """Integration tests for full transcript ingestion flow."""

    def test_ingest_transcript_success(self, client, test_user, test_session):
        """Test successful transcript ingestion end-to-end."""
        # Mock SUPADATA API response
        mock_transcript_data = {
            "youtube_video_id": "TEST123",
            "transcript_text": "This is a test transcript. " * 100,  # ~300 tokens
            "metadata": {
                "title": "Test Video",
                "duration": 120
            }
        }

        with patch.object(TranscriptService, 'fetch_transcript', return_value=mock_transcript_data):
            response = client.post(
                "/api/transcripts/ingest",
                json={"youtube_url": "https://youtube.com/watch?v=TEST123"},
                headers={"Authorization": f"Bearer {test_session['token']}"}
            )

        assert response.status_code == 201
        data = response.json()
        assert data["youtube_video_id"] == "TEST123"
        assert data["chunk_count"] > 0
        assert "metadata" in data

    def test_ingest_duplicate_returns_409(self, client, test_user, test_session):
        """Test duplicate ingestion returns 409 Conflict."""
        url = "https://youtube.com/watch?v=DUPLICATE"

        mock_data = {
            "youtube_video_id": "DUPLICATE",
            "transcript_text": "Text " * 100,
            "metadata": {}
        }

        with patch.object(TranscriptService, 'fetch_transcript', return_value=mock_data):
            # First ingestion
            response1 = client.post(
                "/api/transcripts/ingest",
                json={"youtube_url": url},
                headers={"Authorization": f"Bearer {test_session['token']}"}
            )
            assert response1.status_code == 201

            # Second ingestion (duplicate)
            response2 = client.post(
                "/api/transcripts/ingest",
                json={"youtube_url": url},
                headers={"Authorization": f"Bearer {test_session['token']}"}
            )

            assert response2.status_code == 409
            assert "already ingested" in response2.json()["detail"].lower()

    def test_ingest_requires_authentication(self, client):
        """Test ingestion requires valid session token."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=TEST"}
        )

        assert response.status_code == 401

    def test_ingest_invalid_url_returns_422(self, client, test_user, test_session):
        """Test invalid URL returns 422 validation error."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://vimeo.com/123456"},
            headers={"Authorization": f"Bearer {test_session['token']}"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_full_pipeline_database_and_qdrant(self, db_session, test_user):
        """Test full pipeline updates both PostgreSQL and Qdrant."""
        from app.services.transcript_service import TranscriptService
        from app.db.repositories.transcript_repo import TranscriptRepository
        from app.db.repositories.chunk_repo import ChunkRepository
        from app.services.qdrant_service import QdrantService

        # Mock SUPADATA
        mock_data = {
            "youtube_video_id": "FULLTEST",
            "transcript_text": "This is test content. " * 200,  # ~600 tokens
            "metadata": {"title": "Test"}
        }

        with patch.object(TranscriptService, 'fetch_transcript', return_value=mock_data):
            service = TranscriptService()
            result = await service.ingest_transcript(
                youtube_url="https://youtube.com/watch?v=FULLTEST",
                user_id=str(test_user.id),
                db_session=db_session
            )

        # Verify PostgreSQL
        transcript_repo = TranscriptRepository(db_session)
        transcript = await transcript_repo.get_by_id(result["transcript_id"])
        assert transcript is not None
        assert transcript.youtube_video_id == "FULLTEST"

        chunk_repo = ChunkRepository(db_session)
        chunks = await chunk_repo.get_by_transcript_id(result["transcript_id"])
        assert len(chunks) == result["chunk_count"]

        # Verify Qdrant
        qdrant_service = QdrantService()
        search_results = await qdrant_service.search(
            query_vector=[0.1] * 1024,  # Dummy query
            user_id=str(test_user.id)
        )
        assert len(search_results) == result["chunk_count"]
```

---

### Acceptance Criteria for PR #7:

- [ ] Full pipeline completes successfully (fetch → chunk → embed → store)
- [ ] Duplicate detection works (409 on re-ingestion)
- [ ] Authentication required (401 without token)
- [ ] Invalid URLs return 422
- [ ] Short transcripts (< 700 tokens) stored as single chunk
- [ ] Data synced between PostgreSQL and Qdrant
- [ ] Partial data kept on pipeline failure
- [ ] API endpoint documented in Swagger
- [ ] Seed script creates user + templates + config
- [ ] Seed script creates Qdrant collection
- [ ] All integration tests pass
- [ ] Test coverage > 80%
- [ ] Code passes linting
- [ ] Logging present for each pipeline step

**Dependencies:** PR #5 and PR #6 merged

**Estimated LOC:** 300-400

---

## Overall Phase 4 Completion Criteria

Before marking Phase 4 as complete:

- [ ] All 3 PRs merged to main
- [ ] Can ingest YouTube transcript via API endpoint
- [ ] Data correctly stored in PostgreSQL (transcripts + chunks tables)
- [ ] Vectors correctly stored in Qdrant (with user_id filtering)
- [ ] Both YouTube URL formats work (youtube.com and youtu.be)
- [ ] Duplicates rejected with 409 Conflict
- [ ] Short transcripts kept as single chunk (< 700 tokens)
- [ ] Chunking implements 20% overlap correctly
- [ ] Seed script successfully creates test environment
- [ ] Test coverage > 80% overall for Phase 4 code
- [ ] All code linted and type-hinted
- [ ] Documentation updated (API docs auto-generated)
- [ ] Retry mechanisms implemented (tenacity for external APIs)
- [ ] Error handling graceful (meaningful error messages)
- [ ] Logging present (INFO for success, ERROR for failures)

---

## Phase 4 Timeline Estimate

**Total Effort:** ~12-16 hours of focused development

- **PR #5:** 4-5 hours (foundational services + tests)
- **PR #6:** 4-5 hours (vector infrastructure + integration tests)
- **PR #7:** 4-6 hours (orchestration + API + seed script + comprehensive tests)

**Review Time:** 1-2 hours per PR

**Total Calendar Time:** 3-5 days (with reviews and iterations)

---

## Next Steps After Phase 4

Once Phase 4 is complete, move to **Phase 5: RAG Foundation** which includes:
- OpenRouter LLM client
- Jinja2 prompt templates
- LangGraph state definition
- Retriever and Grader nodes
- Unit tests for RAG components

**Retry Strategy for Phase 5:** Switch to **LangGraph RetryPolicy** for all graph nodes (see `LANGCHAIN_RETRY.md`)

---

**Document Version:**
- v1.0 (2025-10-20): Initial Stage 4 implementation plan

**Cross-References:**
- See: `LANGCHAIN_RETRY.md` for retry mechanism decisions
- See: `HANDOFF.md` for Phase 4 checkboxes (4.1-4.7)
- See: `DATABASE_SCHEMA.md` for transcripts and chunks table schemas
- See: `INIT_PROMPT.md` for overall project context
