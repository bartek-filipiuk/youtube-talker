# Video List Sidebar Implementation Plan

**Feature**: Video List Component in Chat Sidebar
**Created**: 2025-11-01
**Status**: Planning

---

## Overview

Add a video list component to the chat page sidebar that displays the 10 most recently added videos with delete functionality. This component will be positioned above the existing conversation list.

---

## Requirements Summary

Based on user requirements clarification:

1. **Position**: Above chat conversation list in sidebar
2. **Backend API**: Use existing endpoints (confirmed available)
3. **Delete Flow**: Show confirmation dialog before deleting
4. **Pagination**: Previous and Next buttons (10 videos per page)
5. **Display**: Title only (full text, non-clickable)
6. **Empty State**: Show friendly message "No videos yet"
7. **Loading/Error**: Inline text messages (non-blocking)
8. **Side Effects**: Deleting video keeps associated chat conversations

---

## Backend Changes

### 1. Create GET Endpoint with Pagination
**File**: `backend/app/api/routes/transcripts.py`

Add new endpoint:
```python
@router.get("/", response_model=VideoListResponse)
@limiter.limit("30/minute")
async def list_transcripts(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoListResponse:
    """
    Get paginated list of user's transcripts.

    Returns list of videos with minimal data (id, title, created_at)
    plus total count for pagination.
    """
```

**Key Details**:
- Endpoint: `GET /api/transcripts?limit=10&offset=0`
- Auth required: Yes (get_current_user dependency)
- Rate limit: 30/minute per IP
- Returns: List of videos + total count

### 2. Add Lightweight Response Schema
**File**: `backend/app/schemas/transcript.py`

Create new schemas:
```python
class VideoListItem(BaseModel):
    """Lightweight schema for video list display"""
    id: str  # UUID as string
    title: str  # From metadata.title
    created_at: datetime

    class Config:
        from_attributes = True

class VideoListResponse(BaseModel):
    """Paginated video list response"""
    videos: List[VideoListItem]
    total: int
    limit: int
    offset: int
```

**Why**: Existing `TranscriptResponse` is too heavy (includes chunk_count, full metadata). List view only needs id + title.

### 3. Update Repository
**File**: `backend/app/db/repositories/transcript_repo.py`

Modify `list_by_user()` method:
```python
async def list_by_user(
    self,
    user_id: UUID,
    limit: int = 10,
    offset: int = 0
) -> Tuple[List[Transcript], int]:
    """
    List transcripts for user with pagination.

    Returns:
        Tuple of (list of transcripts, total count)
    """
    # Query for transcripts with limit/offset
    result = await self.session.execute(
        select(Transcript)
        .where(Transcript.user_id == user_id)
        .order_by(Transcript.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    transcripts = list(result.scalars().all())

    # Query for total count
    count_result = await self.session.execute(
        select(func.count(Transcript.id))
        .where(Transcript.user_id == user_id)
    )
    total = count_result.scalar_one()

    return transcripts, total
```

**Note**: Currently returns all transcripts. Add limit/offset parameters + total count.

---

## Frontend Changes

### 4. Create Video Store
**File**: `frontend/src/stores/videos.ts` (NEW)

State management for video list:
```typescript
import { atom } from 'nanostores';

export interface Video {
  id: string;
  title: string;
  created_at: string;
}

export interface VideoListState {
  videos: Video[];
  total: number;
  currentPage: number;
  limit: number;
  loading: boolean;
  error: string | null;
}

export const $videoList = atom<VideoListState>({
  videos: [],
  total: 0,
  currentPage: 0,
  limit: 10,
  loading: false,
  error: null
});

// Actions
export function setVideos(videos: Video[], total: number) {
  $videoList.set({
    ...$videoList.get(),
    videos,
    total,
    loading: false,
    error: null
  });
}

export function setLoading(loading: boolean) {
  $videoList.set({ ...$videoList.get(), loading });
}

export function setError(error: string) {
  $videoList.set({ ...$videoList.get(), loading: false, error });
}

export function removeVideo(videoId: string) {
  const state = $videoList.get();
  $videoList.set({
    ...state,
    videos: state.videos.filter(v => v.id !== videoId),
    total: state.total - 1
  });
}

export function nextPage() {
  const state = $videoList.get();
  const maxPage = Math.ceil(state.total / state.limit) - 1;
  if (state.currentPage < maxPage) {
    $videoList.set({ ...state, currentPage: state.currentPage + 1 });
  }
}

export function prevPage() {
  const state = $videoList.get();
  if (state.currentPage > 0) {
    $videoList.set({ ...state, currentPage: state.currentPage - 1 });
  }
}
```

