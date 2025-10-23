# Manual Test Checklist

Complete system verification with real services. This checklist should be completed before considering Phase 9 production-ready.

## Prerequisites

Before starting manual testing, ensure:
- ✅ All services running (PostgreSQL, Qdrant, Backend)
- ✅ Database seeded with test data
- ✅ Valid OpenRouter API key configured
- ✅ Valid OpenAI API key configured (for embeddings)
- ✅ Backend server running (`uvicorn app.main:app --reload`)

## Test Scenarios

### 1. User Registration & Authentication

**Registration:**
- [ ] Register new user with valid email and password
- [ ] Verify token is returned in response
- [ ] Attempt duplicate registration (should fail with 409)
- [ ] Register with invalid email format (should fail with 422)
- [ ] Register with weak password (should fail with 422)

**Login:**
- [ ] Login with valid credentials (should return token)
- [ ] Login with invalid credentials (should fail with 401)
- [ ] Login with non-existent email (should fail with 401)

**Token Validation:**
- [ ] Access protected endpoint with valid token (should succeed)
- [ ] Access protected endpoint without token (should fail with 401)
- [ ] Access protected endpoint with invalid token (should fail with 401)

**Logout:**
- [ ] Logout with valid token (should return 204)
- [ ] Attempt to use token after logout (should fail with 401)

---

### 2. Health Check Endpoints

**Basic Health:**
- [ ] GET `/api/health` returns 200 with `{"status": "ok"}`
- [ ] Response time < 100ms

**Database Health:**
- [ ] GET `/api/health/db` returns 200 with `{"status": "healthy", "service": "postgresql"}`
- [ ] Stop PostgreSQL → endpoint returns 503 with `{"status": "unhealthy"}`
- [ ] Restart PostgreSQL → endpoint returns 200 again
- [ ] Response time < 100ms

**Qdrant Health:**
- [ ] GET `/api/health/qdrant` returns 200 with `{"status": "healthy", "service": "qdrant"}`
- [ ] Stop Qdrant → endpoint returns 503 with `{"status": "unhealthy"}`
- [ ] Restart Qdrant → endpoint returns 200 again
- [ ] Response time < 100ms

---

### 3. Conversation Management API

**List Conversations:**
- [ ] GET `/api/conversations` returns empty list for new user
- [ ] GET `/api/conversations` returns user's conversations (ordered by most recent)
- [ ] Pagination works: `?limit=10&offset=0` returns correct page
- [ ] Limit validation: `?limit=0` fails with 422
- [ ] Limit validation: `?limit=101` fails with 422
- [ ] Response time < 200ms

**Create Conversation:**
- [ ] POST `/api/conversations` with title creates conversation
- [ ] POST `/api/conversations` without title auto-generates title
- [ ] Title longer than 200 chars fails with 422
- [ ] Returns 201 with conversation data
- [ ] Created conversation appears in list

**Get Conversation Detail:**
- [ ] GET `/api/conversations/{id}` returns conversation + messages
- [ ] Non-existent conversation returns 404
- [ ] Invalid UUID format returns 422
- [ ] Other user's conversation returns 403
- [ ] Response time < 200ms

**Delete Conversation:**
- [ ] DELETE `/api/conversations/{id}` returns 204
- [ ] Deleted conversation no longer in list
- [ ] GET deleted conversation returns 404
- [ ] Delete non-existent conversation returns 404
- [ ] Delete other user's conversation returns 403

---

### 4. YouTube Transcript Ingestion

**Valid URL:**
- [ ] POST `/api/transcripts` with valid YouTube URL succeeds
- [ ] Verify transcript saved in database
- [ ] Verify chunks created in database
- [ ] Verify vectors stored in Qdrant (check `/qdrant/dashboard`)
- [ ] Response time < 30s

**Duplicate URL:**
- [ ] Attempt to ingest same URL twice (should fail with 409)

**Invalid URL:**
- [ ] Ingest non-YouTube URL (should fail with 400)
- [ ] Ingest invalid YouTube URL format (should fail with 400)
- [ ] Ingest YouTube URL without transcript (should fail with error)

---

### 5. WebSocket Chat

**Connection:**
- [ ] Connect to `/ws/chat` with valid token (should succeed)
- [ ] Connect with invalid token (should fail and disconnect)
- [ ] Connect without token (should fail and disconnect)

