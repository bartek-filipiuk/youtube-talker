/**
 * API Client for YoutubeTalker Backend
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
 * Create a new conversation
 */
export async function createConversation(token: string, title?: string): Promise<Conversation> {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title: title || 'New conversation' }),
  });

  if (!response.ok) {
    const error: ApiError = await response.json();
    throw new Error(error.detail || 'Failed to create conversation');
  }

  return response.json();
}

/**
 * Get all conversations for the current user
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
