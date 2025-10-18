# Database Schema Documentation
## YoutubeTalker MVP

**Version:** 1.0
**Last Updated:** 2025-10-17
**Database:** PostgreSQL 15+

---

## Overview

The database schema is designed to support:
- User authentication with server-side sessions
- Multi-conversation chat history per user
- YouTube transcript storage and chunking
- Template management for content generation
- System configuration

**Key Design Principles:**
- User data isolation (all content tied to user_id)
- Denormalization where needed (e.g., user_id in chunks table)
- UUID primary keys for security and distributed systems
- Timestamps for audit trails
- JSONB for flexible metadata storage

---

## Entity Relationship Diagram (Text)

```
┌─────────────┐
│   users     │
└──────┬──────┘
       │
       ├──────────┬──────────────┬─────────────┬──────────────┐
       │          │              │             │              │
       ▼          ▼              ▼             ▼              ▼
  ┌─────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐
  │sessions │ │conversations │ │transcripts│ │templates │ │  chunks  │
  └─────────┘ └──────┬───────┘ └─────┬─────┘ └──────────┘ └────┬─────┘
                     │               │                           │
                     ▼               └───────────────────────────┘
              ┌──────────┐                     │
              │ messages │                     │
              └──────────┘                     ▼
                                        (Qdrant Vector DB)
```

**Relationships:**
- 1 User → Many Sessions
- 1 User → Many Conversations
- 1 Conversation → Many Messages
- 1 User → Many Transcripts
- 1 Transcript → Many Chunks
- 1 User → Many Chunks (denormalized)
- 1 User → Many Templates (nullable user_id for defaults)

---

## Table Schemas

### 1. users

**Purpose:** Store user accounts with authentication credentials

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);

-- Constraints
ALTER TABLE users ADD CONSTRAINT check_email_format
    CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');
```

**Columns:**
- `id`: Unique user identifier (UUID)
- `email`: User's email address (unique, login identifier)
- `password_hash`: Bcrypt hashed password (never store plaintext)
- `created_at`: Account creation timestamp
- `updated_at`: Last account update timestamp

**Sample Data:**
```sql
INSERT INTO users (email, password_hash) VALUES
    ('user@example.com', '$2b$12$KIXvkLhR9Q7Z8fX9YvZ9QeO5Z9Q7Z8fX9YvZ9QeO5Z9Q7Z8fX9YvZ');
```

---

### 2. sessions

**Purpose:** Server-side session management (7-day expiry)

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_sessions_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_sessions_token ON sessions(token_hash);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

**Columns:**
- `id`: Session identifier
- `user_id`: Reference to users table
- `token_hash`: SHA-256 hash of session token (sent to client)
- `expires_at`: Session expiration timestamp (7 days from creation)
- `created_at`: Session creation timestamp

**Cleanup Query (run periodically):**
```sql
DELETE FROM sessions WHERE expires_at < NOW();
```

**Sample Data:**
```sql
INSERT INTO sessions (user_id, token_hash, expires_at) VALUES
    ('user-uuid-here', 'hashed-token', NOW() + INTERVAL '7 days');
```

---

### 3. conversations

**Purpose:** Organize chat messages into separate conversation threads

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_conversations_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at DESC);
```

**Columns:**
- `id`: Conversation identifier (exposed to frontend as UUID)
- `user_id`: Owner of the conversation
- `title`: Conversation title (optional, can be auto-generated from first message)
- `created_at`: Conversation creation timestamp
- `updated_at`: Last message timestamp (updated on new message)

**Update Trigger (auto-update updated_at on new message):**
```sql
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_conversation
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_timestamp();
```

---

### 4. messages

**Purpose:** Store complete chat history (user + assistant messages)

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_messages_conversation
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    CONSTRAINT check_role
        CHECK (role IN ('user', 'assistant', 'system'))
);

