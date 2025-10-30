# Video Limits & Quota System - Analysis Report

**Date:** 2025-10-30
**Status:** 🔴 Critical Issues Found
**Priority:** High

---

## Executive Summary

The video quota system is **partially implemented** with critical gaps:
- ✅ Quota enforcement works for new video loads
- ❌ No video deletion functionality (API endpoint missing)
- ❌ No counter decrement mechanism (users get permanently locked out)
- ⚠️ Misleading error message suggests deletion is possible

**Impact:** Users who reach 10 videos are **permanently locked out** until manual database intervention.

---

## Implementation Overview

### Database Schema

**File:** `backend/app/db/models.py:57`

```python
transcript_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
```

**Migration:** `1a95e025e49d_add_user_role_and_transcript_count.py`
- Added `role` column (enum: 'user', 'admin') with default 'user'
- Added `transcript_count` column with default 0
- Created index on `role` for fast role-based queries

**Constraints:**
- None currently (missing CHECK constraint for max limit)

---

## Quota Check Logic

**File:** `backend/app/api/websocket/video_loader.py:111-144`

```python
async def check_user_quota(user: User, db: AsyncSession) -> tuple[bool, str]:
    """
    Check if user can load another video.

    Returns:
        (allowed: bool, error_message: str)
    """
    if user.role == "admin":
        return True, ""

    if user.transcript_count >= 10:
        return False, (
            "You've reached your video limit (10 videos). "
            "Delete some videos to add more, or contact support for an upgrade."
        )

    return True, ""
```

**Quota Limits:**
- **Regular users:** 10 videos maximum
- **Admin users:** Unlimited

**Enforcement Point:** `video_loader.py:406` (before video load confirmation)

---

## Increment Mechanism

**File:** `backend/app/db/repositories/user_repo.py:49-79`

```python
async def increment_transcript_count(self, user_id: UUID) -> None:
    """
    Increment the transcript_count for a user atomically.
    Uses atomic UPDATE to prevent race conditions.
    """
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(transcript_count=User.transcript_count + 1)
    )
    result = await self.session.execute(stmt)

    if result.rowcount == 0:
        raise ValueError(f"User {user_id} not found")

    await self.session.flush()
```

**Called from:** `video_loader.py:631` (after successful ingestion)

**Concurrency:** Uses SQL-level atomic UPDATE (safe for concurrent loads)

---

## Current Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Video Load Request                                          │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Validate YouTube URL  │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Check Duration Limit  │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Check User Quota      │◄─────────── Currently here
                    │ (10 videos max)       │
                    └───────────┬───────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
        ┌───────────────┐            ┌──────────────────┐
        │ Quota Exceeded│            │ Store Pending    │
        │ Send Error    │            │ Request          │
        └───────────────┘            └─────────┬────────┘
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │ User Confirms    │
                                    │ (yes/no)         │
                                    └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Ingest Video     │
                                    │ (background task)│
                                    └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Increment Count  │
                                    │ (atomic SQL)     │
                                    └─────────┬────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Success          │
                                    └──────────────────┘
```

---

## 🔴 Critical Issues

### Issue 1: No Decrement Function

**Problem:**
- No `decrement_transcript_count()` method exists in `UserRepository`
- Once user hits 10 videos, they're **permanently locked out**
- Even if they delete transcripts from database manually, count never decreases

**Impact:**
- Users cannot manage their quota
- Requires manual database intervention (UPDATE users SET transcript_count = ...)
- Poor user experience

**Files affected:**
- `backend/app/db/repositories/user_repo.py` (missing method)
- `backend/app/api/routes/transcripts.py` (no DELETE endpoint to call it)

---

### Issue 2: No Video Deletion API Endpoint

**Problem:**
- Only `POST /api/transcripts/ingest` endpoint exists
- No `DELETE /api/transcripts/{id}` endpoint implemented
- Users have **no way to delete videos** through the application

**Current API:**
```python
# backend/app/api/routes/transcripts.py
router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])

@router.post("/ingest", response_model=TranscriptResponse, status_code=201)
async def ingest_transcript(...):
    # Only ingestion endpoint exists
```

**Missing endpoint:**
```python
# This doesn't exist yet:
@router.delete("/{transcript_id}", status_code=204)
async def delete_transcript(transcript_id: UUID, ...):
    # Would need to:
    # 1. Verify user owns transcript
    # 2. Delete chunks from Qdrant
    # 3. Delete transcript from PostgreSQL (cascades to chunks)
    # 4. Decrement user.transcript_count
