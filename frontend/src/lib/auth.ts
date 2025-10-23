/**
 * Protected Route Logic
 * Ensures users are authenticated before accessing protected pages
 */

import { getCurrentUser } from './api';
import type { User } from './api';

export interface AuthResult {
  token: string;
  user: User;
}

/**
 * Require authentication - redirect to login if not authenticated
 * Use this in protected pages (e.g., chat, conversations)
 *
 * @returns Auth data if authenticated, null if redirected
 */
export async function requireAuth(): Promise<AuthResult | null> {
  // Check if we're in the browser
  if (typeof window === 'undefined') {
    return null;
  }

  // Get token from localStorage
  const token = localStorage.getItem('token');
  const userStr = localStorage.getItem('user');

  if (!token || !userStr) {
    // Not authenticated - redirect to login
    window.location.href = '/';
    return null;
  }

  try {
    // Validate token with backend
    const user = await getCurrentUser(token);

    return { token, user };
  } catch (error) {
    // Token is invalid - clear storage and redirect
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
    return null;
  }
}

/**
 * Check if user is authenticated (without redirect)
 *
 * @returns true if authenticated, false otherwise
 */
export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  const token = localStorage.getItem('token');
  return !!token;
}

/**
 * Get auth token from storage
 *
 * @returns Token string or null
 */
export function getToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return localStorage.getItem('token');
}
