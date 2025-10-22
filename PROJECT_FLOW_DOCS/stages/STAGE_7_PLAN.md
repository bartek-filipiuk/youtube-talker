# Stage 7: WebSocket Chat API - Implementation Plan

**Version:** 1.0
**Last Updated:** 2025-10-22
**Status:** Planning Complete - Ready for Implementation

---

## Overview

Build real-time chat interface with WebSocket that integrates Stage 6's LangGraph flows. Focus on progress updates (not token streaming) and clean error handling.

---

## Architecture Decisions (Based on Requirements)

### 1. **Progress Updates (Not Streaming)**
- Send **status messages** during RAG flow execution:
  - "Classifying your query..."
  - "Searching knowledge base..."
  - "Analyzing results..."
  - "Generating response..."
- Send **complete response** when ready (no token-by-token streaming)
- Keep messages minimal and useful

### 2. **Authentication Flow**
- Token in query param: `ws://localhost:8000/ws/chat?token=xxx`
- Validate on connection → get user
- Auto-create conversation if needed
- Verify ownership once per conversation

### 3. **Error Handling**
- Save nothing on error
- Show user-friendly error message
- Update conversation.updated_at only on success
- Log all errors with context

---

## PR Strategy (2 PRs)

### **PR #15: WebSocket Foundation**
- Connection manager
- Basic chat handler with auth
- Status message system
- Simple echo/ping test

### **PR #16: RAG Integration + Testing**
- Integrate run_graph() from Stage 6
- Message persistence
- Rate limiting
- End-to-end tests

---

## PR #15: WebSocket Foundation

### Files to Create:

**1. `app/api/websocket/__init__.py`**
- Empty init file

**2. `app/api/websocket/connection_manager.py`**
- `ConnectionManager` class:
  - `connect(websocket, user_id)` - Track active connections
  - `disconnect(websocket)` - Cleanup
  - `send_json(websocket, data)` - Send JSON message
  - Heartbeat mechanism (30s ping/pong)

**3. `app/api/websocket/messages.py`**
- Pydantic schemas for WebSocket messages:
  - `IncomingMessage` (from client)
  - `StatusMessage` (progress updates)
  - `AssistantMessage` (complete response)
  - `ErrorMessage` (error responses)

**4. `app/api/websocket/chat_handler.py`**
- `websocket_endpoint(websocket, token: str)` - Main endpoint
- **On connection**:
  - Validate token → get user
  - If invalid: send error + disconnect
  - Register in ConnectionManager
- **On message received**:
  - Validate message format
  - Extract conversation_id (auto-create if "new")
  - Verify user owns conversation
  - Send back echo (for testing)
- **Heartbeat**: Respond to ping messages

**5. `app/main.py`** (update)
- Add WebSocket route: `app.websocket("/ws/chat")(websocket_endpoint)`

**6. Tests:**
- `tests/unit/test_connection_manager.py` (5+ tests)
- `tests/integration/test_websocket_basic.py` (5+ tests)
  - Test connection with valid token
  - Test connection with invalid token
  - Test heartbeat
  - Test message echo
  - Test disconnect

**Acceptance Criteria:**
- ✅ WebSocket connection established with valid token
- ✅ Invalid tokens rejected immediately
- ✅ Heartbeat keeps connection alive
- ✅ Basic message echo works
- ✅ Test coverage > 80%

---

## PR #16: RAG Integration + Testing

### Files to Create/Update:

**1. `app/api/websocket/chat_handler.py`** (update)
- **On user message**:
  1. Send status: `{"type": "status", "message": "Classifying your query...", "step": "routing"}`
  2. Fetch last 10 messages (MessageRepository)
  3. Call `run_graph(user_query, user_id, conversation_history)`
  4. **Send status updates** at each step (intercept from run_graph logs or add callbacks)
  5. On success:
     - Send complete response: `{"type": "message", "role": "assistant", "content": "...", "metadata": {...}}`
     - Save user message (MessageRepository)
     - Save assistant response (MessageRepository)
     - Update conversation.updated_at
  6. On error:
     - Send error: `{"type": "error", "message": "Something went wrong. Please try again."}`
     - Log error with full context
     - Don't save anything

