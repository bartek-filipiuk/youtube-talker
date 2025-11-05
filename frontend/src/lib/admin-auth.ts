/**
 * Admin Authentication Utilities for SSR
 *
 * Provides server-side admin authentication checks for Astro pages.
 * Use requireAdmin() in Astro frontmatter to protect admin routes.
 */

import type { AstroGlobal } from 'astro';
import { API_BASE } from './api';

export interface AdminUser {
  id: string;
  email: string;
  role: string;
}

export interface AdminAuthResult {
  token: string;
  user: AdminUser;
}

/**
 * Require admin authentication in SSR context.
 *
 * Checks for valid token in cookies/localStorage and verifies admin status.
 * Redirects to home page if not authenticated or not admin.
 *
 * Usage in Astro frontmatter:
 * ```astro
 * ---
 * import { requireAdmin } from '@/lib/admin-auth';
 * const auth = await requireAdmin(Astro);
 * if (auth instanceof Response) return auth;
 * // auth.user.email, auth.token available here
 * ---
 * ```
 *
 * @param Astro - Astro global object
 * @returns AdminAuthResult if authenticated admin, or Response (redirect) if not
 */
export async function requireAdmin(Astro: AstroGlobal): Promise<AdminAuthResult | Response> {
  // Step 1: Get token from cookies first, fallback to query param (for client-side transitions)
  let token = Astro.cookies.get('token')?.value;

  // Fallback: Check URL query params (e.g., /admin?token=xxx from client-side navigation)
  if (!token) {
    token = Astro.url.searchParams.get('token') || undefined;
  }

  // No token found - redirect to login
  if (!token) {
    return Astro.redirect('/?error=auth_required');
  }

  // Step 2: Validate token with backend
  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    // Token invalid or expired
    if (!response.ok) {
      if (response.status === 401) {
        return Astro.redirect('/?error=session_expired');
      }
      throw new Error(`Auth check failed: ${response.status}`);
    }

    const user: AdminUser = await response.json();

    // Step 3: Verify admin status
    if (user.role !== 'admin') {
      return Astro.redirect('/?error=admin_required');
    }

    // Step 4: Return auth result for use in page
    return {
      token,
      user,
    };

  } catch (error) {
    console.error('Admin auth check failed:', error);
    return Astro.redirect('/?error=auth_error');
  }
}

/**
 * Optional: Set token in cookie for SSR auth
 * Call this from a client-side script when user logs in
 *
 * Usage:
 * ```typescript
 * // After successful login
 * document.cookie = `token=${token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=Strict`;
 * ```
 */
export function setAuthCookie(token: string, maxAgeDays: number = 7): void {
  const maxAgeSeconds = maxAgeDays * 24 * 60 * 60;
  document.cookie = `token=${token}; path=/; max-age=${maxAgeSeconds}; SameSite=Strict`;
}

/**
 * Optional: Clear auth cookie on logout
 */
export function clearAuthCookie(): void {
  document.cookie = 'token=; path=/; max-age=0; SameSite=Strict; Secure';
}

/**
 * Get authentication token from localStorage or cookies (client-side only).
 *
 * Checks localStorage first, then falls back to cookies. If token is found in cookie,
 * it will be stored in localStorage for future use.
 *
 * Usage:
 * ```typescript
 * const token = getClientToken();
 * if (!token) {
 *   window.location.href = '/?error=auth_required';
 *   return;
 * }
 * ```
 *
 * @returns Token string if found, null otherwise
 */
export function getClientToken(): string | null {
  // Try localStorage first
  let token = localStorage.getItem('token');

  if (!token) {
    // Fallback to cookie (SSR auth)
    const cookieMatch = document.cookie.match(/(?:^|;\s*)token=([^;]+)/);
    if (cookieMatch) {
      token = cookieMatch[1];
      // Store in localStorage for future use
      localStorage.setItem('token', token);
    }
  }

  return token;
}

