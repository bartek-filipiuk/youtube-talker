/**
 * Authentication State Management with Nanostores
 * Manages user authentication state across the application
 */

import { atom, computed } from 'nanostores';
import type { User } from '../lib/api';

// Auth state atoms
export const $token = atom<string | null>(null);
export const $user = atom<User | null>(null);

// Computed state - is user authenticated?
export const $isAuthenticated = computed($token, (token) => !!token);

/**
 * Set authentication (after login/register)
 */
export function setAuth(token: string, user: User): void {
  $token.set(token);
  $user.set(user);

  // Persist to localStorage
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }
}

/**
 * Clear authentication (after logout)
 */
export function clearAuth(): void {
  $token.set(null);
  $user.set(null);

  // Remove from localStorage
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
}

/**
 * Load auth from localStorage (on page load)
 */
export function loadAuthFromStorage(): void {
  if (typeof window === 'undefined') return;

  const token = localStorage.getItem('token');
  const userStr = localStorage.getItem('user');

  if (token && userStr) {
    try {
      const user = JSON.parse(userStr);
      $token.set(token);
      $user.set(user);
    } catch (error) {
      console.error('Failed to parse user from localStorage:', error);
      clearAuth();
    }
  }
}

// Auto-load auth on import (client-side only)
if (typeof window !== 'undefined') {
  loadAuthFromStorage();
}