### 5. Create API Client Methods
**File**: `frontend/src/lib/api.ts`

Add video list methods:
```typescript
export async function getVideos(
  token: string,
  limit: number = 10,
  offset: number = 0
): Promise<{ videos: Video[]; total: number }> {
  const url = `${API_URL}/api/transcripts?limit=${limit}&offset=${offset}`;
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch videos: ${response.statusText}`);
  }

  return response.json();
}

export async function deleteTranscript(
  token: string,
  transcriptId: string
): Promise<void> {
  const url = `${API_URL}/api/transcripts/${transcriptId}`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to delete transcript: ${response.statusText}`);
  }
}
```

**Note**: Reuse existing DELETE endpoint at `/api/transcripts/{transcript_id}` (already exists in backend at line 94-160 of `transcripts.py`).

### 6. Create VideoList Component
**File**: `frontend/src/components/VideoList.astro` (NEW)

Follow the pattern from `ConversationList.astro`:
```astro
---
/**
 * Video List Component
 *
 * Displays paginated list of user's videos with delete functionality
 */
---

<div class="bg-gray-50 border-b border-gray-200 p-4">
  <!-- Header -->
  <h3 class="text-sm font-semibold text-gray-700 mb-3">Your Videos</h3>

  <!-- Video List -->
  <div id="videosList" class="space-y-2 mb-3">
    <!-- Populated by client-side script -->
  </div>

  <!-- Pagination Controls -->
  <div id="videoPagination" class="flex justify-between items-center text-sm hidden">
    <button
      id="prevPageBtn"
      class="px-3 py-1 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
      disabled
    >
      ← Previous
    </button>
    <span id="pageInfo" class="text-gray-500"></span>
    <button
      id="nextPageBtn"
      class="px-3 py-1 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
      disabled
    >
      Next →
    </button>
  </div>

  <!-- Loading/Error States -->
  <div id="videoLoading" class="text-xs text-gray-500 hidden">Loading videos...</div>
  <div id="videoError" class="text-xs text-red-600 hidden"></div>
</div>

<script>
  import { requireAuth } from '../lib/auth';
  import { getVideos, deleteTranscript } from '../lib/api';
  import { $videoList, setVideos, setLoading, setError, removeVideo, nextPage, prevPage } from '../stores/videos';

  // Ensure user is authenticated
  const auth = await requireAuth();
  if (!auth) {
    throw new Error('Not authenticated');
  }

  const { token } = auth;

  // DOM elements
  const videosList = document.getElementById('videosList') as HTMLDivElement;
  const videoPagination = document.getElementById('videoPagination') as HTMLDivElement;
  const prevPageBtn = document.getElementById('prevPageBtn') as HTMLButtonElement;
  const nextPageBtn = document.getElementById('nextPageBtn') as HTMLButtonElement;
  const pageInfo = document.getElementById('pageInfo') as HTMLSpanElement;
  const videoLoading = document.getElementById('videoLoading') as HTMLDivElement;
  const videoError = document.getElementById('videoError') as HTMLDivElement;

  // Load videos
  async function loadVideos() {
    const state = $videoList.get();
    setLoading(true);
    videoLoading.classList.remove('hidden');
    videoError.classList.add('hidden');

    try {
      const offset = state.currentPage * state.limit;
      const data = await getVideos(token, state.limit, offset);
      setVideos(data.videos, data.total);
    } catch (error: any) {
      console.error('Failed to load videos:', error);
      setError(error.message);
      videoError.textContent = 'Failed to load videos';
      videoError.classList.remove('hidden');
    } finally {
      videoLoading.classList.add('hidden');
    }
  }

  // Escape HTML
  function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Render videos
  function renderVideos() {
    const state = $videoList.get();

    // Empty state
    if (state.videos.length === 0 && !state.loading) {
      videosList.innerHTML = '<p class="text-xs text-gray-500">No videos yet</p>';
      videoPagination.classList.add('hidden');
      return;
    }

    // Render video list
    videosList.innerHTML = state.videos
      .map((video) => `
        <div class="group flex items-start justify-between p-2 bg-white rounded border border-gray-200">
          <div class="flex-1 min-w-0 pr-2">
            <p class="text-xs text-gray-900 truncate" title="${escapeHtml(video.title)}">
              ${escapeHtml(video.title)}
            </p>
          </div>
          <button
            class="delete-video-btn opacity-0 group-hover:opacity-100 transition p-1 text-gray-400 hover:text-red-600"
            data-id="${video.id}"
            data-title="${escapeHtml(video.title)}"
            title="Delete video"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      `)
      .join('');

    // Update pagination
    const totalPages = Math.ceil(state.total / state.limit);
    if (totalPages > 1) {
      videoPagination.classList.remove('hidden');
      pageInfo.textContent = `Page ${state.currentPage + 1} of ${totalPages}`;
      prevPageBtn.disabled = state.currentPage === 0;
      nextPageBtn.disabled = state.currentPage >= totalPages - 1;
    } else {
      videoPagination.classList.add('hidden');
    }

    // Attach delete handlers
    document.querySelectorAll('.delete-video-btn').forEach((btn) => {
      btn.addEventListener('click', handleDelete);
    });
  }

  // Handle delete
  async function handleDelete(e: Event) {
    e.stopPropagation();

    const btn = e.currentTarget as HTMLButtonElement;
    const videoId = btn.getAttribute('data-id');
    const title = btn.getAttribute('data-title');

    if (!videoId) return;

    // Confirmation dialog
    const confirmed = confirm(
      `Delete video "${title}"?\n\nThis will delete the transcript but keep your chat conversations.`
    );
    if (!confirmed) return;

    try {
      await deleteTranscript(token, videoId);
      removeVideo(videoId);

      // Reload if page is now empty and not first page
      const state = $videoList.get();
      if (state.videos.length === 0 && state.currentPage > 0) {
        prevPage();
        await loadVideos();
      }
    } catch (error: any) {
      alert('Failed to delete video: ' + error.message);
    }
  }

  // Pagination handlers
  prevPageBtn.addEventListener('click', async () => {
    prevPage();
    await loadVideos();
  });

  nextPageBtn.addEventListener('click', async () => {
    nextPage();
    await loadVideos();
  });

  // Subscribe to store changes
  $videoList.subscribe(() => {
    renderVideos();
  });

  // Initial load
  loadVideos();
</script>
```

**Key Features**:
- Follows ConversationList pattern (auth check, state management, delete confirmation)
- Empty state: "No videos yet"
- Loading/Error: Inline text messages
- Delete: Confirmation dialog + keeps chats
- Pagination: Prev/Next buttons with page info

### 7. Integrate into Chat Page
**File**: `frontend/src/pages/chat.astro`

Update sidebar to include VideoList above ConversationList:
```astro
<!-- Conversation Sidebar - Hidden on mobile, visible on tablet+ -->
<aside class="hidden md:block w-80 flex-shrink-0 flex flex-col">
  <!-- Add VideoList at top -->
  <VideoList />

  <!-- Existing ConversationList below -->
  <div class="flex-1 overflow-hidden">
    <ConversationList activeId={activeConversationId} />
  </div>
</aside>
```

Import at top of file:
```astro
---
import Layout from '../layouts/Layout.astro';
import ChatInput from '../components/ChatInput.astro';
import ConversationList from '../components/ConversationList.astro';
import VideoList from '../components/VideoList.astro';  // ADD THIS

// Get conversation ID from URL (for highlighting active conversation)
const urlParams = new URLSearchParams(Astro.url.search);
const activeConversationId = urlParams.get('id');
---
```

---

## Implementation Order

### Phase 1: Backend (Test-Driven)
1. ✅ Create `VideoListItem` and `VideoListResponse` schemas in `transcript.py`
2. ✅ Update `TranscriptRepository.list_by_user()` to support pagination
3. ✅ Write unit tests for repository pagination
4. ✅ Create GET endpoint in `transcripts.py`
5. ✅ Write integration tests for GET endpoint

### Phase 2: Frontend
6. ✅ Create video store (`src/stores/videos.ts`)
7. ✅ Add API methods to `src/lib/api.ts`
8. ✅ Create `VideoList.astro` component
9. ✅ Integrate into `chat.astro`

### Phase 3: Testing
10. ✅ Test delete flow end-to-end (confirmation → API → UI update)
11. ✅ Test pagination (prev/next, edge cases)
12. ✅ Test empty state, loading state, error handling
13. ✅ Use Chrome DevTools MCP for real browser testing (see below)

---

## Testing with Chrome DevTools MCP

After implementation, you can test the video list component in a real browser using the Chrome DevTools MCP server:

### Manual Testing Flow

1. **Navigate to chat page**:
   ```typescript
   // Use MCP tools to navigate
   await mcp__chrome-devtools__navigate_page({ url: 'http://localhost:4321/chat' });
   ```

2. **Take snapshot to verify component rendered**:
   ```typescript
   await mcp__chrome-devtools__take_snapshot({ verbose: false });
   ```
   - Look for "Your Videos" heading
   - Verify video list items are visible
   - Check pagination controls

3. **Test delete button**:
   ```typescript
   // Click delete button on first video
   await mcp__chrome-devtools__click({ uid: 'delete-button-uid-from-snapshot' });

   // Handle confirmation dialog
   await mcp__chrome-devtools__handle_dialog({ action: 'accept' });

   // Take snapshot to verify video removed
   await mcp__chrome-devtools__take_snapshot({ verbose: false });
   ```

4. **Test pagination**:
   ```typescript
   // Click Next button
   await mcp__chrome-devtools__click({ uid: 'next-button-uid' });

   // Wait for loading
   await mcp__chrome-devtools__wait_for({ text: 'Page 2 of' });

   // Verify page updated
   await mcp__chrome-devtools__take_snapshot({ verbose: false });
   ```

5. **Verify network requests**:
   ```typescript
   // List all requests to check API calls
   await mcp__chrome-devtools__list_network_requests({
     resourceTypes: ['xhr', 'fetch']
   });

   // Check specific GET request
   await mcp__chrome-devtools__get_network_request({ reqid: 123 });
   ```

6. **Check console for errors**:
   ```typescript
   await mcp__chrome-devtools__list_console_messages({ types: ['error'] });
   ```

### Automated Test Scenarios

Use devtools MCP to verify:
- ✅ Component renders with correct structure
- ✅ Videos load on page mount
- ✅ Empty state displays when no videos
- ✅ Delete confirmation appears before deletion
- ✅ Video removed from list after delete
- ✅ Pagination buttons enable/disable correctly
- ✅ Page info shows correct page numbers
- ✅ Loading state appears during API calls
- ✅ Error messages display on API failures

---

## Key Design Decisions

### Why Above Conversation List?
- User requested: "put that block on chats only" positioned "above chat list"
- Videos are primary content for the app (transcripts)
- Conversations are secondary (discussions about videos)

### Why Title Only?
- Simplicity: User explicitly requested "only non clickable titles (full)"
- Performance: Minimal data transfer
- Focus: Video selection happens through chat, not video list

### Why Keep Chats on Delete?
- User may have valuable conversation history
- Chats reference videos but aren't dependent on transcript data
- Prevents accidental data loss

### Why Prev/Next (Not Infinite Scroll)?
- User requested: "Prev/Next only"
- Simpler implementation
- Clearer page position indicator
- Better for small datasets (10 items per page)

---

## Files Changed Summary

### Backend
- `backend/app/schemas/transcript.py` - Add `VideoListItem`, `VideoListResponse`
- `backend/app/db/repositories/transcript_repo.py` - Update `list_by_user()` method
- `backend/app/api/routes/transcripts.py` - Add GET endpoint

### Frontend
- `frontend/src/stores/videos.ts` - NEW (video state management)
- `frontend/src/lib/api.ts` - Add `getVideos()`, `deleteTranscript()` methods
- `frontend/src/components/VideoList.astro` - NEW (main component)
- `frontend/src/pages/chat.astro` - Import and add VideoList component

### Tests
- `backend/tests/unit/test_transcript_repo.py` - Add pagination tests
- `backend/tests/integration/test_transcripts_api.py` - Add GET endpoint tests

---

## Success Criteria

- ✅ Video list displays 10 videos per page
- ✅ Pagination works (prev/next buttons, page info)
- ✅ Delete shows confirmation and removes video
- ✅ Empty state shows friendly message
- ✅ Loading/error states display inline
- ✅ Component only visible on chat page
- ✅ Positioned above conversation list
- ✅ Tests pass (80% coverage minimum)
- ✅ Real browser testing via Chrome DevTools MCP confirms functionality

---

**Next Steps**: Exit plan mode and begin implementation following TDD approach.