**2. `app/api/websocket/rate_limiter.py`**
- Simple in-memory rate limiter (10 messages/minute per user)
- `check_rate_limit(user_id) -> bool`
- Returns True if allowed, False if exceeded

**3. Tests:**
- `tests/integration/test_websocket_rag.py` (8+ tests)
  - Test chitchat flow end-to-end
  - Test Q&A flow with status updates
  - Test LinkedIn generation
  - Test conversation history (last 10 messages)
  - Test auto-create conversation
  - Test conversation ownership verification
  - Test rate limiting
  - Test error handling (mock LLM failure)

**Acceptance Criteria:**
- ✅ Complete RAG flow works via WebSocket
- ✅ Status updates sent during processing
- ✅ Messages persisted correctly
- ✅ Conversation history used for context
- ✅ Rate limiting works (10 msg/min)
- ✅ Errors handled gracefully
- ✅ Test coverage > 80%

---

## Message Format Specification

### Client → Server (IncomingMessage)
```json
{
  "conversation_id": "uuid-or-new",  // "new" auto-creates
  "content": "What is FastAPI?"
}
```

### Server → Client (StatusMessage)
```json
{
  "type": "status",
  "message": "Searching knowledge base...",
  "step": "retrieving"  // "routing" | "retrieving" | "grading" | "generating"
}
```

### Server → Client (AssistantMessage)
```json
{
  "type": "message",
  "role": "assistant",
  "content": "<p>FastAPI is...</p>",
  "metadata": {
    "intent": "qa",
    "chunks_used": 5,
    "source_chunks": ["chunk-id-1", ...],
    "conversation_id": "uuid"
  }
}
```

### Server → Client (ErrorMessage)
```json
{
  "type": "error",
  "message": "Something went wrong. Please try again.",
  "code": "LLM_ERROR"  // or "RATE_LIMIT", "INVALID_INPUT", etc.
}
```

---

## Implementation Notes

### Status Update Strategy
Since we're not streaming tokens, inject status updates at key points:

```python
# In chat_handler.py
await send_status(websocket, "Classifying your query...", "routing")
result = await run_graph(...)  # This calls our Stage 6 router

# Could add hooks in router.py to send status between flows:
# - After classify_intent → send "Searching knowledge base..."
# - After retriever → send "Analyzing results..."
# - After grader → send "Generating response..."
```

**Option 1 (Simple)**: Hard-code status messages in chat_handler before/after run_graph
**Option 2 (Better)**: Modify run_graph to accept optional callback for status updates

**Recommendation**: Start with Option 1 for MVP, refactor to Option 2 if needed.

---

### Rate Limiting
Simple in-memory counter (good for MVP, single-instance):

```python
# rate_limiter.py
from collections import defaultdict
from time import time

class RateLimiter:
    def __init__(self, max_requests=10, window=60):
        self.requests = defaultdict(list)  # user_id → [timestamps]
        self.max_requests = max_requests
        self.window = window

    def check(self, user_id: str) -> bool:
        now = time()
        # Remove old requests
        self.requests[user_id] = [
            ts for ts in self.requests[user_id]
            if now - ts < self.window
        ]
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        self.requests[user_id].append(now)
        return True
```

---

### Conversation Auto-Creation
```python
# In chat_handler.py
conversation_id = message.conversation_id

if conversation_id == "new" or not conversation_id:
    # Auto-create new conversation
    conversation = await conversation_repo.create(
        user_id=current_user.id,
        title=f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    conversation_id = conversation.id
else:
    # Verify user owns conversation
    conversation = await conversation_repo.get_by_id(conversation_id)
    if not conversation or conversation.user_id != current_user.id:
        await send_error(websocket, "Conversation not found or access denied")
        return
```

---

## Testing Strategy

### Unit Tests
- ConnectionManager: connect, disconnect, send_json
- Message schemas: validation
- Rate limiter: check limits, window expiry

