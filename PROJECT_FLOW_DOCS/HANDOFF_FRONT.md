# Frontend Development Handoff
## YoutubeTalker MVP

**Version:** 1.0
**Last Updated:** 2025-10-17
**Target:** Frontend (Astro)

---

## How to Use This Document

This is the **frontend development checklist** for YoutubeTalker. Follow these rules:

1. **Start AFTER backend Phase 7 is complete** (WebSocket chat API working)
2. **Work on ONE checkbox at a time**
3. **Each checkbox = one reviewable unit of work**
4. **Test in browser** after each task
5. **Request review** before moving to next checkbox

**Progress Tracking:**
- [ ] = Not started
- [x] = Completed and reviewed

---

## Prerequisites

Before starting frontend development:
- [ ] Backend API is running on `http://localhost:8000`
- [ ] Backend `/api/health` endpoint returns 200 OK
- [ ] Backend authentication endpoints work (`/api/auth/login`, `/api/auth/register`)
- [ ] Backend WebSocket endpoint is available (`/api/chat/{conversation_id}`)
- [ ] At least one test user exists in the database
- [ ] At least one conversation exists for testing

---

## Phase 1: Astro Project Setup

**Goal:** Initialize Astro project with basic configuration

### 1.1 Initialize Astro Project

- [ ] Create `frontend/` directory in project root
- [ ] Run `npm create astro@latest` in frontend directory
- [ ] Choose options:
  - Template: "Empty" or "Minimal"
  - TypeScript: Yes
  - Strict mode: Yes
  - Install dependencies: Yes
- [ ] Test: Run `npm run dev` and verify Astro starts
- [ ] Access `http://localhost:4321` in browser

**Acceptance Criteria:**
- Astro development server runs without errors
- Default page loads in browser

---

### 1.2 Install Dependencies

- [ ] Install TailwindCSS: `npx astro add tailwind`
- [ ] Install Nanostores: `npm install nanostores @nanostores/react`
- [ ] Install additional packages:
  ```bash
  npm install marked  # Markdown rendering
  npm install dompurify  # XSS protection
  npm install @types/dompurify
  ```
- [ ] Verify: Check `package.json` for all dependencies

**Acceptance Criteria:**
- All packages install successfully
- TailwindCSS is configured

---

### 1.3 Configure TypeScript

- [ ] Review `tsconfig.json`
- [ ] Add path aliases if needed:
  ```json
  {
    "compilerOptions": {
      "paths": {
        "@components/*": ["src/components/*"],
        "@lib/*": ["src/lib/*"],
        "@stores/*": ["src/stores/*"]
      }
    }
  }
  ```
- [ ] Update `astro.config.mjs` to include aliases

**Acceptance Criteria:**
- TypeScript imports work with aliases

---

### 1.4 Create Base Layout

- [ ] Create `src/layouts/Layout.astro`
- [ ] Add basic HTML structure:
  - `<html>`, `<head>`, `<body>`
  - Viewport meta tag
  - Title from props
  - TailwindCSS imports
- [ ] Add global styles in `src/styles/global.css`
- [ ] Test: Use layout in `src/pages/index.astro`

**Acceptance Criteria:**
- Layout renders correctly
- TailwindCSS styles apply

**Example Layout:**
```astro
---
interface Props {
  title: string;
}
const { title } = Astro.props;
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body class="bg-gray-50">
  <slot />
</body>
</html>
```

---

## Phase 2: Authentication UI

**Goal:** Build login and registration pages

**Dependencies:** Backend Phase 3 completed (auth endpoints working)

### 2.1 API Client Utility

- [ ] Create `src/lib/api.ts`
- [ ] Define `API_BASE` constant (e.g., `http://localhost:8000/api`)
- [ ] Implement functions:
  - `async register(email: string, password: string)`
  - `async login(email: string, password: string)`
  - `async logout(token: string)`
  - `async getCurrentUser(token: string)`
- [ ] Handle errors (network, 401, 400, etc.)
- [ ] Return typed responses

**Acceptance Criteria:**
- API functions work with backend
- Errors are caught and returned

**Example:**
```typescript
export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  return response.json();
}
```

---

