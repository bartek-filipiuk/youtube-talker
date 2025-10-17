# Product Requirements Document (PRD)
## YoutubeTalker MVP

**Version:** 1.0
**Last Updated:** 2025-10-17
**Status:** MVP Planning

---

## Executive Summary

YoutubeTalker is an AI-powered chat application that enables users to have intelligent conversations about YouTube video content. By leveraging RAG (Retrieval-Augmented Generation) technology, users can query knowledge extracted from YouTube transcripts and generate content (e.g., LinkedIn posts) based on that knowledge.

**MVP Goal:** Deliver a functional, single-user prototype that demonstrates core RAG chat capabilities and LinkedIn post generation from YouTube transcript knowledge.

---

## Product Vision

Enable content creators and knowledge workers to efficiently extract insights from YouTube videos and transform them into actionable content through conversational AI.

**Long-term Vision (Post-MVP):** Multi-user platform with custom templates, multi-source knowledge (not just YouTube), and advanced content generation for various social media platforms.

---

## User Personas

### Primary Persona: Content Creator Chris
- **Role:** LinkedIn content creator, consultant, educator
- **Pain Points:**
  - Watches many educational YouTube videos but struggles to remember details
  - Wants to create LinkedIn posts based on learned concepts
  - Needs quick access to specific information from long videos
- **Goals:**
  - Query YouTube video content conversationally
  - Generate LinkedIn posts based on video knowledge
  - Save time on content research and creation

---

## Core Features (MVP Scope)

### 1. User Authentication
- **Description:** Secure login system with username/password
- **Requirements:**
  - User registration with email and password
  - Login with session management (7-day sessions)
  - Logout functionality
  - Server-side session storage in PostgreSQL
- **Acceptance Criteria:**
  - User can register a new account
  - User can log in and receive a session token
  - Session persists for 7 days or until logout
  - Passwords are securely hashed (bcrypt)

### 2. YouTube Transcript Ingestion
- **Description:** Process YouTube videos into searchable knowledge chunks
- **Requirements:**
  - API endpoint to accept YouTube URL
  - Integration with SUPADATA API for transcription
  - Automatic chunking of transcripts (700 tokens, 20% overlap)
  - Embedding generation via OpenRouter
  - Storage in Qdrant vector database
- **Acceptance Criteria:**
  - System accepts YouTube URL and returns success/error
  - Transcript is stored in PostgreSQL with metadata
  - Chunks are created with proper overlap and stored in Qdrant
  - Chunks are associated with the user account
- **MVP Limitation:** Manual API call (no UI for ingestion in MVP)

### 3. Conversational Chat Interface
- **Description:** Real-time chat interface for querying YouTube knowledge
- **Requirements:**
  - WebSocket-based chat connection
  - Real-time message streaming
  - Conversation history persistence
  - Access to last 10 messages as context
  - Message length validation (max 2000 characters)
- **Acceptance Criteria:**
  - User can send messages via WebSocket
  - AI responses are streamed in real-time
  - Conversation history is saved and retrievable
  - User can view previous conversations
  - System maintains context from last 10 messages

### 4. RAG-Based Question Answering
- **Description:** Answer user questions using YouTube transcript knowledge
- **Requirements:**
  - Query classification (chitchat vs. knowledge query)
  - Semantic search in Qdrant (top-12 chunks)
  - LLM-based chunk grading (binary relevant/not relevant)
  - Context-aware response generation
  - Source attribution (which chunks were used)
- **Acceptance Criteria:**
  - System correctly routes queries to appropriate flow
  - Relevant chunks are retrieved based on semantic similarity
  - Only relevant chunks are used for response generation
  - Responses cite source information
  - System handles queries outside knowledge base gracefully

### 5. LinkedIn Post Generation
- **Description:** Generate formatted LinkedIn posts based on transcript knowledge
- **Requirements:**
  - Template-based post generation
  - Hardcoded default LinkedIn template in MVP
  - Topic extraction from user query
  - RAG retrieval specific to requested topic
  - Structured output (formatted for LinkedIn)
