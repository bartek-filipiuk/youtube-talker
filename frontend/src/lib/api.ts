/**
 * API Client for Qivio Backend
 * Handles all HTTP requests to the backend API
 */

// Base API URL - change this for production
export const API_BASE = import.meta.env.PUBLIC_API_BASE || 'http://localhost:8000/api';

// Response types
export interface AuthResponse {
  token: string;
  user: {
    id: string;
    email: string;
  };
}

export interface User {
  id: string;
  email: string;
}

export interface ApiError {
  detail: string;
}

// Allowed AI model types
export type AllowedModel = 'claude-haiku-4.5' | 'gemini-2.5-flash' | 'kimi-k2-thinking' | 'grok-4-fast';

/**
 * Register a new user
 */
export async function register(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Registration failed');
  }

  const data = await response.json();

  // Transform backend response to match AuthResponse interface
  return {
    token: data.token,
    user: {
      id: data.user_id,
      email: data.email,
    },
  };
}

/**
 * Login existing user
 */
export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  const data = await response.json();

  // Transform backend response to match AuthResponse interface
  return {
    token: data.token,
    user: {
      id: data.user_id,
      email: data.email,
    },
  };
}

/**
 * Logout current user
 */
export async function logout(token: string): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    // Log error but don't throw - logout should always succeed client-side
    console.error('Logout request failed');
  }
}

/**
 * Get current user details
 */
export async function getCurrentUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE}/auth/me`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to get user');
  }

  return response.json();
}

// ============================================================================
// Conversation Management
// ============================================================================

export interface ApiMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: ApiMessage[];
}

/**
 * Get a specific conversation with its messages
 */
export async function getConversation(token: string, id: string): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to load conversation');
  }

  return response.json();
}

/**
 * Get the latest conversation for the current user
 */
export async function getLatestConversation(token: string): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations/latest`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to load latest conversation');
  }

  return response.json();
}

/**
 * Create a new conversation
 */
export async function createConversation(token: string, title?: string, model?: AllowedModel): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: title || 'New conversation',
      model: model
    }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to create conversation');
  }

  return response.json();
}

/**
 * Get all conversations for the current user (legacy - non-paginated)
 */
export async function getConversations(token: string): Promise<Conversation[]> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to load conversations');
  }

  // Backend returns paginated response: { conversations: [...], total, limit, offset }
  const data = await response.json();
  return data.conversations || [];
}

/**
 * Get conversations with pagination support
 */
export async function getConversationsPaginated(
  token: string,
  limit: number = 10,
  offset: number = 0
): Promise<{ conversations: Conversation[]; total: number }> {
  const url = `${API_BASE}/conversations?limit=${limit}&offset=${offset}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to load conversations');
  }

  // Backend returns paginated response: { conversations: [...], total, limit, offset }
  const data = await response.json();
  return {
    conversations: data.conversations || [],
    total: data.total || 0
  };
}

/**
 * Update conversation title
 */
export async function updateConversationTitle(
  token: string,
  id: string,
  title: string
): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to update conversation');
  }

  return response.json();
}

/**
 * Delete a conversation
 */
export async function deleteConversation(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to delete conversation');
  }
}

// ============================================================================
// Transcript/Video Management
// ============================================================================

export interface Video {
  id: string;
  title: string;
  created_at: string;
}

export interface VideoListResponse {
  videos: Video[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Get paginated list of user's videos
 */
export async function getVideos(
  token: string,
  limit: number = 10,
  offset: number = 0
): Promise<VideoListResponse> {
  const url = `${API_BASE}/transcripts?limit=${limit}&offset=${offset}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to fetch videos');
  }

  return response.json();
}

/**
 * Delete a transcript/video
 */
export async function deleteTranscript(token: string, transcriptId: string): Promise<void> {
  const url = `${API_BASE}/transcripts/${transcriptId}`;
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to delete transcript');
  }
}

// ============================================================================
// Billing & Subscription Management
// ============================================================================

export interface SubscriptionPlan {
  id: string;
  name: string;
  display_name: string;
  monthly_price_cents: number;
  annual_price_cents: number | null;
  video_limit: number | null;
  message_limit: number | null;
  features: Record<string, boolean>;
}

export interface SubscriptionStatus {
  plan_name: string;
  plan_display_name: string;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'incomplete' | 'none';
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  video_limit: number | null;
  message_limit: number | null;
}

export interface UsageStats {
  videos_used: number;
  videos_limit: number | null;
  messages_used: number;
  messages_limit: number | null;
  period_start: string;
  period_end: string;
}

export interface CheckoutSession {
  checkout_url: string;
  session_id: string;
}

export interface PortalSession {
  portal_url: string;
}

/**
 * Get available subscription plans (public endpoint)
 */
export async function getPlans(): Promise<SubscriptionPlan[]> {
  const response = await fetch(`${API_BASE}/billing/plans`, {
    method: 'GET',
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to fetch plans');
  }

  const data = await response.json();
  return data.plans;
}

/**
 * Get current user's subscription status
 */
export async function getSubscriptionStatus(token: string): Promise<SubscriptionStatus> {
  const response = await fetch(`${API_BASE}/billing/status`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to fetch subscription status');
  }

  // Backend returns nested structure, transform to flat interface
  const data = await response.json();
  const sub = data.subscription;

  return {
    plan_name: sub?.plan?.name || 'free',
    plan_display_name: sub?.plan?.display_name || 'Free',
    status: sub?.status || 'none',
    current_period_start: sub?.current_period_start || null,
    current_period_end: sub?.current_period_end || null,
    trial_end: sub?.trial_end || null,
    cancel_at_period_end: sub?.cancel_at_period_end || false,
    video_limit: sub?.plan?.video_limit || null,
    message_limit: sub?.plan?.message_limit || null,
  };
}

/**
 * Get current user's usage stats
 */
export async function getUsageStats(token: string): Promise<UsageStats> {
  const response = await fetch(`${API_BASE}/billing/usage`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to fetch usage stats');
  }

  // Backend returns UsageResponse directly
  const data = await response.json();
  return {
    videos_used: data.videos_used || 0,
    videos_limit: data.videos_limit,
    messages_used: data.messages_used || 0,
    messages_limit: data.messages_limit,
    period_start: data.period_start,
    period_end: data.period_end,
  };
}

/**
 * Create a Stripe checkout session for subscription
 */
export async function createCheckoutSession(
  token: string,
  planId: string,
  billingCycle: 'monthly' | 'annual'
): Promise<CheckoutSession> {
  const response = await fetch(`${API_BASE}/billing/checkout`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      plan_id: planId,
      billing_cycle: billingCycle,
    }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to create checkout session');
  }

  return response.json();
}

/**
 * Create a Stripe customer portal session
 */
export async function createPortalSession(token: string): Promise<PortalSession> {
  const response = await fetch(`${API_BASE}/billing/portal`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to create portal session');
  }

  return response.json();
}
