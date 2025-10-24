# Frontend Option A - Bug Fixes & Core Features Plan

**Created:** 2025-10-24
**Status:** Approved - In Progress (PR #1)
**Estimated Time:** 5 hours
**Target:** Frontend MVP improvements
**Strategy:** 3 PRs (Foundation → Sidebar → Polish)

---

## ✅ Confirmed Specifications

1. **Markdown rendering:** Required for formatted AI responses
2. **Conversation creation:** URL query param is source of truth (create if missing, load if exists)
3. **Message persistence:** Backend auto-saves during WebSocket (no frontend action needed)
4. **Sidebar content:** Conversation titles only (clean & simple)

---

## 🔀 PR Strategy (Strategy A - 3 PRs)

### **PR #1: Foundation** ← **CURRENT**
- Tasks 1 + 2 (Markdown + Message History)
- Time: 1.5 hours
- Branch: `feature/frontend-markdown-history`

### **PR #2: Sidebar Feature**
- Task 3 (Conversation List)
- Time: 2 hours
- Branch: `feature/frontend-conversation-sidebar`

### **PR #3: Polish**
- Tasks 4 + 5 (Loading States + Responsive)
- Time: 1.5 hours
- Branch: `feature/frontend-polish-responsive`

---

## 🎯 Task Breakdown

### **Task 1: Add Markdown Rendering** (30 min)

**Goal:** Display formatted AI responses (bold, lists, code blocks, links)

**Files to modify:**
1. `frontend/src/lib/markdown.ts` (NEW) - Sanitization utility
2. `frontend/src/components/ChatMessage.astro` - Integrate markdown rendering

**Implementation:**

**Step 1.1:** Create markdown utility (`src/lib/markdown.ts`)
```typescript
import { marked } from 'marked';
import DOMPurify from 'dompurify';

export function renderMarkdown(content: string): string {
  const html = marked.parse(content);
  return DOMPurify.sanitize(html);
}
```

**Step 1.2:** Update ChatMessage component
- Import `renderMarkdown`
- For assistant messages: render with `set:html={renderMarkdown(content)}`
- For user messages: keep as plain text
- Add CSS classes for code blocks, lists, headings

**Acceptance Criteria:**
- ✅ Bold text renders as **bold**
- ✅ Lists render as bullet points
- ✅ Code blocks have background color
- ✅ Links are clickable
- ✅ No XSS vulnerabilities (DOMPurify sanitizes)

---

### **Task 2: Implement Message History Loading** (1 hour)

**Goal:** Load existing messages from backend when opening conversation

**Files to modify:**
1. `frontend/src/lib/api.ts` - Add conversation endpoints
2. `frontend/src/pages/chat.astro` - Load messages on page load
3. `frontend/src/stores/chat.ts` - Initialize with loaded messages

**Implementation:**

**Step 2.1:** Add API functions (`src/lib/api.ts`)
```typescript
export async function getConversation(token: string, id: string) {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) throw new Error('Failed to load conversation');
  return response.json();
}

export async function createConversation(token: string, title?: string) {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ title: title || 'New conversation' })
  });
  if (!response.ok) throw new Error('Failed to create conversation');
  return response.json();
}
```

**Step 2.2:** Update chat page (`src/pages/chat.astro`)
- Check for conversation_id in URL query param
- If missing: create new conversation, redirect to `/chat?id={new_id}`
- If exists: load conversation + messages from backend
- Pass messages to client-side store

**Step 2.3:** Initialize chat store with messages
- Pass messages to client-side script
- Load into `$messages` store
- Display in chat UI

**Acceptance Criteria:**
- ✅ Visiting `/chat` creates new conversation and redirects to `/chat?id=XXX`
- ✅ Visiting `/chat?id=XXX` loads existing messages
- ✅ Messages display in chronological order
- ✅ Page reload shows same messages (no duplication)

---

### **Task 3: Add Conversation List Sidebar** (2 hours) - PR #2

**Goal:** Display list of conversations with create/switch/delete functionality

**Files to create:**
1. `frontend/src/components/ConversationList.astro` (NEW)
2. `frontend/src/stores/conversations.ts` (NEW)

**Files to modify:**
3. `frontend/src/pages/chat.astro` - Add sidebar layout
4. `frontend/src/lib/api.ts` - Add list/delete endpoints

**Implementation:**

**Step 3.1:** Add API functions (`src/lib/api.ts`)
```typescript
export async function getConversations(token: string) {
  const response = await fetch(`${API_BASE}/conversations`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) throw new Error('Failed to load conversations');
  return response.json();
}

export async function deleteConversation(token: string, id: string) {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!response.ok) throw new Error('Failed to delete conversation');
}
```

**Step 3.2:** Create conversation store (`src/stores/conversations.ts`)
```typescript
import { atom } from 'nanostores';

export const $conversations = atom([]);
export const $activeConversationId = atom(null);

export async function loadConversations(token) {
  const convs = await getConversations(token);
  $conversations.set(convs);
}
```

**Step 3.3:** Create sidebar component (`src/components/ConversationList.astro`)
- Display list of conversations (title only)
- Highlight active conversation
- "New Conversation" button (redirects to `/chat`)
- Delete button per conversation (with confirm dialog)
- Click conversation → navigate to `/chat?id={id}`

**Step 3.4:** Update chat layout (`src/pages/chat.astro`)
```html
<div class="flex h-screen">
  <!-- Sidebar: 300px width, collapsible on mobile -->
  <aside class="w-80 bg-gray-100 border-r">
    <ConversationList activeId={conversationId} />
  </aside>

  <!-- Main chat area -->
  <main class="flex-1 flex flex-col">
    <!-- Messages -->
    <!-- Input -->
  </main>
</div>
```

**Acceptance Criteria:**
- ✅ Sidebar displays all user conversations (title only)
- ✅ Active conversation highlighted
- ✅ "New Conversation" creates and redirects
- ✅ Click conversation switches to it
- ✅ Delete conversation shows confirm dialog
- ✅ Deleting active conversation redirects to new conversation

---

### **Task 4: Add Loading & Error States** (1 hour) - PR #3

**Goal:** Professional UX with loading indicators and error messages

**Files to create:**
1. `frontend/src/components/LoadingSpinner.astro` (NEW)
2. `frontend/src/components/EmptyState.astro` (NEW)

**Files to modify:**
3. `frontend/src/pages/chat.astro` - Loading states
4. `frontend/src/components/ConversationList.astro` - Loading/empty states

**Implementation:**

**Step 4.1:** Create LoadingSpinner component
- Spinning SVG icon
- Optional text prop
- TailwindCSS animations

**Step 4.2:** Create EmptyState component
- Icon + message
- Props: `icon`, `title`, `description`

**Step 4.3:** Add loading states to chat page
- Show spinner while fetching conversation
- Show "AI is typing..." during WebSocket response
- Show error message if conversation load fails

**Step 4.4:** Add states to conversation list
- Skeleton loader while fetching conversations
- Empty state: "No conversations yet - start chatting!"
- Error state: "Failed to load conversations. [Retry]"

**Acceptance Criteria:**
- ✅ Loading spinner shows during API calls
- ✅ Typing indicator shows during AI response
- ✅ Empty states are helpful and friendly
- ✅ Error messages are actionable
- ✅ No blank white screens

---

### **Task 5: Responsive Design & Polish** (30 min) - PR #3

**Goal:** Works on mobile, tablet, desktop

**Files to modify:**
1. `frontend/src/pages/chat.astro` - Responsive layout
2. `frontend/src/components/ConversationList.astro` - Collapsible sidebar

**Implementation:**

**Step 5.1:** Add responsive breakpoints
```html
<!-- Sidebar: hidden on mobile, visible on desktop -->
<aside class="hidden md:block md:w-80">
  <!-- Conversation list -->
</aside>

<!-- Mobile: hamburger menu button -->
<button class="md:hidden" @click="toggleSidebar()">
  ☰
</button>
```

**Step 5.2:** Test on breakpoints
- 375px (mobile) - sidebar collapses, messages stack
- 768px (tablet) - sidebar visible
- 1920px (desktop) - full layout

**Acceptance Criteria:**
- ✅ Mobile (375px): Sidebar hidden, hamburger menu works
- ✅ Tablet (768px): Sidebar visible
- ✅ Desktop (1920px): Full layout
- ✅ No horizontal scrolling
- ✅ Input area always accessible

---

## 📦 PR #1 Summary (Current)

**Branch:** `feature/frontend-markdown-history`
**Time:** 1.5 hours
**Files Changed:** 5 (2 new, 3 modified)

**Changes:**
- ✅ Create `frontend/src/lib/markdown.ts`
- ✅ Modify `frontend/src/components/ChatMessage.astro`
- ✅ Modify `frontend/src/lib/api.ts`
- ✅ Modify `frontend/src/pages/chat.astro`
- ✅ Modify `frontend/src/stores/chat.ts`

**Testing Checklist:**
- [ ] Markdown renders: **bold**, lists, `code`, links
- [ ] No XSS (DOMPurify sanitizes)
- [ ] `/chat` → creates new conversation
- [ ] `/chat?id=XXX` → loads messages
- [ ] Page reload → same messages (no duplication)
- [ ] No console errors

---

## ✅ Final Acceptance Criteria (All PRs)

Before marking complete, verify:
- [ ] Markdown renders correctly (bold, lists, code, links)
- [ ] Message history loads on page refresh
- [ ] No duplicate conversations created on reload
- [ ] Conversation list displays and updates
- [ ] New/switch/delete conversation works
- [ ] Loading states show during API calls
- [ ] Empty states are helpful
- [ ] Error messages are clear
- [ ] Mobile layout works (375px)
- [ ] Desktop layout works (1920px)
- [ ] No console errors
- [ ] Manual E2E test passes:
  1. Register → Login
  2. Create conversation → Send message
  3. Reload page → Messages persist
  4. Create 2nd conversation → Switch between them
  5. Delete conversation → Redirects correctly

---

**Status:** PR #1 in progress
**Next:** Complete Tasks 1 & 2, test, create PR
