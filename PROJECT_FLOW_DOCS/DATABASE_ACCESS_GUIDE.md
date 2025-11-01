# PostgreSQL Database Access Guide

Quick reference for accessing and inspecting the PostgreSQL database running in Docker.

---

## Table of Contents
1. [Connection Information](#connection-information)
2. [Docker Commands](#docker-commands)
3. [PostgreSQL CLI Commands](#postgresql-cli-commands)
4. [Common Inspection Queries](#common-inspection-queries)
5. [Troubleshooting](#troubleshooting)

---

## Connection Information

**From `.env` file:**
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/youtube_talker
```

**Connection details:**
- **Host (from host machine)**: localhost
- **Port (from host machine)**: 5435
- **Host (inside container)**: postgres (from docker-compose network)
- **Port (inside container)**: 5432
- **Database**: youtube_talker
- **Username**: postgres
- **Password**: postgres
- **Container name**: youtube-talker-postgres

---

## Docker Commands

### 1. Find PostgreSQL Container Name

```bash
docker ps | grep postgres
```

Output:
```
youtube-talker-postgres   ...   Up   0.0.0.0:5435->5432/tcp
```

### 2. Execute Single SQL Query (One-liner)

**Syntax:**
```bash
docker exec <container-name> psql -U <username> -d <database> -c "<SQL query>"
```

**Example:**
```bash
docker exec youtube-talker-postgres psql -U postgres -d youtube_talker -c "SELECT COUNT(*) FROM users;"
```

### 3. Connect to Interactive PostgreSQL CLI

**Option A: Direct connection**
```bash
docker exec -it youtube-talker-postgres psql -U postgres -d youtube_talker
```

**Option B: Connect to container shell first**
```bash
# Enter container bash
docker exec -it youtube-talker-postgres bash

# Then connect to PostgreSQL
psql -U postgres -d youtube_talker
```

**Exit:**
- From psql: `\q` or `Ctrl+D`
- From container bash: `exit` or `Ctrl+D`

### 4. Run SQL File from Host Machine

```bash
docker exec -i youtube-talker-postgres psql -U postgres -d youtube_talker < /path/to/script.sql
```

### 5. Backup Database

```bash
docker exec youtube-talker-postgres pg_dump -U postgres youtube_talker > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 6. Restore Database

```bash
docker exec -i youtube-talker-postgres psql -U postgres -d youtube_talker < backup.sql
```

---

## PostgreSQL CLI Commands

### Meta-Commands (start with `\`)

Once connected with `psql`, use these meta-commands:

| Command | Description |
|---------|-------------|
| `\l` | List all databases |
| `\dt` | List all tables in current database |
| `\d table_name` | Describe table schema (columns, types, constraints) |
| `\d+ table_name` | Detailed table info (includes indexes, triggers) |
| `\di` | List all indexes |
| `\du` | List all roles/users |
| `\dn` | List all schemas |
| `\df` | List all functions |
| `\x` | Toggle expanded display (vertical format) |
| `\timing` | Toggle query execution time display |
| `\?` | Show all psql commands |
| `\h SQL_COMMAND` | Show SQL command help (e.g., `\h SELECT`) |
| `\q` | Quit psql |

### Useful Settings

```sql
-- Enable expanded display (vertical format for wide rows)
\x

-- Show query execution time
\timing

-- Set pagination off (show all results at once)
\pset pager off
```

---

## Common Inspection Queries

### 1. List All Tables

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';
```

**Or using psql meta-command:**
```sql
\dt
```

### 2. View Table Schema

```sql
-- Using psql meta-command (recommended)
\d users

-- Or SQL query
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position;
```

### 3. Check Table Row Counts

```sql
SELECT
    schemaname,
    tablename,
    n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
```

**Quick counts:**
```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM transcripts;
SELECT COUNT(*) FROM chunks;
SELECT COUNT(*) FROM conversations;
SELECT COUNT(*) FROM messages;
```

### 4. View Table Constraints

```sql
-- All constraints on a table
SELECT
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'users'::regclass;

-- Or using psql meta-command
\d+ users
```

### 5. Check Indexes

```sql
-- All indexes on a table
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'users';

-- Or using psql meta-command
\di
```

### 6. View Foreign Keys

```sql
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name;
```

### 7. View Recent Migrations (Alembic)

```sql
SELECT * FROM alembic_version;
```

### 8. Check Active Database Connections

```sql
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity
WHERE datname = 'youtube_talker';
```

### 9. Check Table Sizes

```sql
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 10. Inspect User Data

```sql
-- View all users
SELECT id, email, role, transcript_count, created_at
FROM users
ORDER BY created_at DESC;

-- View users with video counts
SELECT
    u.id,
    u.email,
    u.role,
    u.transcript_count,
    COUNT(t.id) AS actual_transcript_count
FROM users u
LEFT JOIN transcripts t ON u.id = t.user_id
GROUP BY u.id, u.email, u.role, u.transcript_count
ORDER BY u.created_at DESC;
```

### 11. Inspect Transcripts

```sql
-- View all transcripts with user info
SELECT
    t.id,
    t.youtube_video_id,
    t.title,
    u.email AS user_email,
    t.created_at
FROM transcripts t
JOIN users u ON t.user_id = u.id
ORDER BY t.created_at DESC;

-- Count chunks per transcript
SELECT
    t.id AS transcript_id,
    t.youtube_video_id,
    COUNT(c.id) AS chunk_count
FROM transcripts t
LEFT JOIN chunks c ON t.id = c.transcript_id
GROUP BY t.id, t.youtube_video_id
ORDER BY chunk_count DESC;
```

### 12. Check for Orphaned Data

```sql
-- Chunks without transcripts (should be 0)
SELECT COUNT(*)
FROM chunks c
LEFT JOIN transcripts t ON c.transcript_id = t.id
WHERE t.id IS NULL;

-- Transcripts without users (should be 0)
SELECT COUNT(*)
FROM transcripts t
LEFT JOIN users u ON t.user_id = u.id
WHERE u.id IS NULL;
```

---

## Troubleshooting

### Problem: Can't Connect to Database

**Check if container is running:**
```bash
docker ps | grep postgres
```

**Check container logs:**
```bash
docker logs youtube-talker-postgres
```

**Restart container:**
```bash
docker compose restart postgres
```

### Problem: "Idle in Transaction" Blocking Queries

**Find blocking sessions:**
```sql
SELECT
    pid,
    state,
    query,
    wait_event,
    wait_event_type
FROM pg_stat_activity
WHERE datname = 'youtube_talker'
AND state <> 'idle'
ORDER BY state_change;
```

**Terminate specific session:**
```sql
SELECT pg_terminate_backend(12345);  -- Replace 12345 with actual PID
```

**Terminate all idle sessions:**
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'youtube_talker'
AND state = 'idle in transaction'
AND state_change < NOW() - INTERVAL '5 minutes';
```

### Problem: Migration Stuck or Failed

**Check current migration version:**
```bash
docker exec youtube-talker-postgres psql -U postgres -d youtube_talker -c "SELECT * FROM alembic_version;"
```

**Check if migration is in progress:**
```sql
SELECT pid, state, query
FROM pg_stat_activity
WHERE query LIKE '%ALTER TABLE%'
OR query LIKE '%CREATE TABLE%';
```

**Rollback migration (if needed):**
```bash
.venv/bin/alembic downgrade -1
```

### Problem: Database Lock Issues

**Check locks:**
```sql
SELECT
    l.locktype,
    l.mode,
    l.granted,
    a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE a.datname = 'youtube_talker';
```

---

## Quick Reference Card

### Most Used Commands

```bash
# Connect to database
docker exec -it youtube-talker-postgres psql -U postgres -d youtube_talker

# Quick query from host
docker exec youtube-talker-postgres psql -U postgres -d youtube_talker -c "SELECT COUNT(*) FROM users;"

# List tables
\dt

# Describe table
\d users

# Enable vertical output
\x

# Show query timing
\timing

# Count all rows
SELECT COUNT(*) FROM users;

# View recent data
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

# Quit
\q
```

---

## Database Schema Overview

**Main tables:**
- `users` - User accounts (auth + quota tracking)
- `transcripts` - YouTube video metadata
- `chunks` - Chunked transcript text (for RAG)
- `conversations` - User conversation sessions
- `messages` - Chat messages history
- `model_pricing` - LLM API cost tracking
- `alembic_version` - Migration version tracking

**Relationships:**
- `users` 1→N `transcripts`
- `users` 1→N `conversations`
- `transcripts` 1→N `chunks`
- `conversations` 1→N `messages`

---

**Last Updated:** 2025-11-01
**Database Version:** PostgreSQL 15
**Container:** youtube-talker-postgres