/**
 * Show a toast notification (client-side only).
 *
 * Creates a temporary notification that appears in the top-right corner
 * and automatically disappears after a few seconds.
 *
 * @param message - The message to display
 * @param type - Notification type: 'success', 'error', or 'info'
 * @param duration - How long to show the toast in milliseconds (default: 3000)
 *
 * Usage:
 * ```typescript
 * import { showToast } from '@/lib/admin-auth';
 * showToast('Channel created successfully!', 'success');
 * showToast('Failed to delete user', 'error');
 * ```
 */
export function showToast(
  message: string,
  type: 'success' | 'error' | 'info' = 'info',
  duration: number = 3000
): void {
  const toast = document.createElement('div');

  // Base styles
  toast.className = 'fixed top-4 right-4 px-6 py-4 rounded-md shadow-lg transition-opacity duration-300 z-50 max-w-md';

  // Type-specific styles
  const typeStyles = {
    success: 'bg-green-50 border border-green-200 text-green-800',
    error: 'bg-red-50 border border-red-200 text-red-800',
    info: 'bg-blue-50 border border-blue-200 text-blue-800',
  };

  toast.className += ' ' + typeStyles[type];
  toast.textContent = message;
  toast.style.opacity = '0';

  document.body.appendChild(toast);

  // Fade in
  setTimeout(() => {
    toast.style.opacity = '1';
  }, 10);

  // Fade out and remove
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 300);
  }, duration);
}

/**
 * Show a confirmation dialog (client-side only).
 *
 * Creates a custom modal dialog as a modern replacement for the browser's confirm().
 * Returns a Promise that resolves to true if confirmed, false if cancelled.
 *
 * @param message - The confirmation message to display
 * @param title - Optional title for the dialog (default: 'Confirm')
 * @param confirmText - Text for the confirm button (default: 'Confirm')
 * @param cancelText - Text for the cancel button (default: 'Cancel')
 *
 * Usage:
 * ```typescript
 * import { showConfirm } from '@/lib/admin-auth';
 * const confirmed = await showConfirm('Delete this item?', 'Confirm Delete');
 * if (confirmed) {
 *   // User clicked confirm
 * }
 * ```
 */
export function showConfirm(
  message: string,
  title: string = 'Confirm',
  confirmText: string = 'Confirm',
  cancelText: string = 'Cancel'
): Promise<boolean> {
  return new Promise((resolve) => {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';

    // Create modal content
    const modal = document.createElement('div');
    modal.className = 'bg-white rounded-lg shadow-xl max-w-md w-full p-6 transform transition-all';

    // Title
    const titleEl = document.createElement('h3');
    titleEl.className = 'text-lg font-semibold text-gray-900 mb-3';
    titleEl.textContent = title;

    // Message
    const messageEl = document.createElement('p');
    messageEl.className = 'text-gray-600 mb-6 whitespace-pre-line';
    messageEl.textContent = message;

    // Buttons container
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'flex gap-3 justify-end';

    // Cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition font-medium';
    cancelBtn.textContent = cancelText;
    cancelBtn.onclick = () => {
      cleanup();
      resolve(false);
    };

    // Confirm button
    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'px-4 py-2 text-white bg-red-600 hover:bg-red-700 rounded-md transition font-medium';
    confirmBtn.textContent = confirmText;
    confirmBtn.onclick = () => {
      cleanup();
      resolve(true);
    };

    // Cleanup function
    const cleanup = () => {
      overlay.style.opacity = '0';
      setTimeout(() => {
        document.body.removeChild(overlay);
      }, 200);
    };

    // Close on overlay click
    overlay.onclick = (e) => {
      if (e.target === overlay) {
        cleanup();
        resolve(false);
      }
    };

    // Close on Escape key
    const escapeHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        cleanup();
        resolve(false);
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    document.addEventListener('keydown', escapeHandler);

    // Assemble modal
    buttonsDiv.appendChild(cancelBtn);
    buttonsDiv.appendChild(confirmBtn);
    modal.appendChild(titleEl);
    modal.appendChild(messageEl);
    modal.appendChild(buttonsDiv);
    overlay.appendChild(modal);

    // Add to DOM with fade-in
    overlay.style.opacity = '0';
    document.body.appendChild(overlay);
    setTimeout(() => {
      overlay.style.opacity = '1';
    }, 10);

    // Focus confirm button
    setTimeout(() => confirmBtn.focus(), 100);
  });
}
