# Integration Testing Lessons: Preventing Common RAG Pipeline Issues

**Date:** 2025-10-23
**Context:** Issues found during E2E testing after SUPADATA SDK integration

---

## Issues Encountered

### 1. LLM Output Length Constraints
**Problem:** Pydantic validation failed because LLM returned reasoning longer than 200 chars
**Root Cause:** Underestimated realistic LLM output length without testing
**Fix:** Increased `max_length` to 500 characters

### 2. Template Schema Mismatch
**Problem:** Jinja templates accessed `chunk.metadata.youtube_video_id` but chunks were flat dicts
**Root Cause:** Templates assumed nested structure, actual data was flat
**Fix:** Changed to `chunk.youtube_video_id|default('Unknown')`

### 3. SQLAlchemy Greenlet Error
**Problem:** Accessing ORM object attributes outside async context caused greenlet spawn error
**Root Cause:** Returned ORM objects from async function, accessed in sync list comprehension
**Fix:** Convert ORM objects to dicts inside async context before returning

---

## Prevention Guidelines

### 1. **Test with Real Data Early**
```python
# ❌ DON'T: Set constraints without testing
reasoning: str = Field(max_length=200)  # Too strict!

# ✅ DO: Test with actual LLM output, add buffer
reasoning: str = Field(max_length=500)  # Tested with Gemini, allows 1-2 sentences
```

**Rule:** Run integration tests with real external APIs before considering feature complete.

---

### 2. **Document Data Structures Explicitly**
```python
# ❌ DON'T: Assume structure in templates
{{ chunk.metadata.get('youtube_video_id') }}

# ✅ DO: Document what chunks actually contain
"""
Chunk structure (flat dict):
{
    "chunk_id": str,
    "chunk_text": str,
    "youtube_video_id": str,  # ← Direct field, not nested
    "chunk_index": int,
    "score": float
}
"""
{{ chunk.youtube_video_id }}
```

**Rule:** Add docstrings showing exact data structure for any dict/object passed to templates.

---

### 3. **Never Pass ORM Objects Across Async Boundaries**
```python
# ❌ DON'T: Return ORM objects for later access
async def get_last_n(conversation_id: UUID) -> List[Message]:
    result = await session.execute(query)
    return list(result.scalars().all())  # ORM objects!

# Later (FAILS):
messages = await repo.get_last_n(conv_id)
history = [{"role": msg.role} for msg in messages]  # ← Greenlet error!

# ✅ DO: Convert to dicts inside async context
async def get_last_n(conversation_id: UUID) -> List[dict]:
    result = await session.execute(query)
    messages = list(result.scalars().all())
    # Access attributes here, inside async context
    return [{"role": msg.role, "content": msg.content} for msg in messages]
```

**Rule:** Repository methods should return plain dicts, not ORM objects, unless consumed immediately.

---

### 4. **Type Hints Everywhere**
```python
# ❌ DON'T: Untyped returns
async def get_last_n(conversation_id, n=10):
    ...
    return messages  # What type? Message objects? Dicts?

# ✅ DO: Explicit type hints
async def get_last_n(conversation_id: UUID, n: int = 10) -> List[dict]:
    ...
    return [{"role": msg.role, "content": msg.content} for msg in messages]
```

**Rule:** Type hints prevent schema mismatches and make data contracts explicit.

---

### 5. **Integration Tests Before PR**
```bash
# ❌ DON'T: Rely only on unit tests
pytest tests/unit/  # All pass, but real APIs fail!

# ✅ DO: Run E2E tests with real services
docker compose up -d  # PostgreSQL, Qdrant
python scripts/test_e2e_manual.py  # Real SUPADATA, OpenRouter, OpenAI APIs
```

**Rule:** E2E tests catch integration issues that unit tests miss.

---

## Checklist Before Merging External API Integration

- [ ] **LLM Output Constraints**: Tested with real API, added 50% buffer to max lengths
- [ ] **Data Structures**: Documented in docstrings what each function returns
- [ ] **ORM Objects**: Never returned from async functions for later access
- [ ] **Type Hints**: All functions have explicit return type hints
- [ ] **Templates**: Verified data structure matches what templates expect
- [ ] **E2E Test**: Ran full pipeline test with real external services
- [ ] **Error Logs**: Checked server logs for warnings/errors during test

---

## Key Takeaway

**Integration issues appear at boundaries:**
- LLM constraints (boundary between our code and external API)
- Template data (boundary between Python and Jinja)
- Async/sync (boundary between async DB queries and sync processing)

**Solution:** Make boundaries explicit with:
1. Type hints
2. Docstrings showing exact data structures
3. E2E tests that cross all boundaries

---

**Last Updated:** 2025-10-23
**Next Review:** After next external API integration