- **Acceptance Criteria:**
  - User can request LinkedIn post generation
  - System retrieves relevant chunks for topic
  - Generated post follows LinkedIn template format
  - Post is returned in chat and stored in conversation history
  - Template variables (topic, key_points, tone) are properly filled

### 6. Conversation Management
- **Description:** Organize chats into separate conversations
- **Requirements:**
  - Each conversation has unique UUID
  - List of user's conversations
  - Ability to create new conversations
  - Ability to delete conversations
  - Conversation titles (can be auto-generated from first message)
- **Acceptance Criteria:**
  - User can view list of all conversations
  - User can start a new conversation
  - User can open and continue existing conversations
  - Deleting a conversation removes all associated messages

---

## Technical Requirements

### Technology Stack

**Backend:**
- Python 3.11+
- FastAPI (async)
- PostgreSQL 15+
- SQLAlchemy 2.0 (async)
- Alembic (migrations)
- Qdrant (vector database)
- LangChain + LangGraph
- OpenRouter API (LLM + embeddings)
- SUPADATA API (transcription)
- SlowAPI (rate limiting)

**Frontend:**
- Astro Framework
- WebSocket client
- TailwindCSS (or preferred CSS framework)

**Infrastructure:**
- Docker + Docker Compose (local dev)
- Environment-based configuration (.env)

### Data Storage

**PostgreSQL Tables:**
- users
- sessions
- conversations
- messages
- transcripts
- chunks
- templates
- config

**Qdrant:**
- Collection: youtube_chunks
- Vector dimension: 1024 (OpenRouter embeddings-small)
- Metadata: chunk_id, user_id, youtube_video_id, chunk_index

### External APIs

1. **SUPADATA API**
   - Purpose: YouTube video transcription
   - Input: YouTube URL
   - Output: Full transcript with metadata

2. **OpenRouter API**
   - LLM Model: anthropic/claude-haiku-4.5
   - Embedding Model: openai/text-embedding-3-small
   - Purpose: Chat responses, chunk grading, embeddings

### Performance Requirements

- WebSocket response latency: < 2 seconds for first token
- RAG retrieval time: < 500ms
- Message history load: < 200ms
- Support for conversations with 100+ messages
- Concurrent users: 1 user in MVP, architecture supports 10+ users

### Security Requirements

- Passwords hashed with bcrypt
- Session tokens stored as hashes
- SQL injection prevention (parameterized queries)
- Rate limiting on all endpoints (SlowAPI)
- CORS properly configured
- Environment variables for sensitive data

---

## User Stories

### Authentication
1. As a user, I want to register an account so that I can use the system
2. As a user, I want to log in with my credentials so that I can access my conversations
3. As a user, I want to stay logged in for 7 days so that I don't need to re-authenticate frequently
4. As a user, I want to log out to secure my account

### Content Ingestion
5. As an admin, I want to submit YouTube URLs via API so that transcripts are added to the knowledge base
6. As a user, I want my knowledge base to be private so that other users cannot access my data

### Chat & Questions
7. As a user, I want to ask questions about my YouTube videos so that I can quickly find information
8. As a user, I want the AI to answer based only on my knowledge base so that responses are accurate
9. As a user, I want to see my conversation history so that I can review past discussions
10. As a user, I want to create multiple conversations so that I can organize different topics
11. As a user, I want to copy AI responses to my clipboard for easy use elsewhere

### LinkedIn Generation
12. As a user, I want to generate LinkedIn posts based on topics in my videos so that I can create content faster
13. As a user, I want the LinkedIn post to follow a professional format so that it's ready to publish
14. As a user, I want the post to be based only on my knowledge base so that content is authentic

---

## Success Metrics

**MVP Success Criteria:**
1. User can register, log in, and maintain a session
2. System successfully ingests and processes at least 5 YouTube videos (manual)
3. User can ask 10 different questions and receive relevant answers
4. Generated LinkedIn posts are coherent and based on retrieved knowledge
5. Conversation history is persisted and retrievable
6. Zero critical bugs in core flows
7. Response time < 2 seconds for 90% of queries