### 2.2 Auth Store (State Management)

- [ ] Create `src/stores/auth.ts`
- [ ] Use Nanostores to create:
  - `$token` - stores session token
  - `$user` - stores user data
  - `$isAuthenticated` - computed from token
- [ ] Implement:
  - `setAuth(token, user)` - save to store and localStorage
  - `clearAuth()` - clear store and localStorage
  - `loadAuthFromStorage()` - restore from localStorage on page load

**Acceptance Criteria:**
- Auth state persists across page refreshes
- Token is stored in localStorage

**Example:**
```typescript
import { atom, computed } from 'nanostores';

export const $token = atom<string | null>(null);
export const $user = atom<{ id: string; email: string } | null>(null);
export const $isAuthenticated = computed($token, (token) => !!token);

export function setAuth(token: string, user: any) {
  $token.set(token);
  $user.set(user);
  localStorage.setItem('token', token);
}

export function clearAuth() {
  $token.set(null);
  $user.set(null);
  localStorage.removeItem('token');
}
```

---

### 2.3 Login Page

- [ ] Create `src/pages/index.astro` (or `login.astro`)
- [ ] Create `src/components/LoginForm.astro`
- [ ] Add form fields:
  - Email (type="email", required)
  - Password (type="password", required, minlength=8)
  - Submit button
- [ ] Add client-side script to handle form submission:
  - Call `login()` from api.ts
  - On success: Save token, redirect to `/chat`
  - On error: Display error message
- [ ] Style with TailwindCSS

**Acceptance Criteria:**
- Login form submits correctly
- Successful login redirects to chat page
- Errors are displayed to user

---

### 2.4 Registration Page

- [ ] Create `src/pages/register.astro`
- [ ] Create `src/components/RegisterForm.astro`
- [ ] Add form fields:
  - Email
  - Password
  - Confirm Password (client-side validation)
  - Submit button
- [ ] Handle form submission:
  - Validate passwords match
  - Call `register()` from api.ts
  - On success: Auto-login and redirect
  - On error: Display error
- [ ] Add link to login page

**Acceptance Criteria:**
- Registration creates new user
- Auto-login after registration works
- Password confirmation validates

---

### 2.5 Protected Route Middleware

- [ ] Create `src/lib/auth.ts` utility
- [ ] Implement `requireAuth()` function:
  - Check if token exists in localStorage
  - Validate token with backend (`/api/auth/me`)
  - If invalid, redirect to login
- [ ] Use in protected pages (chat, conversations)

**Acceptance Criteria:**
- Unauthenticated users redirected to login
- Authenticated users can access protected pages

**Example:**
```typescript
export async function requireAuth() {
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/';
    return null;
  }

  try {
    const user = await getCurrentUser(token);
    return { token, user };
  } catch (error) {
    localStorage.removeItem('token');
    window.location.href = '/';
    return null;
  }
}
```

---

### 2.6 Logout Functionality

- [ ] Create `src/pages/logout.astro`
- [ ] On page load:
  - Call `logout()` API
  - Clear auth store
  - Redirect to login
- [ ] Add logout button to header/nav (to be created)

**Acceptance Criteria:**
- Logout clears session
- User redirected to login

---

## Phase 3: Conversation Management UI

**Goal:** Build conversation list and management

**Dependencies:** Backend Phase 9.2 completed (conversation endpoints)

### 3.1 Conversations API Client

- [ ] Add to `src/lib/api.ts`:
  - `async getConversations(token: string)`
  - `async getConversation(token: string, id: string)`
  - `async createConversation(token: string, title?: string)`
  - `async deleteConversation(token: string, id: string)`

**Acceptance Criteria:**
- API functions call backend successfully
- Typed responses

---

### 3.2 Conversations Store

- [ ] Create `src/stores/conversations.ts`
- [ ] Use Nanostores:
  - `$conversations` - array of conversations
  - `$activeConversationId` - current conversation ID
- [ ] Implement:
  - `loadConversations(token)` - fetch from API
  - `createConversation(token)` - create new
  - `deleteConversation(token, id)` - delete

**Acceptance Criteria:**
- Store manages conversation state
- Actions update store reactively

---