### Integration Tests
- WebSocket connection with auth
- Message flow (send → receive)
- RAG integration
- Error scenarios
- Rate limiting

### Manual Testing Checklist
- [ ] Connect with valid token
- [ ] Connect with invalid token (should fail)
- [ ] Send chitchat message → get response
- [ ] Send Q&A message → see status updates → get response
- [ ] Send LinkedIn request → get formatted post
- [ ] Rapid fire 11 messages → 11th should be rate-limited
- [ ] Disconnect and reconnect
- [ ] Multiple concurrent connections

---

## Dependencies

**Python Packages** (already installed):
- `websockets` (included with FastAPI)
- `python-multipart` (for WebSocket)

**No new dependencies needed!**

---

## File Structure
```
app/
├── api/
│   └── websocket/
│       ├── __init__.py           # NEW (PR #15)
│       ├── connection_manager.py # NEW (PR #15)
│       ├── messages.py           # NEW (PR #15)
│       ├── chat_handler.py       # NEW (PR #15, updated PR #16)
│       └── rate_limiter.py       # NEW (PR #16)
tests/
├── unit/
│   ├── test_connection_manager.py  # NEW (PR #15)
│   └── test_rate_limiter.py        # NEW (PR #16)
└── integration/
    ├── test_websocket_basic.py     # NEW (PR #15)
    └── test_websocket_rag.py       # NEW (PR #16)
```

---

## Estimated Effort
- **PR #15**: ~4-6 hours (WebSocket foundation)
- **PR #16**: ~6-8 hours (RAG integration + tests)
- **Total**: ~10-14 hours

---

## Success Criteria

✅ **PR #15 Complete When:**
- WebSocket connection works with auth
- Basic message echo functional
- Heartbeat keeps connection alive
- Unit + integration tests passing

✅ **PR #16 Complete When:**
- Full RAG flow works via WebSocket
- Status updates shown during processing
- Messages saved to database
- Rate limiting enforced
- All tests passing (80%+ coverage)

✅ **Stage 7 Complete When:**
- User can chat in real-time
- Progress feedback is clear
- Errors handled gracefully
- Ready for frontend integration (HANDOFF_FRONT.md Phase 4)

---

## Next Steps After Stage 7

After this stage is complete, the backend will be **fully functional** for the chat experience. The remaining phases (8-10) are polish and additional features:
- Phase 8: Template system (already have prompts, could defer)
- Phase 9: Health checks, conversation management API
- Phase 10: Final polish

Frontend can begin work once Stage 7 is merged! 🚀

---

## Key Integration Points with Stage 6

### Using run_graph()
```python
from app.rag.graphs.router import run_graph

# In chat_handler.py
result = await run_graph(
    user_query=message.content,
    user_id=str(current_user.id),
    conversation_history=history  # Last 10 messages
)

# result contains:
# - intent: "chitchat" | "qa" | "linkedin"
# - response: "<p>HTML formatted response</p>"
# - metadata: {chunks_used, source_chunks, etc.}
```

### Conversation History Format
```python
# Convert Message models to conversation_history format
history = [
    {"role": msg.role, "content": msg.content}
    for msg in last_10_messages
]
```

---

## Authentication Flow Diagram

```
Client                    WebSocket Server              Database
  |                              |                          |
  |--- Connect ws://...?token=xxx |                          |
  |                              |                          |
  |                              |--- Validate token ------>|
  |                              |<--- User object ---------|
  |                              |                          |
  |<--- Connection accepted -----|                          |
  |                              |                          |
  |--- Send message ------------>|                          |
  |                              |--- Get conversation ---->|
  |                              |<--- Verify ownership ----|
  |                              |                          |
  |<--- Status: "Routing..." ----|                          |
  |                              |                          |
  |                              |--- run_graph() --------->|
  |                              |                          |
  |<--- Status: "Searching..." --|                          |
  |                              |                          |
  |<--- Response ---------------|                          |
  |                              |--- Save messages ------->|
  |                              |                          |
```

---

**Document Version:**
- v1.0 (2025-10-22): Initial Stage 7 plan based on user requirements