**Quality Metrics:**
- RAG retrieval relevance: > 80% (manual evaluation)
- Chunk grader accuracy: > 75% (manual evaluation)
- System uptime: > 95% (local development)
- Test coverage: > 80%

---

## Non-Functional Requirements

### Usability
- Chat interface is intuitive (no training required)
- Error messages are clear and actionable
- WebSocket reconnection is automatic

### Maintainability
- Code follows PEP 8 (Python)
- All functions have docstrings
- Database schema is versioned (Alembic migrations)
- Modular architecture (easy to add new flows)

### Scalability (Post-MVP)
- Architecture supports multi-user (even if MVP is single-user)
- Template system allows user customization
- LangGraph flows are independent modules

### Observability
- Structured logging (JSON format)
- LangSmith integration for LangGraph tracing (late MVP)
- Health check endpoints for monitoring

---

## Out of Scope (Post-MVP)

**Authentication & Users:**
- Email verification
- Password reset
- OAuth/SSO
- User profile management
- Multi-user collaboration

**Content Features:**
- Template editing via UI
- Additional content types (Twitter/X, Blog posts)
- Multi-source knowledge (PDFs, articles)
- Batch video ingestion UI
- Video search/browse interface

**Chat Features:**
- Message editing/deletion
- Conversation search
- Export conversations
- Typing indicators
- Markdown editor for messages
- Image/file attachments

**Advanced RAG:**
- Conversation summarization
- Long-term memory
- Multi-query retrieval
- Query expansion
- Re-ranking algorithms

**Infrastructure:**
- Production deployment
- CI/CD pipeline
- Load balancing
- Caching layer (Redis)
- CDN for static assets

---

## Assumptions & Constraints

**Assumptions:**
1. User has access to YouTube URLs for transcription
2. SUPADATA API is reliable and has sufficient quota
3. OpenRouter API has sufficient rate limits for MVP testing
4. Qdrant can be run locally or via cloud instance
5. Single user in MVP simplifies access control

**Constraints:**
1. MVP budget: Minimal cloud costs (use free tiers where possible)
2. MVP timeline: ~20-25 working days (single developer)
3. OpenRouter API costs: ~$0.01 per conversation (acceptable for MVP)
4. No production hosting in MVP (local/dev environment only)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SUPADATA API downtime | Medium | High | Cache transcripts; add retry logic |
| OpenRouter rate limits | Low | Medium | Implement exponential backoff; monitor usage |
| Qdrant connection failures | Low | High | Connection pooling; health checks |
| Poor RAG relevance | Medium | Medium | Iterative prompt engineering; chunk grading |
| WebSocket disconnections | Medium | Low | Auto-reconnect; heartbeat mechanism |
| Slow response times | Low | Medium | Optimize chunk retrieval; async processing |

---

## Development Approach

**Methodology:** Incremental development with test-driven approach

**Workflow:**
1. Work on one HANDOFF.md checkbox at a time
2. Write tests before/during implementation
3. Code review required for every change
4. No direct pushes to main branch
5. Each feature = separate branch + PR

**Testing Strategy:**
- Unit tests for services, repositories, and RAG nodes
- Integration tests for API endpoints
- End-to-end test for complete user journey
- Manual testing for chat UX

**Documentation:**
- Inline docstrings for all functions
- API endpoint documentation (OpenAPI/Swagger)
- Database schema documentation
- HANDOFF.md tracks progress

---

## Appendix

### Glossary
- **RAG:** Retrieval-Augmented Generation
- **Chunk:** Segment of text (700 tokens) used for vector search
- **Embedding:** Vector representation of text for semantic search
- **Qdrant:** Vector database for similarity search
- **LangGraph:** Framework for building stateful LLM applications
- **SUPADATA:** API service for YouTube transcription

### References
- LangChain Documentation: https://python.langchain.com/
- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- Qdrant Documentation: https://qdrant.tech/documentation/
- OpenRouter API: https://openrouter.ai/docs
- FastAPI Documentation: https://fastapi.tiangolo.com/

---

**Document Approval:**
- Product Owner: [Pending]
- Technical Lead: [Pending]
- Created: 2025-10-17
