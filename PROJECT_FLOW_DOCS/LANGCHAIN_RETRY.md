# LangChain/LangGraph Retry Mechanisms Guide

**Version:** 1.0
**Last Updated:** 2025-10-20
**Purpose:** Reference guide for implementing retry logic in YoutubeTalker MVP

---

## Overview

This document explains the three retry mechanisms available for the YoutubeTalker project:
1. **LangGraph RetryPolicy** - Native retry for graph nodes (Phase 5+)
2. **LangChain with_retry()** - Simple retry for runnables (Phase 5+)
3. **Tenacity library** - Fine-grained retry for external APIs (Phase 4+)

---

## 1. LangGraph RetryPolicy (Recommended for Phase 5+)

### When to Use
- **RAG graph nodes** (retriever, grader, generator, router)
- **LLM invocations** within LangGraph workflows
- **Tool execution** in LangGraph agents
- Any operation that's part of a LangGraph state machine

### Why LangGraph RetryPolicy?
- ✅ Native integration with LangGraph's checkpointing
- ✅ Failed nodes retry without re-running successful nodes
- ✅ Per-node retry configuration
- ✅ Automatic handling of common network errors (5xx HTTP codes)
- ✅ Cleaner code than manual try/except

### Basic Usage

```python
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy

builder = StateGraph(State)

# Default policy: retries on most exceptions (excludes ValueError, TypeError)
# Handles 5xx HTTP status codes automatically
builder.add_node(
    "retriever_node",
    retrieve_chunks,
    retry_policy=RetryPolicy()
)

# Custom policy: retry only on specific exceptions
builder.add_node(
    "llm_call_node",
    generate_response,
    retry_policy=RetryPolicy(
        retry_on=ConnectionError,  # Only retry on connection errors
        max_attempts=3
    )
)

# Multiple exception types
builder.add_node(
    "api_call_node",
    call_external_api,
    retry_policy=RetryPolicy(
        retry_on=(ConnectionError, TimeoutError),
        max_attempts=5
    )
)
```

### Advanced Example: Database Operations

```python
import sqlite3
from langgraph.types import RetryPolicy

# Retry on specific database errors
builder.add_node(
    "query_database",
    query_database_func,
    retry_policy=RetryPolicy(retry_on=sqlite3.OperationalError)
)

# Retry with max attempts
builder.add_node(
    "model_call",
    call_model_func,
    retry_policy=RetryPolicy(max_attempts=5)
)
```

### Tool Error Handling

```python
from langgraph.prebuilt import ToolNode

# Custom error messages
tool_node = ToolNode(
    tools=[my_tool],
    handle_tool_errors="Custom error message when tool fails!"
)

# Custom error handler function
def handle_tool_error(state: State, error: Exception) -> dict:
    return {
        "messages": [{
            "role": "tool",
            "content": f"Tool execution failed: {str(error)}. Please try a different approach.",
            "tool_call_id": state["messages"][-1].tool_calls[0]["id"]
        }]
    }

custom_tool_node = ToolNode(tools=[my_tool], handle_tool_errors=handle_tool_error)
```

### Functional API (Tasks)

```python
from langgraph.func import task
from langgraph.types import RetryPolicy

# Configure retry policy for individual tasks
retry_policy = RetryPolicy(retry_on=ValueError, max_attempts=3)

@task(retry_policy=retry_policy)
def risky_operation():
    # Your code here
    pass
```

---

## 2. LangChain with_retry() (Simple Runnable Retry)

### When to Use
- **Simple LangChain chains** not using LangGraph
- **Quick retry logic** for one-off operations
- **Parser retries** (e.g., JSON parsing with fallback)

### Basic Usage

```python
from langchain_core.runnables import RunnableLambda

chain = prompt | llm | parser

# Add retry logic (default: 3 attempts)
chain_with_retry = chain.with_retry(stop_after_attempt=3)

result = chain_with_retry.invoke({"query": "What is the capital of France?"})
```

### Parser Retries

```python
from langchain.output_parsers import RetryOutputParser
from langchain_core.output_parsers import PydanticOutputParser

parser = PydanticOutputParser(pydantic_object=MyModel)

# Retry parser re-invokes LLM with error context
retry_parser = RetryOutputParser.from_llm(parser=parser, llm=llm)

# Parse with retry
result = retry_parser.parse_with_prompt(bad_response, original_prompt)
```

