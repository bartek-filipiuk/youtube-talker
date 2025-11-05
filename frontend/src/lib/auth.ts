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
 * import { showToast } from '@/lib/auth';
 * showToast('Message sent successfully!', 'success');
 * showToast('Failed to send message', 'error');
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
 * import { showConfirm } from '@/lib/auth';
 * const confirmed = await showConfirm('Delete this conversation?', 'Confirm Delete');
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