-- Indexes
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_metadata ON messages USING GIN(metadata);
```

**Columns:**
- `id`: Message identifier
- `conversation_id`: Reference to conversations table
- `role`: Message sender ('user' | 'assistant' | 'system')
- `content`: Message text (HTML for assistant, plain text for user)
- `metadata`: JSONB for additional data (e.g., source_chunk_ids, content_type)
- `created_at`: Message timestamp

**Metadata Examples:**
```json
// For assistant messages with RAG sources
{
  "source_chunk_ids": ["chunk-uuid-1", "chunk-uuid-2"],
  "graded_chunks_count": 8,
  "retrieval_time_ms": 245
}

// For LinkedIn post generation
{
  "content_type": "linkedin_post",
  "template_id": "template-uuid",
  "topic": "RAG best practices"
}
```

**Query: Get Last 10 Messages for Context**
```sql
SELECT role, content, created_at
FROM messages
WHERE conversation_id = $1
ORDER BY created_at DESC
LIMIT 10;
```

---

### 5. transcripts

**Purpose:** Store full YouTube video transcriptions with metadata

```sql
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    youtube_video_id VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(500),
    channel_name VARCHAR(255),
    duration INTEGER,
    transcript_text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_transcripts_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_transcripts_user_id ON transcripts(user_id);
CREATE INDEX idx_transcripts_youtube_video_id ON transcripts(youtube_video_id);
CREATE INDEX idx_transcripts_metadata ON transcripts USING GIN(metadata);
```

**Columns:**
- `id`: Transcript identifier
- `user_id`: Owner of the transcript
- `youtube_video_id`: YouTube video ID (e.g., "dQw4w9WgXcQ")
- `title`: Video title from YouTube
- `channel_name`: YouTube channel name
- `duration`: Video duration in seconds
- `transcript_text`: Full transcript text
- `metadata`: JSONB for SUPADATA response metadata
- `created_at`: Ingestion timestamp

**Metadata Example:**
```json
{
  "language": "en",
  "thumbnail_url": "https://i.ytimg.com/...",
  "publish_date": "2024-01-15",
  "view_count": 1000000,
  "supadata_response": { /* original API response */ }
}
```

**Duplicate Check Query:**
```sql
SELECT id FROM transcripts
WHERE youtube_video_id = $1 AND user_id = $2;
```

---

### 6. chunks

**Purpose:** Store chunked transcript segments for RAG retrieval

```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id UUID NOT NULL,
    user_id UUID NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_chunks_transcript
        FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE,
    CONSTRAINT fk_chunks_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_chunk_index
        UNIQUE (transcript_id, chunk_index)
);

-- Indexes
CREATE INDEX idx_chunks_transcript_id ON chunks(transcript_id);
CREATE INDEX idx_chunks_user_id ON chunks(user_id);
CREATE INDEX idx_chunks_metadata ON chunks USING GIN(metadata);
```

**Columns:**
- `id`: Chunk identifier (stored in Qdrant metadata)
- `transcript_id`: Reference to parent transcript
- `user_id`: Denormalized user reference (for faster lookups from Qdrant)
- `chunk_text`: Chunked text segment (700 tokens with 20% overlap)
- `chunk_index`: Order within transcript (0, 1, 2, ...)
- `token_count`: Actual token count of this chunk
- `metadata`: JSONB for additional context
- `created_at`: Chunk creation timestamp

**Metadata Example:**
```json
{
  "youtube_video_id": "dQw4w9WgXcQ",
  "start_time": 120,
  "end_time": 180,
  "video_title": "Example Video"
}
```

**Query: Get Chunks by IDs (from Qdrant results)**
```sql
SELECT id, chunk_text, metadata
FROM chunks
WHERE id = ANY($1::uuid[]);
```

---

### 7. templates

**Purpose:** Store content generation templates (LinkedIn, Twitter, etc.)

**MVP Note:** For MVP, only 'linkedin' template type is implemented. Template type validation is handled in the application layer (Pydantic schemas) rather than database constraints, allowing flexible addition of new content types post-MVP without requiring database migrations.

```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    template_type VARCHAR(50) NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    template_content TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '[]',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_templates_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT unique_user_template
        UNIQUE (user_id, template_type, template_name)
    -- Note: No CHECK constraint on template_type for extensibility
    -- Validation performed in application layer (Pydantic)
);