### Fallback Chains

```python
# Try primary chain, fallback to better model on failure
primary_chain = prompt | small_model | parser
fallback_chain = prompt | large_model | parser

chain_with_fallback = primary_chain.with_fallbacks([fallback_chain])

result = chain_with_fallback.invoke({"input": "complex query"})
```

---

## 3. Tenacity Library (External API Retries)

### When to Use
- **External HTTP APIs** (SUPADATA, OpenRouter, third-party services)
- **Network operations** requiring exponential backoff
- **Fine-grained retry control** (jitter, custom predicates)
- **Non-LangChain operations** (database connections, file I/O)

### Why Tenacity for Phase 4?
- ✅ Exponential backoff with jitter (prevents thundering herd)
- ✅ Retry only on specific HTTP status codes
- ✅ Conditional retry based on exception content
- ✅ Maximum delay limits
- ✅ Industry-standard for HTTP retries

### Installation

```bash
pip install tenacity
```

### Basic HTTP Retry

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
)
async def fetch_transcript(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return response.json()
```

### Advanced: Retry on Specific Status Codes

```python
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
import httpx

def is_retryable_http_error(exception):
    """Retry only on 5xx server errors and 429 rate limits."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500 or exception.response.status_code == 429
    return isinstance(exception, (httpx.ConnectError, httpx.TimeoutException))

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception(is_retryable_http_error)
)
async def call_openrouter_api(payload: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
```

### Retry with Logging

```python
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log, after_log
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def fetch_with_logging(url: str):
    # Automatically logs retry attempts
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

---

## Decision Matrix: When to Use Which?

| Scenario | Mechanism | Why |
|----------|-----------|-----|
| **LLM call in LangGraph node** | LangGraph RetryPolicy | Native integration, preserves checkpoints |
| **Vector search in RAG flow** | LangGraph RetryPolicy | Part of state machine, automatic retry |
| **Tool execution in agent** | LangGraph ToolNode errors | Built-in error handling for tools |
| **SUPADATA API (Phase 4)** | Tenacity | External HTTP API, need exponential backoff |
| **OpenRouter embeddings (Phase 4)** | Tenacity | External HTTP API, batch retries |
| **Qdrant upsert/search** | Try/except + manual | Already idempotent, simple retry sufficient |
| **Simple LangChain chain** | .with_retry() | Quick, built-in solution |
| **Parser errors** | RetryOutputParser | Re-invokes LLM with error context |

---

## YoutubeTalker Implementation Strategy

### Phase 4: Transcript Ingestion Pipeline

**Use Tenacity for:**
- ✅ SUPADATA API calls (fetch_transcript)
- ✅ OpenRouter embeddings API (generate_embeddings)
- ✅ Any external HTTP operations

**Example: SUPADATA Client**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

class TranscriptService:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
    )
    async def fetch_transcript(self, youtube_url: str):
        # Retries on network errors, 5xx, timeouts
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transcript",
                json={"video_id": self._extract_video_id(youtube_url)},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
```

**Qdrant Operations:**
```python
# Simple try/except sufficient (operations are idempotent)
async def upsert_chunks(self, chunks):
    try:
        self.client.upsert(collection_name="youtube_chunks", points=chunks)
    except Exception as e:
        logger.error(f"Qdrant upsert failed: {e}")
        raise
```

---

### Phase 5: RAG with LangGraph

**Use LangGraph RetryPolicy for:**
- ✅ Retriever node (Qdrant search)
- ✅ Grader node (LLM classification)
- ✅ Generator node (LLM response generation)
- ✅ Router node (intent classification)

**Example: RAG Graph**
```python
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy

builder = StateGraph(GraphState)

# Retriever node - retry on Qdrant connection errors
builder.add_node(
    "retrieve",
    retrieve_chunks,
    retry_policy=RetryPolicy(retry_on=ConnectionError, max_attempts=3)
)

# Grader node - retry on LLM API errors
builder.add_node(
    "grade",
    grade_chunks,
    retry_policy=RetryPolicy(max_attempts=3)  # Retries on 5xx by default
)

# Generator node - retry on LLM failures
builder.add_node(
    "generate",
    generate_response,
    retry_policy=RetryPolicy(max_attempts=3)
)

# Connect nodes
builder.add_edge("retrieve", "grade")
builder.add_edge("grade", "generate")
```

**Why This Split?**
- **Phase 4 (tenacity)**: External APIs need HTTP-specific retry logic (status codes, exponential backoff)
- **Phase 5 (RetryPolicy)**: LangGraph nodes benefit from native checkpointing and state preservation

---

## Best Practices

### 1. Always Set Maximum Attempts
```python
# ✅ Good: Prevents infinite retries
retry_policy = RetryPolicy(max_attempts=5)

# ❌ Bad: Could retry forever
retry_policy = RetryPolicy()  # No max_attempts
```

### 2. Use Exponential Backoff for HTTP
```python
# ✅ Good: Prevents overwhelming failed service
wait=wait_exponential(multiplier=1, min=2, max=60)

# ❌ Bad: Fixed delay can cause thundering herd
wait=wait_fixed(2)
```

### 3. Retry Only on Transient Errors
```python
# ✅ Good: Retry on network/server errors only
retry=retry_if_exception_type((ConnectionError, httpx.HTTPStatusError))

# ❌ Bad: Retrying on ValueError won't help
retry=retry_if_exception_type(Exception)  # Too broad
```

### 4. Log Retry Attempts
```python
# ✅ Good: Visibility into retry behavior
@retry(
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def api_call():
    pass
```

### 5. Set Reasonable Timeouts
```python
# ✅ Good: Fail fast on unresponsive services
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)

# ❌ Bad: No timeout can hang forever
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

---

## Common Pitfalls

### ❌ Retrying on Non-Retryable Errors
```python
# Don't retry on validation errors (they won't succeed on retry)
@retry(retry=retry_if_exception_type(ValueError))  # Bad
async def validate_input(data):
    if not data["email"]:
        raise ValueError("Email required")
```

### ❌ No Maximum Delay
```python
# Exponential backoff can grow too large without max
wait=wait_exponential(multiplier=2, min=1)  # Missing max!
# After 10 retries: 1, 2, 4, 8, 16, 32, 64, 128, 256, 512 seconds!
```

### ❌ Retrying Database Transactions
```python
# Don't blindly retry transactions (may cause duplicates)
@retry(stop=stop_after_attempt(3))
async def create_user(email):
    user = User(email=email)
    db.add(user)
    await db.commit()  # Retry might create duplicate users!
```

### ✅ Use Idempotency Keys Instead
```python
# Better: Make operation idempotent
async def create_user(email):
    existing = await db.get_by_email(email)
    if existing:
        return existing
    user = User(email=email)
    db.add(user)
    await db.commit()
    return user
```

---

## Testing Retry Logic

### Mock Transient Failures
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_retry_on_timeout():
    """Test that function retries on timeout."""
    service = TranscriptService()

    # First call fails, second succeeds
    mock_client = AsyncMock()
    mock_client.post.side_effect = [
        httpx.TimeoutException("Timeout"),  # First attempt
        AsyncMock(json=lambda: {"transcript": "text"})  # Second attempt succeeds
    ]

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await service.fetch_transcript("https://youtube.com/watch?v=TEST")

    assert mock_client.post.call_count == 2  # Verify retry happened
    assert result["transcript"] == "text"
```

---

## References

**LangGraph Documentation:**
- [How to Add Retry Policies](https://langchain-ai.github.io/langgraph/how-tos/graph-api/#retry-policies)
- [Tool Error Handling](https://langchain-ai.github.io/langgraph/how-tos/tool-calling/)
- [Functional API Retries](https://langchain-ai.github.io/langgraph/how-tos/use-functional-api/)

**LangChain Documentation:**
- [Runnable Retries](https://python.langchain.com/docs/how_to/lcel_cheatsheet#retry-logic)
- [Fallback Chains](https://python.langchain.com/docs/how_to/fallbacks)
- [Output Parser Retries](https://python.langchain.com/docs/how_to/output_parser_retry)

**Tenacity Documentation:**
- [GitHub Repository](https://github.com/jd/tenacity)
- [Documentation](https://tenacity.readthedocs.io/)

---

**Last Updated:** 2025-10-20
**Next Review:** Before Phase 5 implementation