**Chitchat Messages:**
- [ ] Send "Hello" → receive friendly response
- [ ] Send "How are you?" → receive chitchat response
- [ ] Response time < 5s

**Q&A Messages:**
- [ ] Send question about ingested video → receive status updates
- [ ] Verify status updates: `processing`, `retrieving`, `generating`
- [ ] Receive answer with sources metadata
- [ ] Verify messages saved to database
- [ ] Response time < 10s

**LinkedIn Post Generation:**
- [ ] Send "Generate LinkedIn post" → receive formatted post
- [ ] Verify post has proper structure (hook, body, CTA)
- [ ] Verify status updates sent
- [ ] Response time < 10s

**Conversation Auto-Creation:**
- [ ] First message auto-creates conversation
- [ ] Subsequent messages use same conversation
- [ ] Conversation appears in `/api/conversations` list

**Error Handling:**
- [ ] Send message without ingested transcript → receive error
- [ ] LLM API failure → receive user-friendly error
- [ ] Network timeout → receive timeout error

---

### 6. Rate Limiting

**WebSocket Rate Limiting:**
- [ ] Send 10 messages rapidly (all should succeed)
- [ ] Send 11th message within 60s (should be rate-limited with 429)
- [ ] Wait 60 seconds
- [ ] Send message (should work again)

**API Rate Limiting:**
- [ ] Make 50 API requests rapidly (check for rate limiting)
- [ ] Verify rate limit headers in response

---

### 7. Error Scenarios

**Invalid Input:**
- [ ] Send message longer than 2000 chars → validation error
- [ ] Send malformed JSON → 400 error
- [ ] Send empty message → validation error

**Database Issues:**
- [ ] Stop PostgreSQL → health check returns 503
- [ ] API requests fail gracefully
- [ ] Restart PostgreSQL → system recovers

**Qdrant Issues:**
- [ ] Stop Qdrant → health check returns 503
- [ ] RAG queries fail gracefully with error message
- [ ] Chitchat still works
- [ ] Restart Qdrant → RAG queries work again

**External API Failures:**
- [ ] Invalid OpenRouter key → LLM error message
- [ ] Invalid OpenAI key → embedding error message
- [ ] Network timeout → timeout error message

---

### 8. Multi-User Testing

**User Isolation:**
- [ ] Register 2 different users (User A and User B)
- [ ] User A creates conversation
- [ ] User B cannot access User A's conversation (403)
- [ ] User A can list and access own conversations
- [ ] User B can list and access own conversations

**Rate Limit Isolation:**
- [ ] User A hits rate limit
- [ ] User B can still send messages (rate limits independent)

**Data Isolation:**
- [ ] User A ingests video
- [ ] User B cannot query User A's video data
- [ ] User B must ingest own videos

---

### 9. Performance Checks

Use these as guidelines, not strict requirements:

- [ ] **RAG Retrieval:** < 500ms
- [ ] **WebSocket First Message:** < 5s
- [ ] **List Conversations:** < 200ms
- [ ] **Health Checks:** < 100ms
- [ ] **Login/Register:** < 500ms
- [ ] **Create Conversation:** < 300ms

---

### 10. Security Checks

**Authentication:**
- [ ] JWT tokens expire after 7 days
- [ ] Expired tokens cannot access protected endpoints
- [ ] Tokens are properly hashed in database

**Authorization:**
- [ ] Users can only access own conversations
- [ ] Users can only delete own conversations
- [ ] Users can only access own transcripts

**Input Validation:**
- [ ] SQL injection attempts are blocked
- [ ] XSS attempts are sanitized
- [ ] Path traversal attempts are blocked

**Secrets:**
- [ ] `.env` file not committed to git
- [ ] API keys not exposed in logs
- [ ] Passwords properly hashed (bcrypt)
- [ ] Session tokens hashed (SHA-256)

---

## Success Criteria

**Phase 9 is complete when:**
- ✅ All automated E2E tests pass
- ✅ All checkboxes above are completed
- ✅ Test coverage > 80%
- ✅ No P0 or P1 bugs found
- ✅ Documentation is up-to-date

---

## Testing Notes

**Date:** _____________
**Tester:** _____________
**Environment:** _____________

**Issues Found:**
1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

**Blockers:**
- _____________________________________________

**Next Steps:**
- _____________________________________________

---

**Last Updated:** 2025-10-22
**Version:** 1.0