-- Indexes
CREATE INDEX idx_templates_user_id ON templates(user_id);
CREATE INDEX idx_templates_type_default ON templates(template_type, is_default);
```

**Columns:**
- `id`: Template identifier
- `user_id`: Template owner (NULL = system default template)
- `template_type`: Type of content (MVP: 'linkedin', Post-MVP: 'twitter', 'blog', 'email', etc.)
- `template_name`: Human-readable template name
- `template_content`: Jinja2 template string
- `variables`: JSONB array of variable names used in template
- `is_default`: Whether this is the default template for the type
- `created_at`: Template creation timestamp
- `updated_at`: Last template update timestamp

**Template Content Example (LinkedIn):**
```jinja2
# {{ topic }}

{{ introduction }}

## Key Insights:
{% for point in key_points %}
- {{ point }}
{% endfor %}

{{ conclusion }}

{{ call_to_action }}

#{{ hashtags | join(' #') }}
```

**Variables Example:**
```json
["topic", "introduction", "key_points", "conclusion", "call_to_action", "hashtags"]
```

**Query: Get Template for User (fallback to default)**
```sql
SELECT * FROM templates
WHERE template_type = $1
  AND (user_id = $2 OR (user_id IS NULL AND is_default = TRUE))
ORDER BY user_id DESC NULLS LAST
LIMIT 1;
```

**Seed Default Template:**
```sql
INSERT INTO templates (user_id, template_type, template_name, template_content, variables, is_default)
VALUES (
    NULL,
    'linkedin',
    'Default LinkedIn Post',
    '# {{ topic }}\n\n{{ content }}\n\n#{{ tags | join(" #") }}',
    '["topic", "content", "tags"]',
    TRUE
);
```

---

### 8. config

**Purpose:** System-wide configuration settings

```sql
CREATE TABLE config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Columns:**
- `key`: Configuration key (unique identifier)
- `value`: JSONB value (supports any data type)
- `description`: Human-readable description
- `updated_at`: Last update timestamp

**Seed Configuration:**
```sql
INSERT INTO config (key, value, description) VALUES
    ('max_context_messages', '10', 'Number of recent messages to include in LLM context'),
    ('rag_top_k', '12', 'Number of chunks to retrieve from Qdrant'),
    ('chunk_size', '700', 'Target chunk size in tokens'),
    ('chunk_overlap_percent', '20', 'Overlap percentage for chunking'),
    ('session_expires_days', '7', 'Session expiration in days');
```

**Query: Get Config Value**
```sql
SELECT value FROM config WHERE key = $1;
```

---

## Qdrant Vector Database Schema

### Collection: youtube_chunks

**Configuration:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="youtube_chunks",
    vectors_config=VectorParams(
        size=1024,  # OpenRouter embeddings-small dimension
        distance=Distance.COSINE
    )
)
```

**Point Structure:**
```python
{
    "id": "chunk-uuid-from-postgres",  # UUID as string
    "vector": [0.123, 0.456, ...],     # 1024-dim embedding
    "payload": {
        "chunk_id": "chunk-uuid",
        "user_id": "user-uuid",
        "youtube_video_id": "dQw4w9WgXcQ",
        "chunk_index": 0,
        "transcript_id": "transcript-uuid"
    }
}
```

**Search Query Example:**
```python
results = client.search(
    collection_name="youtube_chunks",
    query_vector=query_embedding,
    limit=12,
    query_filter={
        "must": [
            {"key": "user_id", "match": {"value": user_uuid}}
        ]
    }
)
```

**Payload Indexes:**
```python
# Create payload indexes for fast filtering
client.create_payload_index(
    collection_name="youtube_chunks",
    field_name="user_id",
    field_schema="keyword"
)

client.create_payload_index(
    collection_name="youtube_chunks",
    field_name="youtube_video_id",
    field_schema="keyword"
)
```

---

## Migration Strategy

### Using Alembic

**Initial Migration (creates all tables):**
```bash
# Initialize Alembic
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