```

**Impact:**
- Error message is misleading: "Delete some videos to add more" - but no delete functionality exists!
- Users get frustrated when they can't follow the suggested action

---

### Issue 3: Race Condition Risk

**Problem:**
Between `check_user_quota()` and `increment_transcript_count()`, concurrent requests could exceed limit.

**Scenario:**
```
Time  │ Request A                │ Request B
──────┼──────────────────────────┼──────────────────────────
t0    │ User has 9 videos        │
t1    │ check_user_quota()       │
t2    │ → allowed (9 < 10)       │
t3    │                          │ check_user_quota()
t4    │                          │ → allowed (9 < 10)
t5    │ ingest_video()           │
t6    │                          │ ingest_video()
t7    │ increment_count() → 10   │
t8    │                          │ increment_count() → 11 ⚠️
```

**Result:** User ends up with 11 videos (exceeds limit)

**Mitigation:** Add database CHECK constraint:
```sql
ALTER TABLE users
ADD CONSTRAINT check_user_transcript_limit
CHECK (role = 'admin' OR transcript_count <= 10);
```

---

## ✅ What's Working

1. **Quota enforcement for new loads**
   - Properly checks count before allowing video load
   - Blocks requests when limit reached

2. **Admin unlimited access**
   - Admin users can load unlimited videos
   - Role-based differentiation works

3. **Atomic counter increment**
   - Uses SQL UPDATE for thread-safety
   - No race conditions during increment itself

4. **Clear error message**
   - User-facing message explains the limit
   - Mentions upgrade path (though misleading about deletion)

---

## Required Fixes

### Priority 1: Implement Video Deletion (Critical)

**Tasks:**
1. Add `decrement_transcript_count()` to `UserRepository`
2. Create `DELETE /api/transcripts/{transcript_id}` endpoint
3. Implement deletion service that:
   - Verifies user ownership
   - Deletes vectors from Qdrant
   - Deletes transcript from PostgreSQL (cascades to chunks)
   - Decrements user counter
4. Add frontend UI for video deletion
5. Write tests for deletion flow

**Estimated effort:** 4-6 hours

---

### Priority 2: Add Database Constraint (High)

**Task:** Add CHECK constraint to prevent exceeding limit via race condition

**Migration:**
```sql
-- alembic migration
ALTER TABLE users
ADD CONSTRAINT check_user_transcript_limit
CHECK (role = 'admin' OR transcript_count <= 10);
```

**Estimated effort:** 30 minutes

---

### Priority 3: Update Error Message (Medium)

**Current:**
```python
"You've reached your video limit (10 videos). "
"Delete some videos to add more, or contact support for an upgrade."
```

**Option A (if deletion not implemented yet):**
```python
"You've reached your video limit (10 videos). "
"Contact support for an upgrade or to manage your videos."
```

**Option B (after deletion implemented):**
```python
"You've reached your video limit (10 videos). "
"Go to 'My Videos' to delete some, or contact support for an upgrade."
```

**Estimated effort:** 5 minutes

---

## Testing Recommendations

### Unit Tests Needed

1. **test_check_user_quota.py**
   - ✅ Already exists (`tests/unit/test_video_loader.py`)
   - Covers: regular user at limit, admin unlimited, under limit

2. **test_increment_transcript_count.py** (NEW)
   - Test atomic increment
   - Test user not found error
   - Test concurrent increments

3. **test_decrement_transcript_count.py** (NEW)
   - Test atomic decrement
   - Test cannot go below 0
   - Test user not found error

4. **test_delete_transcript_endpoint.py** (NEW)
   - Test successful deletion
   - Test ownership verification
   - Test counter decrement
   - Test 404 if not found
   - Test 403 if not owned by user

---

### Integration Tests Needed

1. **test_quota_full_flow.py** (NEW)
   - Load 10 videos → hit limit → verify blocked
   - Delete 1 video → verify can load again
   - Verify counter accuracy throughout

2. **test_quota_race_condition.py** (NEW)
   - Simulate concurrent loads at limit boundary
   - Verify database constraint prevents exceeding

---

## Code References

**Key files:**
- `backend/app/db/models.py:57` - User.transcript_count field
- `backend/app/db/repositories/user_repo.py:49-79` - increment_transcript_count()
- `backend/app/api/websocket/video_loader.py:111-144` - check_user_quota()
- `backend/app/api/websocket/video_loader.py:406` - Quota enforcement point
- `backend/app/api/websocket/video_loader.py:631` - Counter increment call
- `backend/app/api/routes/transcripts.py` - Transcript API endpoints
- `backend/alembic/versions/1a95e025e49d_add_user_role_and_transcript_count.py` - Migration

---

## Related Documentation

- **HANDOFF.md** - Backend development checklist
- **DATABASE_SCHEMA.md** - Full database schema
- **PRD.md** - Product requirements for quota system

---

## Conclusion

The quota system is **functional for blocking new loads** but **incomplete for user management**. The most critical issue is the lack of video deletion functionality, which makes users unable to recover from reaching their limit. This should be prioritized before production release.

**Recommended action:** Implement video deletion (Priority 1) before considering quota system "complete."

---

**Last Updated:** 2025-10-30
**Reviewed By:** Claude Code (automated analysis)