### 3.3 Conversation List Component

- [ ] Create `src/components/ConversationList.astro`
- [ ] Display list of conversations:
  - Title
  - Last message preview (truncated)
  - Timestamp
- [ ] Add "New Conversation" button
- [ ] Add delete button per conversation (confirm dialog)
- [ ] Highlight active conversation
- [ ] Click conversation ’ navigate to `/chat?id={conversation_id}`

**Acceptance Criteria:**
- Conversations display correctly
- Click navigates to chat
- New conversation works
- Delete works with confirmation

---

### 3.4 Conversations Page (Optional for MVP)

- [ ] Create `src/pages/conversations.astro`
- [ ] List all conversations
- [ ] Include ConversationList component
- [ ] Add navigation to header

**Acceptance Criteria:**
- Page shows all user conversations
- Navigation works

**Note:** This can be sidebar in chat page instead of separate page

---

## Phase 4: Chat Interface

**Goal:** Build main chat UI with message display

**Dependencies:** Backend Phase 7 completed (WebSocket working)

### 4.1 Chat Layout

- [ ] Create `src/layouts/ChatLayout.astro`
- [ ] Layout structure:
  - Sidebar (left): Conversation list
  - Main area (right): Chat messages + input
  - Header: User info, logout button
- [ ] Make responsive (sidebar collapses on mobile)
- [ ] Style with TailwindCSS

**Acceptance Criteria:**
- Layout displays correctly on desktop and mobile
- Sidebar is collapsible

---

### 4.2 Chat Page Structure

- [ ] Create `src/pages/chat.astro`
- [ ] Use ChatLayout
- [ ] Get `conversation_id` from URL query param
- [ ] Verify user owns conversation (backend call)
- [ ] If no conversation_id, create new conversation
- [ ] Load conversation messages on page load

**Acceptance Criteria:**
- Chat page loads with conversation ID
- Messages load from backend
- Auto-creates conversation if needed

---

### 4.3 Message Display Component

- [ ] Create `src/components/ChatMessage.astro`
- [ ] Accept props: `role` ('user' | 'assistant'), `content`, `timestamp`
- [ ] Style differently for user vs assistant:
  - User: right-aligned, blue background
  - Assistant: left-aligned, gray background
- [ ] Render content as HTML (sanitize with DOMPurify)
- [ ] Display timestamp
- [ ] Add copy button for assistant messages

**Acceptance Criteria:**
- Messages render with correct styling
- HTML content is sanitized
- Copy button works

**Example:**
```astro
---
interface Props {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}
const { role, content, timestamp } = Astro.props;
const isUser = role === 'user';
---

<div class={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
  <div class={`max-w-2xl p-4 rounded-lg ${isUser ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}>
    <div class="prose" set:html={content}></div>
    <div class="text-xs opacity-75 mt-2">{new Date(timestamp).toLocaleString()}</div>
  </div>