**Migration File Structure:**
```
alembic/
├── versions/
│   └── 001_initial_schema.py
├── env.py
└── alembic.ini
```

**Sample Migration (001_initial_schema.py):**
```python
def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    # ... (create other tables)
```

---

## Data Retention & Cleanup

**Automated Cleanup Jobs:**

1. **Expired Sessions:**
```sql
-- Run daily via cron
DELETE FROM sessions WHERE expires_at < NOW();
```

2. **Orphaned Qdrant Points (if chunk deleted):**
```python
# Sync job: Remove Qdrant points for deleted chunks
async def cleanup_qdrant():
    db_chunk_ids = await db.fetch_all("SELECT id FROM chunks")
    qdrant_points = client.scroll(collection_name="youtube_chunks", limit=10000)

    db_ids = {str(row['id']) for row in db_chunk_ids}
    qdrant_ids = {point.id for point in qdrant_points}

    orphaned = qdrant_ids - db_ids
    if orphaned:
        client.delete(collection_name="youtube_chunks", points_selector=list(orphaned))
```

---

## Backup & Restore

**PostgreSQL Backup:**
```bash
# Full backup
pg_dump -U postgres youtube_talker > backup.sql

# Restore
psql -U postgres youtube_talker < backup.sql
```

**Qdrant Snapshot:**
```python
# Create snapshot
client.create_snapshot(collection_name="youtube_chunks")

# Download snapshot
snapshot_info = client.list_snapshots(collection_name="youtube_chunks")[0]
client.download_snapshot(collection_name="youtube_chunks", snapshot_name=snapshot_info.name)
```

---

## Performance Considerations

**Index Strategy:**
- All foreign keys are indexed
- Frequently filtered columns (user_id, conversation_id) have indexes
- JSONB columns use GIN indexes for metadata queries
- Qdrant payload indexes for user_id and youtube_video_id

**Query Optimization:**
- Use `EXPLAIN ANALYZE` for slow queries
- Consider partitioning messages table if > 1M rows
- Use connection pooling (SQLAlchemy async pool)

**Expected Data Volume (1 year, 1 active user):**
- Users: 1 row
- Sessions: ~50 rows (7-day expiry)
- Conversations: ~100 rows
- Messages: ~10,000 rows
- Transcripts: ~500 rows (1-2 videos/day)
- Chunks: ~50,000 rows (~100 chunks/video)
- Templates: ~5 rows
- Qdrant: ~50,000 points

**Storage Estimate:**
- PostgreSQL: ~500 MB
- Qdrant: ~200 MB (1024-dim vectors)

---

## Security Notes

1. **Never store plaintext passwords** - Always use bcrypt with salt
2. **Hash session tokens** - Store SHA-256 hash, not raw token
3. **Use parameterized queries** - SQLAlchemy ORM prevents SQL injection
4. **Validate UUIDs** - Ensure user_id from session matches requested resources
5. **Row-level security** - All queries filter by user_id where applicable

---

## Appendix: Example Queries

**Get User's Conversations with Last Message:**
```sql
SELECT
    c.id,
    c.title,
    c.updated_at,
    (
        SELECT content
        FROM messages
        WHERE conversation_id = c.id
        ORDER BY created_at DESC
        LIMIT 1
    ) as last_message
FROM conversations c
WHERE c.user_id = $1
ORDER BY c.updated_at DESC;
```

**Get Conversation with Messages:**
```sql
SELECT
    m.id,
    m.role,
    m.content,
    m.metadata,
    m.created_at
FROM messages m
WHERE m.conversation_id = $1
ORDER BY m.created_at ASC;
```

**Get Transcript with Chunk Count:**
```sql
SELECT
    t.id,
    t.youtube_video_id,
    t.title,
    COUNT(c.id) as chunk_count
FROM transcripts t
LEFT JOIN chunks c ON c.transcript_id = t.id
WHERE t.user_id = $1
GROUP BY t.id;
```

---

**Document Version History:**
- v1.0 (2025-10-17): Initial schema design