</div>
```

---

### 4.4 Messages Container

- [ ] Create container div in `chat.astro` for messages
- [ ] Render list of ChatMessage components
- [ ] Auto-scroll to bottom on new message
- [ ] Add loading indicator while fetching

**Acceptance Criteria:**
- Messages display in order (oldest to newest)
- Auto-scroll works
- Loading state shown

---

### 4.5 Copy to Clipboard Button

- [ ] Create `src/components/CopyButton.astro`
- [ ] Accept prop: `text` (content to copy)
- [ ] On click:
  - Copy text to clipboard (use `navigator.clipboard.writeText()`)
  - Show "Copied!" feedback (tooltip or toast)
- [ ] Style as icon button

**Acceptance Criteria:**
- Copy button copies text to clipboard
- User feedback is clear

---

## Phase 5: WebSocket Integration

**Goal:** Real-time chat with WebSocket

**Dependencies:** Backend Phase 7 completed, Frontend Phase 4 completed

### 5.1 WebSocket Client Class

- [ ] Create `src/lib/websocket.ts`
- [ ] Implement `WebSocketClient` class:
  - Constructor: `(url: string, token: string)`
  - Methods:
    - `connect()` - establish WebSocket connection
    - `sendMessage(content: string)` - send message
    - `onMessage(callback: (data: any) => void)` - receive messages
    - `onError(callback)` - handle errors
    - `disconnect()` - close connection
  - Auto-reconnect on disconnect (with exponential backoff)
  - Heartbeat/ping-pong

**Acceptance Criteria:**
- WebSocket connects to backend
- Messages send and receive
- Auto-reconnect works

**Example:**
```typescript
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string;

  constructor(url: string, token: string) {
    this.url = url;
    this.token = token;
  }

  connect() {
    this.ws = new WebSocket(`${this.url}?token=${this.token}`);
    this.ws.onopen = () => console.log('WebSocket connected');
    this.ws.onclose = () => this.reconnect();
  }

  sendMessage(content: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ message: content }));
    }
  }

  onMessage(callback: (data: any) => void) {
    if (this.ws) {
      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        callback(data);
      };
    }
  }

  private reconnect() {
    setTimeout(() => this.connect(), 1000);
  }
}
```

---

### 5.2 Chat Messages Store

- [ ] Create `src/stores/chat.ts`
- [ ] Use Nanostores:
  - `$messages` - array of messages
  - `$isTyping` - boolean for "AI is typing" indicator
- [ ] Implement:
  - `addMessage(role, content)` - append message
  - `setTyping(isTyping)` - update typing state

**Acceptance Criteria:**
- Store manages message state reactively
- UI updates when store changes

---

### 5.3 Message Input Component

- [ ] Create `src/components/ChatInput.astro`
- [ ] Add textarea for message input
- [ ] Add send button
- [ ] Validate: max 2000 characters
- [ ] Disable input while message is sending
- [ ] On submit:
  - Add user message to store
  - Send via WebSocket
  - Clear input
- [ ] Support Enter key to send (Shift+Enter for new line)

**Acceptance Criteria:**
- Input works correctly
- Message length validation
- Enter key sends message

---

### 5.4 WebSocket Message Handling

- [ ] In `chat.astro`, initialize WebSocket on page load
- [ ] Set up message handler:
  - On `{"type": "chunk"}`: Append to current assistant message (streaming)
  - On `{"type": "done"}`: Finalize message, stop typing indicator
  - On error: Display error to user
- [ ] Add "AI is typing..." indicator during streaming
- [ ] Save messages to backend (via `$messages` store, persist on done)

**Acceptance Criteria:**
- Messages stream in real-time
- Typing indicator shows during AI response
- Messages persist after refresh

---

### 5.5 Streaming Message Display

- [ ] Create logic to handle streaming chunks
- [ ] Display partial message as it arrives
- [ ] Update message content progressively
- [ ] Show "..." or spinner while streaming

**Acceptance Criteria:**
- Streaming works smoothly
- No flickering or jumping

---

### 5.6 WebSocket Error Handling

- [ ] Handle WebSocket disconnections
- [ ] Display reconnection status to user
- [ ] Retry failed messages
- [ ] Show error for rate limit exceeded

**Acceptance Criteria:**
- Errors are user-friendly
- Reconnection is automatic

---

## Phase 6: Message Rendering & Polish

**Goal:** Enhanced message display and UX

### 6.1 Markdown Rendering

- [ ] Install marked: `npm install marked`
- [ ] Convert assistant messages from markdown to HTML
- [ ] Sanitize HTML with DOMPurify
- [ ] Style markdown elements (headings, lists, code blocks)
- [ ] Test with various markdown inputs

**Acceptance Criteria:**
- Markdown renders correctly
- Code blocks have syntax highlighting (optional)
- HTML is sanitized

**Example:**
```typescript
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const html = marked(content);
const clean = DOMPurify.sanitize(html);
```

---

### 6.2 Message Timestamps

- [ ] Display relative timestamps ("2 minutes ago", "1 hour ago")
- [ ] Use library like `date-fns` or implement custom logic
- [ ] Show full timestamp on hover

**Acceptance Criteria:**
- Timestamps are human-readable
- Hover shows full date/time

---

### 6.3 Loading States

- [ ] Add skeleton loaders for:
  - Conversation list while loading
  - Messages while loading
- [ ] Show spinner during API calls
- [ ] Disable buttons during loading

**Acceptance Criteria:**
- Loading states are clear
- No blank screens during load

---

### 6.4 Empty States

- [ ] Show message when no conversations exist
  - "Create your first conversation"
- [ ] Show message when conversation is empty
  - "Start chatting..."
- [ ] Add helpful prompts

**Acceptance Criteria:**
- Empty states are informative

---

### 6.5 Error Messages

- [ ] Display errors in UI (not just console)
- [ ] Use toast notifications or inline errors
- [ ] Distinguish error types (network, auth, validation)

**Acceptance Criteria:**
- Errors are visible to user
- Error messages are actionable

---

## Phase 7: Final Polish & Testing

**Goal:** Responsive design, testing, and optimization

### 7.1 Responsive Design

- [ ] Test on mobile (375px width)
- [ ] Test on tablet (768px)
- [ ] Test on desktop (1920px)
- [ ] Adjust layout for each breakpoint
- [ ] Ensure sidebar collapses on mobile

**Acceptance Criteria:**
- App works on all screen sizes
- No horizontal scrolling

---

### 7.2 Accessibility

- [ ] Add ARIA labels to buttons and forms
- [ ] Ensure keyboard navigation works
  - Tab through elements
  - Enter to submit
  - Escape to close modals
- [ ] Test with screen reader (basic check)
- [ ] Add focus indicators

**Acceptance Criteria:**
- Keyboard navigation works
- ARIA labels present

---

### 7.3 Performance Optimization

- [ ] Lazy load conversation list
- [ ] Virtualize long message lists (if > 100 messages)
- [ ] Optimize images (if any)
- [ ] Minimize bundle size (check with build analysis)

**Acceptance Criteria:**
- Page load time < 2 seconds
- Smooth scrolling with 100+ messages

---

### 7.4 Browser Testing

- [ ] Test in Chrome
- [ ] Test in Firefox
- [ ] Test in Safari (if on Mac)
- [ ] Test in Edge
- [ ] Fix browser-specific issues

**Acceptance Criteria:**
- App works in all major browsers

---

### 7.5 End-to-End Manual Testing

- [ ] Test full user journey:
  1. Register new account
  2. Login
  3. Create conversation
  4. Send multiple messages
  5. View response streaming
  6. Copy message to clipboard
  7. Request LinkedIn post generation
  8. Delete conversation
  9. Logout
- [ ] Verify all features work

**Acceptance Criteria:**
- Full journey completes without errors

---

### 7.6 Visual Polish

- [ ] Consistent spacing and margins
- [ ] Consistent color scheme
- [ ] Smooth transitions and animations
- [ ] Hover states on interactive elements
- [ ] Loading spinners styled

**Acceptance Criteria:**
- UI looks polished and professional

---

### 7.7 Documentation

- [ ] Update `frontend/README.md`
- [ ] Document setup steps
- [ ] Document environment variables (if any)
- [ ] Add screenshots (optional)

**Acceptance Criteria:**
- README is complete
- New developer can set up frontend

---

## Completion Checklist

Before marking frontend as "complete", verify:

- [ ] All Phase 1-7 checkboxes are complete
- [ ] App works on desktop and mobile
- [ ] No console errors in browser
- [ ] All features functional
- [ ] Responsive design implemented
- [ ] Documentation updated

**MVP Frontend Status:**  Complete (once all above checked)

---

## Optional Enhancements (Post-MVP)

These are nice-to-have features for future iterations:

- [ ] Dark mode toggle
- [ ] Conversation search
- [ ] Message editing/deletion
- [ ] Typing indicators for multi-user (future)
- [ ] File upload support (PDFs, etc.)
- [ ] Conversation export (markdown, PDF)
- [ ] User profile page
- [ ] Custom template editor UI
- [ ] Notification system (toast library)
- [ ] PWA support (service worker)

---

## Notes & Decisions

**Track frontend-specific decisions here:**

- Decision 1: [Date] - Used Nanostores over Redux (lighter weight for MVP)
- Decision 2: [Date] - Chose Marked for markdown (well-maintained, simple API)
- ...

---

**Document Version:**
- v1.0 (2025-10-17): Initial frontend handoff
